"""Cria o mapa "Topologia NOC SENAI - Fibra x Rádio" no Zabbix (recria se já existir).

Visual: fundo e ícones gerados por mapa_visual.py (pasta mapa/), enviados ao Zabbix como imagens.
Enlaces mudam de cor pelos triggers: verde = normal, vermelho = caído, laranja = perda/instável,
amarelo = previsão de piora. O R-FILIAL e as antenas trocam para o ícone vermelho quando há problema.
"""
import base64
from pathlib import Path

from zbx import call

NOME = "Topologia NOC SENAI - Fibra x Rádio"
HOST = "R-FILIAL"
PASTA = Path(__file__).parent / "mapa"
VERDE, VERMELHO, LARANJA, AMARELO, CINZA = "3FB58A", "E5484D", "F2A33A", "E6C229", "9AA5B1"
ICONE = 96  # lado dos ícones em px; posição no Zabbix = canto superior esquerdo


def enviar_imagem(nome, tipo):
    """Cria ou atualiza a imagem no Zabbix (tipo 1 = ícone, 2 = fundo) e devolve o imageid."""
    dados = base64.b64encode((PASTA / f"{nome}.png").read_bytes()).decode()
    existente = call("image.get", {"filter": {"name": [nome]}, "output": ["imageid"]})
    if existente:
        call("image.update", {"imageid": existente[0]["imageid"], "image": dados})
        return existente[0]["imageid"]
    return call("image.create", {"name": nome, "imagetype": tipo, "image": dados})["imageids"][0]


fundo = enviar_imagem("NOC_fundo_topologia", 2)
img = {f"{t}{s}": enviar_imagem(f"NOC_{t}{s}", 1)
       for t in ("roteador", "switch", "antena", "servidor", "pcs") for s in ("", "_alerta")}

hostid = call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid"]})[0]["hostid"]
trg = {t["description"]: t["triggerid"] for t in call("trigger.get", {"hostids": hostid, "inherited": False,
                                                                      "output": ["description"]})}


def t(inicio):
    """triggerid pelo começo do nome (os nomes completos estão em fix_redundancia.py)."""
    return next(v for k, v in trg.items() if k.startswith(inicio))


FIBRA_CAIU, RADIO_CAIU, ISOLADA = t("Link FIBRA caiu"), t("Link RÁDIO"), t("FILIAL ISOLADA")
FIBRA_INSTAVEL, RADIO_LAT, RADIO_PREV = t("Link FIBRA instável"), t("Latência alta no RÁDIO"), t("PREVISÃO")
RADIO_NORMAL, RADIO_PERDA = t("RÁDIO acima do normal"), t("RÁDIO com perda")


def pos(cx, cy):
    return {"x": cx - ICONE // 2, "y": cy - ICONE // 2}


def imagem(sid, icone, cx, cy, rotulo):
    return {"selementid": sid, "elementtype": 4, "iconid_off": img[icone], "label": rotulo,
            "label_location": 0, **pos(cx, cy)}


def com_estado(sid, tipo, elementos, icone, cx, cy, rotulo):
    """Elemento ligado a host (0) ou triggers (2): troca para o ícone vermelho quando há problema."""
    return {"selementid": sid, "elementtype": tipo, "elements": elementos, "iconid_off": img[icone],
            "iconid_on": img[f"{icone}_alerta"], "label": rotulo, "label_location": 0, **pos(cx, cy)}


def ligacao(a, b, gatilhos=(), rotulo="", tracejado=False):
    return {"selementid1": a, "selementid2": b, "drawtype": 4 if tracejado else 2, "color": VERDE, "label": rotulo,
            "linktriggers": [{"triggerid": i, "drawtype": 4 if tracejado else 2, "color": cor} for i, cor in gatilhos]}


ANTENAS = [{"triggerid": i} for i in (RADIO_CAIU, RADIO_PERDA, RADIO_PREV)]
selements = [
    # Matriz (zona azul, x 30-520)
    imagem("pcm", "pcs", 170, 215, "PCs da Matriz"),
    imagem("swm", "switch", 170, 330, "SW-MATRIZ"),
    imagem("zbx", "servidor", 170, 520, "Zabbix NOC + IA\n192.168.10.50"),
    imagem("rm", "roteador", 400, 330, "R-MATRIZ\n192.168.10.1"),
    com_estado("am", 2, ANTENAS, "antena", 400, 555, "Rádio Matriz\n10.0.2.3"),
    # Filial (zona verde, x 880-1370)
    com_estado("rf", 0, [{"hostid": hostid}], "roteador", 1000, 330, "R-FILIAL\n192.168.20.1"),
    com_estado("af", 2, ANTENAS, "antena", 1000, 555, "Rádio Filial\n10.0.2.4"),
    imagem("swf", "switch", 1230, 330, "SW-FILIAL"),
    imagem("pcf", "pcs", 1230, 215, "PCs da Filial"),
]
LAT = "{{?last(/R-FILIAL/icmppingsec[%s,3,,,500])*1000}.fmtnum(1)} ms"
radio = [(RADIO_CAIU, VERMELHO), (ISOLADA, VERMELHO), (RADIO_PERDA, LARANJA), (RADIO_LAT, LARANJA),
         (RADIO_PREV, AMARELO), (RADIO_NORMAL, AMARELO)]
links = [
    ligacao("pcm", "swm"), ligacao("zbx", "swm"), ligacao("swm", "rm"),
    ligacao("rm", "rf", [(FIBRA_CAIU, VERMELHO), (ISOLADA, VERMELHO), (FIBRA_INSTAVEL, LARANJA)],
            LAT % "10.0.1.2"),
    ligacao("rm", "am", radio), ligacao("am", "af", radio, LAT % "10.0.2.2", tracejado=True), ligacao("af", "rf", radio),
    ligacao("rf", "swf"), ligacao("swf", "pcf"),
]

for antigo in call("map.get", {"filter": {"name": [NOME]}, "output": ["sysmapid"]}):
    call("map.delete", [antigo["sysmapid"]])
mapa = call("map.create", {"name": NOME, "width": 1400, "height": 790, "backgroundid": fundo,
                           "highlight": 0, "expandproblem": 0, "markelements": 0, "label_type": 0,
                           "label_location": 0, "selements": selements, "links": links})["sysmapids"][0]
print(f"[ok] mapa criado (id {mapa})")
