"""Relatório de SLA em PDF: disponibilidade da fibra e do rádio, quedas, tempo no rádio, MTTR e chamados.

Sob demanda (/api/relatorio.pdf) e mensal: todo dia 1º, o do mês anterior vai no Telegram dos administradores.
"""
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from fpdf import FPDF, FontFace

import agenda
import atendimento
import auth
import fonte
import livro
import telegram
from banco import db

router = APIRouter()
VIOLETA, ROSA, CINZA, TINTA = (111, 90, 224), (217, 65, 92), (117, 114, 127), (27, 26, 33)


def _faixas_fora(pontos, serie):
    """Trechos em que o enlace não respondeu: [(início, fim)]."""
    out, ini = [], None
    for i, p in enumerate(pontos):
        if p.get(serie) is None and ini is None:
            ini = pontos[max(0, i - 1)]["t"]
        if p.get(serie) is not None and ini is not None:
            out.append((ini, p["t"]))
            ini = None
    if ini is not None:
        out.append((ini, pontos[-1]["t"]))
    return out


def _instante(texto: str) -> float:
    """Data do livro de chamados: o Analista IA grava no formato do Zabbix ("2026.10.23 17:26:01"), não em ISO."""
    try:
        return datetime.fromisoformat(texto).timestamp()
    except ValueError:
        return datetime.strptime(texto, "%Y.%m.%d %H:%M:%S").timestamp()


def metricas(de: int, ate: int):
    horas = max(1, round((time.time() - de) / 3600))
    pontos = [p for p in fonte.serie("latencia", horas) if de <= p["t"] <= ate]
    n = len(pontos) or 1
    disp = lambda chave: round(sum(1 for p in pontos if p.get(chave) is not None) / n * 100, 2)
    filial = round(sum(1 for p in pontos if p.get("fibra") is not None or p.get("radio") is not None) / n * 100, 2)
    quedas = _faixas_fora(pontos, "fibra")
    media = lambda chave: (lambda v: round(sum(v) / len(v), 2) if v else None)([p[chave] for p in pontos if p.get(chave) is not None])

    alertas = [a for a in fonte.alertas(horas) if de <= a["inicio"] <= ate]
    graves = [a for a in alertas if a["nivel"] >= 4 and a["fim"]]
    mttr = sum(a["fim"] - a["inicio"] for a in graves) / len(graves) if graves else None
    por_sev = {}
    for a in alertas:
        por_sev[a["severidade"]] = por_sev.get(a["severidade"], 0) + 1

    with db() as con:
        sg = [c for c in atendimento.listar(con, {"papel": "Administrador", "id": 0}) if de <= c["criado_em"] <= ate]
    resolvidos = [c for c in sg if c["status"] == "resolvido" and c["sla"]["solucao"]["em"]]
    no_prazo = [c for c in resolvidos if c["sla"]["solucao"]["em"] <= c["sla"]["solucao"]["prazo"]
                and (c["sla"]["resposta"]["em"] or 0) <= c["sla"]["resposta"]["prazo"]]
    noc = [c for c in livro.chamados() if de <= _instante(c["inicio"]) <= ate]
    return {
        "de": de, "ate": ate,
        "disponibilidade": {"fibra": disp("fibra"), "radio": disp("radio"), "filial": filial},
        "latencia_media": {"fibra": media("fibra"), "radio": media("radio")},
        "quedas_fibra": len(quedas), "tempo_no_radio": sum(f - i for i, f in quedas),
        "alertas": len(alertas), "por_severidade": por_sev, "mttr": mttr,
        "chamados_sg": len(sg), "sg_resolvidos": len(resolvidos), "sg_no_prazo": len(no_prazo), "chamados_noc": len(noc),
        "piores": sorted(alertas, key=lambda a: (-a["nivel"], -((a["fim"] or time.time()) - a["inicio"])))[:8],
    }


def _dur(seg):
    seg = int(seg or 0)
    h, m = seg // 3600, seg % 3600 // 60
    return f"{h}h {m:02d}min" if h else f"{m} min"


def _pct(v):
    return f"{v:.2f}%".replace(".", ",")


def _data(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


def gerar_pdf(m) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*VIOLETA)
    pdf.cell(0, 6, "S E N N A G U A R D", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*TINTA)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 11, "Relatório de disponibilidade e SLA", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*CINZA)
    pdf.cell(0, 6, f"NOC Matriz - Filial (SENAI)  |  {_data(m['de'])} a {_data(m['ate'])}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Indicadores principais
    d = m["disponibilidade"]
    blocos = [("Filial no ar", _pct(d['filial'])), ("Fibra no ar", _pct(d['fibra'])),
              ("Quedas da fibra", str(m["quedas_fibra"])), ("Tempo no rádio", _dur(m["tempo_no_radio"]))]
    largura = (pdf.w - 20 - 9) / 4
    y = pdf.get_y()
    for i, (rotulo, valor) in enumerate(blocos):
        x = 10 + i * (largura + 3)
        pdf.set_fill_color(244, 242, 250)
        pdf.rect(x, y, largura, 22, "F")
        pdf.set_xy(x + 4, y + 3)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*CINZA)
        pdf.cell(largura - 8, 4, rotulo)
        pdf.set_xy(x + 4, y + 9)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*TINTA)
        pdf.cell(largura - 8, 9, valor)
    pdf.set_y(y + 28)

    # Barras de disponibilidade
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Disponibilidade por enlace", new_x="LMARGIN", new_y="NEXT")
    for rotulo, valor, cor in (("Fibra (sfp1)", d["fibra"], VIOLETA), ("Rádio (ether1)", d["radio"], (35, 150, 139)), ("Filial (qualquer enlace)", d["filial"], (31, 157, 95))):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*TINTA)
        pdf.cell(45, 7, rotulo)
        x, yb, w = pdf.get_x(), pdf.get_y() + 2, 120
        pdf.set_fill_color(236, 234, 242)
        pdf.rect(x, yb, w, 3.5, "F")
        pdf.set_fill_color(*cor)
        pdf.rect(x, yb, w * valor / 100, 3.5, "F")
        pdf.set_x(x + w + 4)
        pdf.cell(0, 7, _pct(valor), new_x="LMARGIN", new_y="NEXT")
    lat = m["latencia_media"]
    pdf.set_text_color(*CINZA)
    pdf.cell(0, 7, f"Latência média: fibra {str(lat['fibra'] or '-').replace('.', ',')} ms, rádio {str(lat['radio'] or '-').replace('.', ',')} ms.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Alertas e chamados
    pdf.set_text_color(*TINTA)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Incidentes e atendimento", new_x="LMARGIN", new_y="NEXT")
    linhas = [
        ("Alertas no período", str(m["alertas"]) + "  (" + ", ".join(f"{k}: {v}" for k, v in m["por_severidade"].items()) + ")" if m["por_severidade"] else "0"),
        ("Tempo médio de reparo (Alta/Desastre)", _dur(m["mttr"]) if m["mttr"] else "-"),
        ("Chamados NOC (queda acima de 1 h)", str(m["chamados_noc"])),
        ("Chamados abertos pela Filial (SG)", str(m["chamados_sg"])),
        ("SG resolvidos dentro do SLA", f"{m['sg_no_prazo']} de {m['sg_resolvidos']}" + (f"  ({round(m['sg_no_prazo'] / m['sg_resolvidos'] * 100)}%)" if m["sg_resolvidos"] else "")),
    ]
    for rotulo, valor in linhas:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*CINZA)
        pdf.cell(80, 7, rotulo)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*TINTA)
        pdf.cell(0, 7, valor, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    if m["piores"]:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Principais alertas", new_x="LMARGIN", new_y="NEXT")
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(225, 222, 232)
        with pdf.table(col_widths=(20, 90, 38, 28), text_align=("LEFT", "LEFT", "LEFT", "RIGHT"),
                       headings_style=FontFace(emphasis="BOLD", color=CINZA), line_height=6, first_row_as_headings=True,
                       borders_layout="HORIZONTAL_LINES") as t:
            pdf.set_font("Helvetica", "", 8)
            t.row(("Severidade", "Problema", "Início", "Duração"))
            for a in m["piores"]:
                fim = a["fim"] or time.time()
                t.row((a["severidade"], a["nome"][:70], _data(a["inicio"]), _dur(fim - a["inicio"]) + ("" if a["fim"] else " (ativo)")))

    pdf.set_auto_page_break(False)  # o rodapé fica na mesma página
    pdf.set_y(-18)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*CINZA)
    pdf.cell(0, 5, f"Gerado pelo SennaGuard em {_data(time.time())}. Fonte: Zabbix ({'simulação' if fonte.SIMULACAO else 'dados reais'}).")
    return bytes(pdf.output())


@router.get("/api/relatorio.pdf")
def baixar(de: int | None = None, ate: int | None = None, _=auth.exigir("relatorios")):
    ate = ate or int(time.time())
    de = de or ate - 24 * 3600
    if de >= ate:
        raise HTTPException(422, "O início do período precisa ser antes do fim.")
    nome = f"sennaguard-sla-{datetime.fromtimestamp(de):%Y%m%d}-{datetime.fromtimestamp(ate):%Y%m%d}.pdf"
    return Response(gerar_pdf(metricas(de, ate)), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


def _mes_anterior(agora=None):
    agora = agora or datetime.now()
    fim = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ini = fim.replace(year=fim.year - 1, month=12) if fim.month == 1 else fim.replace(month=fim.month - 1)
    return int(ini.timestamp()), int(fim.timestamp())


@agenda.tarefa(600)
def relatorio_mensal():
    """Dia 1º, a partir das 8 h: manda o relatório do mês anterior aos administradores, uma vez só."""
    agora = datetime.now()
    if agora.day != 1 or agora.hour < 8 or not telegram.ativo():
        return
    chave = f"relatorio_mensal_{agora:%Y%m}"
    with db() as con:
        con.execute("create table if not exists marcas (chave text primary key, em integer)")
        if con.execute("select 1 from marcas where chave=?", (chave,)).fetchone():
            return
        con.execute("insert into marcas values (?,?)", (chave, int(time.time())))
        admins = [r[0] for r in con.execute("select telegram_chat_id, notificacoes from usuarios where papel='Administrador' and ativo=1 and telegram_chat_id is not null")
                  if telegram.aceita(r[1], "relatorio", urgente=True)]
    de, ate = _mes_anterior(agora)
    pdf = gerar_pdf(metricas(de, ate))
    for chat in admins:
        telegram.enviar_documento(chat, f"sennaguard-sla-{datetime.fromtimestamp(de):%Y-%m}.pdf", pdf,
                                  f"📊 Relatório de SLA de {datetime.fromtimestamp(de):%m/%Y}")
