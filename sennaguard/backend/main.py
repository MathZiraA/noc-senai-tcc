"""API do SennaGuard: visão do enlace, alertas, chamados, equipamentos e usuários do NOC.

Rodar:  uvicorn main:app --reload --port 8000
Zabbix real:  defina ZABBIX_URL (…/api_jsonrpc.php) e ZABBIX_TOKEN; sem eles, roda em simulação.
Em produção a interface já compilada (frontend/dist) é servida por esta mesma API.
"""
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

import agenda
import sonda
import anexos
import atendimento
import backup
import chat
import conhecimento
import manutencao
import perfil
import relatorio
import auth
import fonte
import livro
import telegram
import tempo_real
import teste
import tv
from banco import BANCO, db  # noqa: F401  (BANCO e db usados também por gerenciar.py)
from html import escape as _e  # texto de usuário nas mensagens HTML do Telegram

DIST = Path(__file__).parent.parent / "frontend" / "dist"
PAPEIS = ("Administrador", "Analista", "Operador", "Cliente")
SENHA_DEMO = "senai2026"  # só no modo simulação

app = FastAPI(title="SennaGuard API", docs_url=None, redoc_url=None, openapi_url=None)  # sem mapa público da API
for r in (tempo_real.router, telegram.router, tv.router, relatorio.router, manutencao.router,
          backup.router, chat.router, conhecimento.router, teste.router, anexos.router, perfil.router):
    app.include_router(r)


@app.on_event("startup")
def iniciar():
    with db() as con:
        con.execute("""create table if not exists usuarios (
            id integer primary key, nome text not null, email text unique not null, papel text not null,
            ativo integer default 1, alerta_email integer default 1, chamado_email integer default 0,
            criado_em integer, ultimo_acesso integer, senha_hash text)""")
        if "senha_hash" not in [c[1] for c in con.execute("pragma table_info(usuarios)")]:
            con.execute("alter table usuarios add column senha_hash text")
        con.execute("create table if not exists sessoes (token_hash text primary key, usuario_id integer, expira integer, ip text)")
        atendimento.criar_tabelas(con)
        anexos.criar_tabelas(con)
        perfil.criar_tabelas(con)
        telegram.criar_tabelas(con)
        tv.criar_tabelas(con)
        manutencao.criar_tabelas(con)
        teste.criar_tabelas(con)
        conhecimento.criar_tabelas(con, simulacao=fonte.SIMULACAO)
        con.execute("""create table if not exists avaliacoes_ia (eventid text, usuario_id integer, util integer, em integer,
                       primary key (eventid, usuario_id))""")
        if fonte.SIMULACAO and not con.execute("select 1 from usuarios").fetchone():
            agora, h = int(time.time()), auth.hash_senha(SENHA_DEMO)
            con.executemany("insert into usuarios (nome,email,papel,ativo,alerta_email,chamado_email,criado_em,ultimo_acesso,senha_hash) values (?,?,?,?,?,?,?,?,?)", [
                ("Matheus Ziravello", "matheus.ziravello@gmail.com", "Administrador", 1, 1, 1, agora - 40 * 86400, None, h),
                ("noc-analista", "analista@noc.local", "Analista", 1, 0, 0, agora - 30 * 86400, None, h),
                ("Plantão Matriz", "plantao@noc.local", "Operador", 1, 1, 0, agora - 12 * 86400, None, h),
                ("cliente-noc", "cliente@filial.local", "Cliente", 1, 0, 1, agora - 20 * 86400, None, h),
                ("Estagiário CTI", "estagio@noc.local", "Operador", 0, 0, 0, agora - 60 * 86400, None, h),
            ])
        if fonte.SIMULACAO and not con.execute("select 1 from chamados_manuais").fetchone():
            cliente = dict(con.execute("select * from usuarios where papel='Cliente' limit 1").fetchone())
            agora = int(time.time()) - 50 * 60
            cid = con.execute("""insert into chamados_manuais (titulo,descricao,categoria,impacto,status,contexto,aberto_por,responsavel,criado_em,atualizado_em)
                                 values (?,?,?,?,?,?,?,?,?,?)""", (
                "Sistema de vendas lento na Filial", "Desde as 10h o sistema de vendas demora para abrir as telas no caixa 2 e no estoque.",
                "lentidao", "setor", "aberto", atendimento.contexto_do_enlace(fonte.visao()), cliente["id"], None, agora, agora)).lastrowid
            atendimento.registrar(con, cid, "abertura", cliente, "Sistema de vendas lento na Filial")
    if fonte.SIMULACAO:
        livro.semear_exemplo()
        backup.semear_simulacao()
    else:
        sonda.iniciar(fonte.FIBRA_IP, fonte.RADIO_IP)
    agenda.iniciar()


# ---------------------------------------------------------------- sessão
class Login(BaseModel):
    email: str
    senha: str


def _publico(u):
    return {k: u[k] for k in ("id", "nome", "email", "papel")} | {
        "permissoes": sorted(auth.PERMISSOES[u["papel"]]), "modo": "simulação" if fonte.SIMULACAO else "zabbix",
        "telegram": bool(u.get("telegram_chat_id")), "telegram_disponivel": telegram.ativo()} | perfil.do_usuario(u)


_SENHA_FALSA = auth.hash_senha(secrets.token_hex(16))


@app.post("/api/login")
def login(dados: Login, req: Request, resp: Response):
    # O Apache acrescenta o IP real no fim do X-Forwarded-For; o começo pode ser forjado pelo cliente
    ip = req.headers.get("x-forwarded-for", req.client.host if req.client else "").split(",")[-1].strip()
    email = dados.email.strip().lower()  # a mesma forma no bloqueio e na busca: espaços não ganham tentativas novas
    chave, chave_ip = f"{ip}|{email}", f"ip|{ip}"
    if auth.bloqueado(chave) or auth.bloqueado(chave_ip, 20):  # 5 por e-mail e 20 por IP a cada 5 min
        raise HTTPException(429, "Muitas tentativas. Aguarde 5 minutos e tente de novo.")
    with db() as con:
        u = con.execute("select * from usuarios where lower(email)=?", (email,)).fetchone()
        # Sempre calcula o scrypt, mesmo sem usuário: o tempo de resposta não revela quais e-mails existem
        if not auth.confere_senha(dados.senha, u["senha_hash"] if u else _SENHA_FALSA) or not u:
            auth.falhou(chave)
            auth.falhou(chave_ip)
            raise HTTPException(401, "E-mail ou senha incorretos.")
        if not u["ativo"]:
            raise HTTPException(403, "Acesso desativado. Fale com o administrador do NOC.")
        con.execute("update usuarios set ultimo_acesso=? where id=?", (int(time.time()), u["id"]))
        auth.abrir_sessao(con, resp, u["id"], ip)
        return _publico(dict(u))


@app.post("/api/logout", status_code=204)
def logout(req: Request, resp: Response):
    with db() as con:
        auth.fechar_sessao(con, req, resp)


@app.get("/api/publico")
def publico():
    """Sem sessão: a tela de login usa para mostrar o aviso de demonstração."""
    return {"simulacao": fonte.SIMULACAO, "senha_demo": SENHA_DEMO if fonte.SIMULACAO else None}


@app.get("/api/eu")
def eu(req: Request):
    with db() as con:
        u = auth.usuario_da_sessao(con, req)
    if not u:
        raise HTTPException(401, "Sem sessão.")
    return _publico(u)


class TrocaSenha(BaseModel):
    atual: str
    nova: str = Field(min_length=8, max_length=128)


@app.put("/api/eu/senha", status_code=204)
def trocar_senha(dados: TrocaSenha, req: Request, u=auth.exigir("visao")):
    if not auth.confere_senha(dados.atual, u["senha_hash"]):
        raise HTTPException(400, "Senha atual incorreta.")
    with db() as con:
        con.execute("update usuarios set senha_hash=? where id=?", (auth.hash_senha(dados.nova), u["id"]))
        auth.derrubar_outras_sessoes(con, req, u["id"])


# ---------------------------------------------------------------- NOC
@app.get("/api/visao")
def visao(u=auth.exigir("visao")):
    v = fonte.visao()
    if "equipamentos" not in auth.PERMISSOES[u["papel"]]:  # links de internet (WAN) só para a equipe do NOC
        v.pop("internet", None)
    return v


@app.get("/api/serie/{metrica}")
def serie(metrica: Literal["latencia", "trafego", "sinal", "wan"], horas: float = 24, de: int | None = None, ate: int | None = None,
          u=auth.exigir("visao")):
    """Últimas `horas` horas, ou o intervalo `de`–`ate` (segundos Unix) do período personalizado e do zoom."""
    if metrica == "wan" and "equipamentos" not in auth.PERMISSOES[u["papel"]]:
        raise HTTPException(403, "Seu perfil não tem acesso a isso.")
    if de is not None and ate is not None:
        if not 0 < ate - de <= 31 * 86400:
            raise HTTPException(422, "Período inválido (de 1 minuto a 31 dias).")
        return fonte.serie(metrica, max(ate - de, 60) / 3600, min(ate, int(time.time())))
    return fonte.serie(metrica, min(max(horas, 1 / 60), 744))


JANELA_INCIDENTE = 60  # mesma janela do Analista IA: eventos do mesmo host em 60 s viram um incidente


@app.get("/api/alertas")
def alertas(horas: int = 168, u=auth.exigir("alertas")):
    abertos = {c["eventid"]: c["numero"] for c in livro.chamados()}
    lista = [dict(a, chamado=abertos.get(a["id"], a["chamado"])) for a in fonte.alertas(horas)]
    # Agrupa em incidentes: o primeiro evento de cada grupo dá o id do incidente
    grupos: dict[str, tuple[int, str]] = {}
    for a in sorted(lista, key=lambda a: a["inicio"]):
        g = grupos.get(a["host"])
        if g and a["inicio"] - g[0] <= JANELA_INCIDENTE:
            a["incidente"] = g[1]
        else:
            grupos[a["host"]] = (a["inicio"], a["id"])
            a["incidente"] = a["id"]
    with db() as con:
        votos = {}
        for r in con.execute("select eventid, util, usuario_id from avaliacoes_ia"):
            v = votos.setdefault(r["eventid"], {"uteis": 0, "inuteis": 0, "meu": None})
            v["uteis" if r["util"] else "inuteis"] += 1
            if r["usuario_id"] == u["id"]:
                v["meu"] = bool(r["util"])
    for a in lista:
        a["avaliacao"] = votos.get(a["id"]) if a["analise"] else None
    return lista


class Avaliacao(BaseModel):
    util: bool


@app.post("/api/alertas/{eventid}/avaliacao", status_code=204)
def avaliar_ia(eventid: str, a: Avaliacao, u=auth.exigir("reconhecer")):
    with db() as con:
        con.execute("insert or replace into avaliacoes_ia values (?,?,?,?)", (eventid, u["id"], int(a.util), int(time.time())))
    tempo_real.avisar("alertas")


@app.get("/api/ia/metricas")
def metricas_ia(_=auth.exigir("alertas")):
    """Precisão percebida do Analista IA, para a monografia: % das avaliações marcadas como úteis."""
    with db() as con:
        total, uteis = con.execute("select count(*), coalesce(sum(util), 0) from avaliacoes_ia").fetchone()
    return {"avaliacoes": total, "uteis": uteis, "percentual": round(uteis / total * 100) if total else None}


class Reconhecer(BaseModel):
    mensagem: str = Field("", max_length=500)


@app.post("/api/alertas/{eventid}/reconhecer")
def reconhecer(eventid: str, corpo: Reconhecer, u=auth.exigir("reconhecer")):
    msg = f"[{u['nome']}] {corpo.mensagem}".strip() if corpo.mensagem else ""
    ok = fonte.reconhecer(eventid, msg)
    tempo_real.avisar("alertas")
    return {"ok": ok}


@app.get("/api/chamados")
def chamados(u=auth.exigir("chamados")):
    with db() as con:
        return {"chamados": livro.chamados(), "integridade": livro.verificar(),
                "manuais": atendimento.listar(con, u), "integridade_manuais": atendimento.verificar(con)}


class NovoChamado(BaseModel):
    titulo: str = Field(min_length=4, max_length=120)
    descricao: str = Field(min_length=10, max_length=4000)
    categoria: Literal[atendimento.CATEGORIAS]
    impacto: Literal[atendimento.IMPACTOS]
    anexos: list[int] = Field(default_factory=list, max_length=anexos.POR_MENSAGEM)


@app.post("/api/chamados", status_code=201)
def abrir_chamado(c: NovoChamado, u=auth.exigir("abrir_chamado")):
    try:
        contexto = atendimento.contexto_do_enlace(fonte.visao())
    except Exception:  # Zabbix fora do ar não impede abrir o chamado
        contexto = None
    with db() as con:
        agora = int(time.time())
        cid = con.execute("""insert into chamados_manuais (titulo,descricao,categoria,impacto,contexto,aberto_por,criado_em,atualizado_em)
                             values (?,?,?,?,?,?,?,?)""", (c.titulo, c.descricao, c.categoria, c.impacto, contexto, u["id"], agora, agora)).lastrowid
        atendimento.registrar(con, cid, "abertura", u, f"{c.titulo}\n\n{c.descricao}", anexos.prender(con, c.anexos, u, cid))
        novo = atendimento.detalhe(con, cid, u)
    tempo_real.avisar("chamados")
    telegram.para_equipe(f"🆕 <b>Chamado SG-{cid}</b> · {atendimento.IMPACTOS_NOME[c.impacto]}\n{_e(c.titulo)}{_clipe(c.anexos)}\n<i>Aberto por {_e(u['nome'])}</i>",
                         tipo="chamados", exceto=u["id"])
    return novo


def _chamado_ou_404(con, cid, u):
    c = atendimento.detalhe(con, cid, u)
    if not c:
        raise HTTPException(404, "Chamado não encontrado.")
    return c


def _clipe(ids):
    return f"\n📎 {len(ids)} anexo{'s' if len(ids) > 1 else ''}" if ids else ""


@app.get("/api/chamados/manuais/{cid}")
def ver_chamado(cid: int, u=auth.exigir("chamados")):
    with db() as con:
        _chamado_ou_404(con, cid, u)
        leu = atendimento.marcar_visto(con, cid, u)
        c = atendimento.detalhe(con, cid, u)
    if leu:
        tempo_real.avisar("chamados")  # o outro lado vê o "visto às" na hora
    return c


class Comentario(BaseModel):
    texto: str = Field("", max_length=4000)
    interno: bool = False  # nota interna: só a equipe vê
    anexos: list[int] = Field(default_factory=list, max_length=anexos.POR_MENSAGEM)


@app.post("/api/chamados/manuais/{cid}/comentario")
def comentar(cid: int, c: Comentario, u=auth.exigir("chamados")):
    if not c.texto.strip() and not c.anexos:
        raise HTTPException(422, "Escreva uma mensagem ou anexe um arquivo.")
    if c.interno and u["papel"] == "Cliente":
        raise HTTPException(403, "Notas internas são só da equipe.")
    with db() as con:
        ch = _chamado_ou_404(con, cid, u)
        atendimento.registrar(con, cid, "nota" if c.interno else "comentario", u, c.texto, anexos.prender(con, c.anexos, u, cid))
        if ch["status"] == "resolvido" and u["papel"] == "Cliente":  # cliente respondendo reabre
            con.execute("update chamados_manuais set status='aberto' where id=?", (cid,))
            atendimento.registrar(con, cid, "reaberto", u)
        atendimento.marcar_visto(con, cid, u)  # quem escreve já leu tudo até aqui
        novo = atendimento.detalhe(con, cid, u)
    tempo_real.avisar("chamados")
    if c.interno:
        aviso = f"📝 <b>SG-{cid}</b> · nota interna de {_e(u['nome'])}\n{_e(c.texto[:400])}{_clipe(c.anexos)}"
        if ch.get("responsavel") and ch["responsavel"] != u["id"]:
            telegram.para_usuarios([ch["responsavel"]], aviso, tipo="chamados")
        elif not ch.get("responsavel"):
            telegram.para_equipe(aviso, tipo="chamados", exceto=u["id"])
        return novo
    aviso = f"💬 <b>SG-{cid}</b> · {_e(u['nome'])} respondeu\n{_e(c.texto[:400])}{_clipe(c.anexos)}"
    if u["papel"] != "Cliente":
        telegram.para_usuarios([ch["aberto_por"]], aviso, tipo="chamados")
    elif ch.get("responsavel"):
        telegram.para_usuarios([ch["responsavel"]], aviso, tipo="chamados")
    else:
        telegram.para_equipe(aviso, tipo="chamados")
    return novo


class MudarStatus(BaseModel):
    status: Literal[atendimento.STATUS]


@app.post("/api/chamados/manuais/{cid}/status")
def mudar_status(cid: int, m: MudarStatus, u=auth.exigir("atender_chamado")):
    with db() as con:
        ch = _chamado_ou_404(con, cid, u)
        if ch["status"] != m.status:
            con.execute("update chamados_manuais set status=?, responsavel=coalesce(responsavel, ?) where id=?", (m.status, u["id"], cid))
            atendimento.registrar(con, cid, m.status, u)
            texto = {"em_atendimento": f"🔧 <b>SG-{cid}</b> está em atendimento com {_e(u['nome'])}.",
                     "resolvido": f"✅ <b>SG-{cid}</b> foi resolvido por {_e(u['nome'])}. Se o problema voltar, é só responder no painel.",
                     "aberto": f"↩️ <b>SG-{cid}</b> voltou para aberto."}[m.status]
            telegram.para_usuarios([ch["aberto_por"]], texto, tipo="chamados")
            if m.status == "resolvido":
                conhecimento.rascunhar_de_chamado(cid)  # vira rascunho na base de conhecimento
        novo = atendimento.detalhe(con, cid, u)
    tempo_real.avisar("chamados")
    return novo


@app.get("/api/equipamentos")
def equipamentos(_=auth.exigir("equipamentos")):
    return fonte.equipamentos()


@app.get("/api/equipamentos/{nome}")
def equipamento(nome: str, _=auth.exigir("equipamentos")):
    e = fonte.detalhe_equipamento(nome)
    if not e:
        raise HTTPException(404, "Equipamento não encontrado no Zabbix.")
    return e


# ---------------------------------------------------------------- usuários (só Administrador)
class Usuario(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    email: EmailStr
    papel: Literal[PAPEIS]
    ativo: bool = True
    alerta_email: bool = True
    chamado_email: bool = False
    senha: str | None = Field(None, min_length=8, max_length=128)  # obrigatória ao criar; ao editar, só se for trocar


CAMPOS = "id,nome,email,papel,ativo,alerta_email,chamado_email,criado_em,ultimo_acesso,foto_em,telegram_chat_id is not null as telegram"


def _admins_ativos(con, exceto):
    return con.execute("select count(*) from usuarios where papel='Administrador' and ativo=1 and id!=?", (exceto,)).fetchone()[0]


@app.get("/api/usuarios")
def listar_usuarios(_=auth.exigir("usuarios")):
    with db() as con:
        return [dict(r) for r in con.execute(f"select {CAMPOS} from usuarios order by ativo desc, nome")]


@app.post("/api/usuarios", status_code=201)
def criar_usuario(u: Usuario, _=auth.exigir("usuarios")):
    if not u.senha:
        raise HTTPException(422, "Defina uma senha inicial (mínimo 8 caracteres).")
    try:
        with db() as con:
            cur = con.execute("insert into usuarios (nome,email,papel,ativo,alerta_email,chamado_email,criado_em,senha_hash) values (?,?,?,?,?,?,?,?)",
                              (u.nome, u.email, u.papel, u.ativo, u.alerta_email, u.chamado_email, int(time.time()), auth.hash_senha(u.senha)))
            return dict(con.execute(f"select {CAMPOS} from usuarios where id=?", (cur.lastrowid,)).fetchone())
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Já existe um usuário com esse e-mail.")


@app.put("/api/usuarios/{uid}")
def editar_usuario(uid: int, u: Usuario, req: Request, eu=auth.exigir("usuarios")):
    with db() as con:
        if (u.papel != "Administrador" or not u.ativo) and not _admins_ativos(con, uid):
            raise HTTPException(409, "O NOC precisa de pelo menos um administrador ativo.")
        try:
            n = con.execute("update usuarios set nome=?,email=?,papel=?,ativo=?,alerta_email=?,chamado_email=? where id=?",
                            (u.nome, u.email, u.papel, u.ativo, u.alerta_email, u.chamado_email, uid)).rowcount
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Já existe um usuário com esse e-mail.")
        if not n:
            raise HTTPException(404, "Usuário não encontrado.")
        if u.senha:
            con.execute("update usuarios set senha_hash=? where id=?", (auth.hash_senha(u.senha), uid))
        if u.senha or not u.ativo:  # derruba as sessões abertas dele
            if uid == eu["id"]:
                auth.derrubar_outras_sessoes(con, req, uid)
            else:
                con.execute("delete from sessoes where usuario_id=?", (uid,))
        return dict(con.execute(f"select {CAMPOS} from usuarios where id=?", (uid,)).fetchone())


@app.delete("/api/usuarios/{uid}", status_code=204)
def remover_usuario(uid: int, eu=auth.exigir("usuarios")):
    if uid == eu["id"]:
        raise HTTPException(409, "Você não pode remover a si mesmo.")
    with db() as con:
        alvo = con.execute("select papel from usuarios where id=?", (uid,)).fetchone()
        if alvo and alvo["papel"] == "Administrador" and not _admins_ativos(con, uid):
            raise HTTPException(409, "O NOC precisa de pelo menos um administrador ativo.")
        con.execute("delete from sessoes where usuario_id=?", (uid,))
        # Nada fica ligado ao id: o SQLite reaproveita o maior id e o próximo usuário herdaria foto, códigos e anexos
        con.execute("delete from telegram_codigos where usuario_id=?", (uid,))
        con.execute("delete from anexos where enviado_por=? and chamado_id is null", (uid,))
        con.execute("delete from usuarios where id=?", (uid,))
    (perfil.FOTOS / str(uid)).unlink(missing_ok=True)


# ---------------------------------------------------------------- interface compilada (produção)
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):
        arquivo = (DIST / caminho).resolve()
        if caminho and arquivo.is_file() and DIST.resolve() in arquivo.parents:
            return FileResponse(arquivo)
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
