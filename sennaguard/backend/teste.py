"""Teste de failover com aprovação: um admin aprova, o SennaGuard desliga a fibra (sfp1) no R-MATRIZ por 60 s,
mede pelo ping na LAN da Filial quanto tempo a rede ficou sem resposta na ida (fibra -> rádio) e na volta,
e gera o laudo.

Segurança:
- usuário próprio no R-MATRIZ (sennaguard-teste), só aceito do IP do servidor e só com chave;
- o app executa sempre a mesma linha fixa;
- o religamento roda no próprio roteador (`:execute`), então a fibra volta mesmo se o servidor cair no meio do teste.
"""
import json
import os
import random
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

import agenda
import auth
import fonte
import telegram
import tempo_real
from banco import db
from html import escape as _e  # texto de usuário nas mensagens HTML do Telegram

router = APIRouter()
CHAVE = Path(os.environ.get("SENNAGUARD_TESTE_KEY", "/etc/sennaguard/mikrotik_teste_key"))
USUARIO = os.environ.get("SENNAGUARD_TESTE_USER", "sennaguard-teste")
R_MATRIZ = os.environ.get("NOC_LOOPBACK_MATRIZ", "10.255.255.1")
LAN_FILIAL = os.environ.get("NOC_LAN_FILIAL", "192.168.20.1")
DURACAO = 60  # segundos com a fibra desligada
LIMITE_OK = 10  # acima disso o Zabbix já acusaria "failover lento"
COMANDO = f':execute script="/interface disable sfp1-WAN-FIBRA; :delay {DURACAO}s; /interface enable sfp1-WAN-FIBRA"'
_rodando = threading.Lock()


def criar_tabelas(con):
    con.execute("""create table if not exists testes (id integer primary key, pedido_por integer, pedido_por_nome text, motivo text,
                   agendado_para integer, status text default 'pendente', decidido_por text, decidido_em integer,
                   inicio integer, fim integer, resultado text, criado_em integer)""")


def _h(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m %H:%M") if ts else "assim que aprovado"


def _publico(r):
    t = dict(r)
    t["resultado"] = json.loads(t["resultado"]) if t["resultado"] else None
    return t


def _medir(inicio_teste):
    """Pinga a LAN da Filial a cada 0,5 s durante o teste. Devolve [(t, respondeu)]."""
    amostras, fim = [], inicio_teste + DURACAO + 40
    if fonte.SIMULACAO:  # na demonstração o resultado sai em 8 s, com as mesmas amostras de 0,5 s
        time.sleep(8)
        return [(round(i * 0.5, 2), not (i * 0.5 < _sim["ida"] or DURACAO <= i * 0.5 < DURACAO + _sim["volta"]))
                for i in range(int((DURACAO + 40) / 0.5))]
    while time.time() < fim:
        t = time.time()
        ok = subprocess.run(["ping", "-c", "1", "-W", "1", LAN_FILIAL], capture_output=True).returncode == 0
        amostras.append((round(t - inicio_teste, 2), ok))
        time.sleep(max(0, 0.5 - (time.time() - t)))
    return amostras


_sim = {"ida": 3.9, "volta": 0.0}


def _quedas(amostras):
    """Trechos sem resposta: [(começo, duração)] em segundos desde o início."""
    out, ini = [], None
    for t, ok in amostras:
        if not ok and ini is None:
            ini = t
        if ok and ini is not None:
            out.append((ini, round(t - ini, 1)))
            ini = None
    if ini is not None:
        out.append((ini, round(amostras[-1][0] - ini, 1)))
    return out


def _executar(tid):
    with _rodando:
        inicio = int(time.time())
        with db() as con:
            con.execute("update testes set status='executando', inicio=? where id=?", (inicio, tid))
        tempo_real.avisar("testes")
        try:
            if fonte.SIMULACAO:
                _sim.update(ida=round(random.uniform(3.2, 4.6), 1), volta=random.choice([0.0, 0.0, 0.5]))
            else:
                if not CHAVE.exists():
                    raise RuntimeError(f"chave do usuário de teste ausente em {CHAVE}")
                r = subprocess.run(["ssh", "-i", str(CHAVE), "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                                    "-o", "StrictHostKeyChecking=accept-new", f"{USUARIO}@{R_MATRIZ}", COMANDO],
                                   capture_output=True, text=True, timeout=30)
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip()[:300] or f"ssh saiu com código {r.returncode}")
            amostras = _medir(inicio)
            quedas = _quedas(amostras)
            ida = next((d for t, d in quedas if t < DURACAO / 2), 0.0)
            volta = next((d for t, d in quedas if t >= DURACAO - 2), 0.0)
            ok = ida <= LIMITE_OK and amostras[-1][1]
            resultado = {"ida_s": ida, "volta_s": volta, "aprovado": ok, "amostras": len(amostras),
                         "quedas": quedas, "filial_respondendo_no_fim": amostras[-1][1], "duracao_s": DURACAO}
            status = "concluido"
        except Exception as e:
            resultado, status = {"erro": str(e)}, "falhou"
        with db() as con:
            con.execute("update testes set status=?, fim=?, resultado=? where id=?", (status, int(time.time()), json.dumps(resultado), tid))
        tempo_real.avisar("testes")
        if status == "concluido":
            texto = (f"🧪 <b>Teste de failover #{tid}: {'APROVADO' if resultado['aprovado'] else 'REPROVADO'}</b>\n"
                     f"Fibra → rádio: {resultado['ida_s']} s sem resposta\nRádio → fibra: "
                     + (f"{resultado['volta_s']} s" if resultado["volta_s"] else "sem perda"))
        else:
            texto = f"⚠️ Teste de failover #{tid} falhou: {resultado['erro']}"
        telegram.para_equipe(texto, papeis=("Administrador", "Analista"))


@agenda.tarefa(5)
def disparar_aprovados():
    if _rodando.locked():
        return
    with db() as con:
        r = con.execute("select id from testes where status='aprovado' and coalesce(agendado_para, 0)<=? order by id limit 1",
                        (int(time.time()),)).fetchone()
    if r:
        threading.Thread(target=_executar, args=(r["id"],), daemon=True).start()


class Pedido(BaseModel):
    motivo: str = Field(min_length=4, max_length=300)
    agendado_para: int | None = None


@router.get("/api/testes")
def listar(_=auth.exigir("testes")):
    with db() as con:
        return [_publico(r) for r in con.execute("select * from testes order by id desc limit 50")]


@router.post("/api/testes", status_code=201)
def pedir(p: Pedido, u=auth.exigir("testes")):
    if p.agendado_para and p.agendado_para < time.time() - 60:
        raise HTTPException(422, "O horário agendado já passou.")
    with db() as con:
        tid = con.execute("insert into testes (pedido_por, pedido_por_nome, motivo, agendado_para, criado_em) values (?,?,?,?,?)",
                          (u["id"], u["nome"], p.motivo, p.agendado_para, int(time.time()))).lastrowid
    tempo_real.avisar("testes")
    telegram.para_equipe(f"🧪 <b>Pedido de teste de failover #{tid}</b> por {_e(u['nome'])}\n{_e(p.motivo)}\nQuando: {_h(p.agendado_para)}\n"
                         "Aprove ou recuse em SennaGuard → Testes de failover.", papeis=("Administrador",))
    return {"id": tid}


def _decidir(tid, u, novo, permitido_de):
    with db() as con:
        r = con.execute("select status, pedido_por from testes where id=?", (tid,)).fetchone()
        if not r:
            raise HTTPException(404, "Teste não encontrado.")
        if r["status"] not in permitido_de:
            raise HTTPException(409, f"O teste está {r['status']} e não pode mudar para {novo}.")
        # O teste derruba a fibra: sempre duas pessoas (quem pede não aprova, nem sendo administrador)
        if novo == "aprovado" and r["pedido_por"] == u["id"]:
            raise HTTPException(403, "Quem pediu o teste não pode aprová-lo. Peça a outro administrador.")
        con.execute("update testes set status=?, decidido_por=?, decidido_em=? where id=?", (novo, u["nome"], int(time.time()), tid))
    tempo_real.avisar("testes")


@router.post("/api/testes/{tid}/aprovar", status_code=204)
def aprovar(tid: int, u=auth.exigir("aprovar_teste")):
    _decidir(tid, u, "aprovado", ("pendente",))


@router.post("/api/testes/{tid}/recusar", status_code=204)
def recusar(tid: int, u=auth.exigir("aprovar_teste")):
    _decidir(tid, u, "recusado", ("pendente", "aprovado"))


@router.post("/api/testes/{tid}/cancelar", status_code=204)
def cancelar(tid: int, u=auth.exigir("testes")):
    with db() as con:
        r = con.execute("select pedido_por from testes where id=?", (tid,)).fetchone()
    if r and r["pedido_por"] != u["id"] and "aprovar_teste" not in auth.PERMISSOES[u["papel"]]:
        raise HTTPException(403, "Só quem pediu ou um administrador pode cancelar.")
    _decidir(tid, u, "cancelado", ("pendente", "aprovado"))


@router.get("/api/testes/{tid}/laudo.pdf")
def laudo(tid: int, _=auth.exigir("testes")):
    from fpdf import FPDF
    with db() as con:
        r = con.execute("select * from testes where id=?", (tid,)).fetchone()
    if not r or r["status"] != "concluido":
        raise HTTPException(404, "Laudo disponível só para testes concluídos.")
    t, res = dict(r), json.loads(r["resultado"])
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(111, 90, 224)
    pdf.cell(0, 6, "S E N N A G U A R D", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(27, 26, 33)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 11, f"Laudo do teste de failover #{tid}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*((31, 157, 95) if res["aprovado"] else (217, 65, 92)))
    pdf.cell(0, 10, "APROVADO" if res["aprovado"] else "REPROVADO", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(27, 26, 33)
    pdf.set_font("Helvetica", "", 10)
    for k, v in [("Pedido por", f"{t['pedido_por_nome']} ({t['motivo']})"), ("Aprovado por", t["decidido_por"] or "-"),
                 ("Executado em", datetime.fromtimestamp(t["inicio"]).strftime("%d/%m/%Y %H:%M:%S")),
                 ("Procedimento", f"sfp1-WAN-FIBRA desligada no R-MATRIZ por {res['duracao_s']} s; ping na LAN da Filial ({LAN_FILIAL}) a cada 0,5 s"),
                 ("Fibra -> rádio (ida)", f"{str(res['ida_s']).replace('.', ',')} s sem resposta (limite {LIMITE_OK} s)"),
                 ("Rádio -> fibra (volta)", f"{str(res['volta_s']).replace('.', ',')} s sem resposta" if res["volta_s"] else "troca transparente, sem perda"),
                 ("Filial respondendo no fim", "sim" if res["filial_respondendo_no_fim"] else "NÃO"),
                 ("Amostras de ping", str(res["amostras"]))]:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(117, 114, 127)
        pdf.cell(55, 8, k)
        pdf.set_text_color(27, 26, 33)
        # A fonte padrão do PDF só tem Latin-1: emoji ou "→" no motivo trocam por "?" em vez de derrubar o laudo
        pdf.multi_cell(0, 8, v.encode("latin-1", "replace").decode("latin-1"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(117, 114, 127)
    pdf.multi_cell(0, 5, f"Gerado pelo SennaGuard em {datetime.now():%d/%m/%Y %H:%M}. Fonte: {'simulação' if fonte.SIMULACAO else 'medição real'}.")
    return Response(bytes(pdf.output()), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="laudo-failover-{tid}.pdf"'})
