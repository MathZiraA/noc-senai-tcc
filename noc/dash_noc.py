"""Reconstrói o dashboard "NOC - Monitoramento de Redundância (OFICIAL)" (idempotente: substitui as páginas).

Página 1 - Redundância: estado e latência dos enlaces, linha do tempo UP/DOWN, tráfego fibra x rádio,
problemas ativos e as análises enviadas pela IA.
Página 2 - Saúde do R-FILIAL: CPU, memória, temperatura e interfaces (preenchidos quando o SNMP responder).
Gráficos por padrão de nome (ex.: "*ether2*Bits*") passam a mostrar dados sozinhos depois da descoberta SNMP.
"""
import config
from zbx import call

DASH = "NOC - Monitoramento de Redundância (OFICIAL)"
HOST = config.HOST
GRUPO = config.GRUPO
ACAO_IA = "Analista IA - Investigação de incidentes"
MIDIA_EMAIL = "Gmail Alertas SENAI"
AZUL, LARANJA, VERDE, VERMELHO, AMARELO = "1E88E5", "FB8C00", "43A047", "E53935", "FDD835"


def campo(tipo, nome, valor):
    return {"type": tipo, "name": nome, "value": valor}


def item(nome, itemid, x, y, w, h, limites):
    """Widget de valor com cor por faixa: limites = [(cor, a partir de), ...]."""
    fields = [campo(4, "itemid.0", itemid)]
    for i, (cor, valor) in enumerate(limites):
        fields += [campo(1, f"thresholds.{i}.color", cor), campo(1, f"thresholds.{i}.threshold", valor)]
    return {"type": "item", "name": nome, "x": x, "y": y, "width": w, "height": h, "fields": fields}


def grafico(nome, x, y, w, h, series, extra=()):
    """series = [(padrão do item, cor, tipo de traço 0=linha 2=degrau), ...]"""
    fields = []
    for i, (padrao, cor, tipo) in enumerate(series):
        fields += [campo(1, f"ds.{i}.hosts.0", HOST), campo(1, f"ds.{i}.items.0", padrao),
                   campo(1, f"ds.{i}.color", cor), campo(0, f"ds.{i}.type", tipo), campo(0, f"ds.{i}.fill", 2)]
    return {"type": "svggraph", "name": nome, "x": x, "y": y, "width": w, "height": h,
            "fields": fields + list(extra)}


hostid = call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid"]})[0]["hostid"]
grupo = call("hostgroup.get", {"filter": {"name": [GRUPO]}, "output": ["groupid"]})[0]["groupid"]
acao = call("action.get", {"filter": {"name": [ACAO_IA]}, "output": ["actionid"]})[0]["actionid"]
email = call("mediatype.get", {"filter": {"name": [MIDIA_EMAIL]}, "output": ["mediatypeid"]})[0]["mediatypeid"]
itens = {i["key_"]: i["itemid"] for i in call("item.get", {"hostids": hostid, "search": {"key_": "icmpping"},
                                                             "output": ["key_"]})}
FIBRA, RADIO = itens[config.K_FIBRA], itens[config.K_RADIO]
LAT_FIBRA, LAT_RADIO = itens[config.K_LAT_FIBRA], itens[config.K_LAT_RADIO]
CAMINHO = call("item.get", {"hostids": hostid, "filter": {"key_": "noc.caminho_ativo"}, "output": ["itemid"]})[0]["itemid"]
UP_DOWN = [(VERMELHO, "0"), (VERDE, "1")]
LATENCIA = [(VERDE, "0"), (AMARELO, "0.02"), (VERMELHO, "0.05")]

redundancia = [
    # Linha 1: o que um técnico precisa ver em 2 segundos
    item("CAMINHO ATIVO MATRIZ ↔ FILIAL", CAMINHO, 0, 0, 16, 4, [(VERMELHO, "0"), (LARANJA, "1"), (VERDE, "2")]),
    item("FIBRA (principal)", FIBRA, 16, 0, 11, 4, UP_DOWN),
    item("RÁDIO (backup)", RADIO, 27, 0, 11, 4, UP_DOWN),
    item("Latência FIBRA", LAT_FIBRA, 38, 0, 9, 4, LATENCIA),
    item("Latência RÁDIO", LAT_RADIO, 47, 0, 9, 4, LATENCIA),
    {"type": "problemsbysv", "name": "Problemas por severidade", "x": 56, "y": 0, "width": 16, "height": 4,
     "fields": [campo(2, "groupids.0", grupo)]},
    # Linha 2: quando cada enlace caiu/voltou e quanto demorou
    grafico("LINHA DO TEMPO DOS ENLACES (1 = UP, 0 = DOWN)", 0, 4, 36, 6,
            [("Enlace FIBRA - estado*", AZUL, 2), ("Enlace RÁDIO - estado*", LARANJA, 2)],
            [campo(0, "lefty_static", 1), campo(1, "lefty_min", "0"), campo(1, "lefty_max", "1.1")]),
    grafico("LATÊNCIA FIBRA x RÁDIO", 36, 4, 36, 6,
            [("Enlace FIBRA - latência", AZUL, 0), ("Enlace RÁDIO - latência", LARANJA, 0)]),
    # Linha 3: o failover visto no tráfego (aparece após a descoberta SNMP das interfaces)
    grafico("TRÁFEGO: FIBRA (ether2) x RÁDIO (ether3) — no failover o tráfego muda de caminho", 0, 10, 72, 6,
            [("*ether2*Bits*", AZUL, 0), ("*ether3*Bits*", LARANJA, 0)]),
    # Linha 4: o que está acontecendo e o que a IA disse
    {"type": "problems", "name": "PROBLEMAS ATIVOS", "x": 0, "y": 16, "width": 40, "height": 7,
     "fields": [campo(2, "groupids.0", grupo), campo(0, "show_lines", 15), campo(0, "show_timeline", 1)]},
    {"type": "actionlog", "name": "ANÁLISES DA IA ENVIADAS POR E-MAIL", "x": 40, "y": 16, "width": 32, "height": 7,
     "fields": [campo(12, "actionids.0", acao), campo(13, "mediatypeids.0", email), campo(0, "show_lines", 10)]},
]

saude = [
    {"type": "hostavail", "name": "Disponibilidade (SNMP / ICMP)", "x": 0, "y": 0, "width": 24, "height": 4,
     "fields": [campo(2, "groupids.0", grupo)]},
    {"type": "clock", "name": "Horário NOC", "x": 24, "y": 0, "width": 12, "height": 4, "fields": []},
    {"type": "actionlog", "name": "Todas as notificações enviadas", "x": 36, "y": 0, "width": 36, "height": 4,
     "fields": [campo(13, "mediatypeids.0", email), campo(0, "show_lines", 5)]},
    grafico("CPU (%)", 0, 4, 24, 6, [("*CPU utilization*", AZUL, 0)]),
    grafico("Memória (%)", 24, 4, 24, 6, [("*Memory utilization*", VERDE, 0)]),
    grafico("Temperatura (°C)", 48, 4, 24, 6, [("*emperature*", VERMELHO, 0)]),
    grafico("Tráfego de todas as interfaces", 0, 10, 72, 6, [("Interface*Bits*", AZUL, 0)]),
]

mapa = call("map.get", {"filter": {"name": ["Topologia NOC SENAI - Fibra x Rádio"]}, "output": ["sysmapid"]})
topologia = [{"type": "map", "name": "TOPOLOGIA — enlaces mudam de cor em tempo real", "x": 0, "y": 0, "width": 72,
              "height": 14, "fields": [campo(8, "sysmapid.0", mapa[0]["sysmapid"])]}] if mapa else []

existente = call("dashboard.get", {"filter": {"name": [DASH]}, "output": ["dashboardid"]})
d = existente[0] if existente else {"dashboardid": call("dashboard.create", {"name": DASH, "pages": [{"widgets": []}]})["dashboardids"][0]}
call("dashboard.update", {"dashboardid": d["dashboardid"], "display_period": 30, "auto_start": 1, "pages": [
    {"name": "Redundância Fibra x Rádio", "widgets": redundancia},
    {"name": "Saúde do R-FILIAL", "widgets": saude},
] + ([{"name": "Mapa da topologia", "widgets": topologia}] if topologia else [])})
print(f"[ok] dashboard reconstruído: {2 + bool(topologia)} páginas")
