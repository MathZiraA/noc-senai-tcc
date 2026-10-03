"""Cria o mapa "Topologia NOC SENAI - Fibra x Rádio" no Zabbix (recria se já existir).
Os enlaces mudam de cor pelos triggers: verde = normal, vermelho = caído, laranja = perda/instável,
amarelo = previsão de degradação. O R-FILIAL e as antenas acendem conforme os problemas."""
from zbx import call

NOME = "Topologia NOC SENAI - Fibra x Rádio"
HOST = "R-FILIAL"
VERDE, VERMELHO, LARANJA, AMARELO, CINZA = "2E7D32", "D32F2F", "F57C00", "F9A825", "607D8B"

img = {i["name"]: i["imageid"] for i in call("image.get", {"output": ["name"], "filter": {"imagetype": 1}})}
hostid = call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid"]})[0]["hostid"]
trg = {t["description"]: t["triggerid"] for t in call("trigger.get", {"hostids": hostid, "inherited": False,
                                                                      "output": ["description"]})}


def t(inicio):
    """triggerid pelo começo do nome (os nomes completos estão em fix_redundancia.py)."""
    return next(v for k, v in trg.items() if k.startswith(inicio))


FIBRA_CAIU, RADIO_CAIU, ISOLADA = t("Link FIBRA caiu"), t("Link RÁDIO"), t("FILIAL ISOLADA")
FIBRA_INSTAVEL, RADIO_LAT, RADIO_PREV = t("Link FIBRA instável"), t("Latência alta no RÁDIO"), t("PREVISÃO")
RADIO_NORMAL, RADIO_PERDA = t("RÁDIO acima do normal"), t("RÁDIO com perda")


def imagem(sid, nome_img, x, y, rotulo):
    return {"selementid": sid, "elementtype": 4, "iconid_off": img[nome_img], "x": x, "y": y, "label": rotulo,
            "label_location": 0}


def gatilhos(sid, nome_img, x, y, rotulo, ids):
    return {"selementid": sid, "elementtype": 2, "elements": [{"triggerid": i} for i in ids],
            "iconid_off": img[nome_img], "x": x, "y": y, "label": rotulo, "label_location": 0}


def ligacao(a, b, rotulo, gat):
    return {"selementid1": a, "selementid2": b, "drawtype": 2, "color": VERDE, "label": rotulo,
            "linktriggers": [{"triggerid": i, "drawtype": 2, "color": cor} for i, cor in gat]}


LAT = "{{?last(/R-FILIAL/icmppingsec[%s,3,,,500])*1000}.fmtnum(1)} ms"
selements = [
    imagem("zbx", "Zabbix_server_2D_(64)", 70, 120, "Zabbix NOC + Analista IA\n192.168.10.50"),
    imagem("swm", "Switch_(64)", 70, 330, "SW-MATRIZ\n192.168.10.0/24"),
    imagem("rm", "Router_(96)", 330, 300, "R-MATRIZ\n192.168.10.1"),
    {"selementid": "rf", "elementtype": 0, "elements": [{"hostid": hostid}], "iconid_off": img["Router_(96)"],
     "x": 790, "y": 300, "label": "R-FILIAL\n192.168.20.1", "label_location": 0},
    imagem("swf", "Switch_(64)", 1060, 330, "SW-FILIAL\n192.168.20.0/24"),
    gatilhos("am", "Satellite_antenna_(64)", 450, 500, "RADIO-P2P-MATRIZ\n10.0.2.3",
             [RADIO_CAIU, RADIO_PERDA, RADIO_PREV]),
    gatilhos("af", "Satellite_antenna_(64)", 700, 500, "RADIO-P2P-FILIAL\n10.0.2.4",
             [RADIO_CAIU, RADIO_PERDA, RADIO_PREV]),
]
radio = [(RADIO_CAIU, VERMELHO), (ISOLADA, VERMELHO), (RADIO_PERDA, LARANJA), (RADIO_LAT, LARANJA),
         (RADIO_PREV, AMARELO), (RADIO_NORMAL, AMARELO)]
links = [
    ligacao("zbx", "swm", "", []),
    ligacao("swm", "rm", "LAN", []),
    ligacao("rm", "rf", "FIBRA (principal, OSPF 10) 10.0.1.0/30\n" + LAT % "10.0.1.2",
            [(FIBRA_CAIU, VERMELHO), (ISOLADA, VERMELHO), (FIBRA_INSTAVEL, LARANJA)]),
    ligacao("rm", "am", "", radio),
    ligacao("am", "af", "RÁDIO (backup, OSPF 100) 10.0.2.0/29\n" + LAT % "10.0.2.2", radio),
    ligacao("af", "rf", "", radio),
    ligacao("rf", "swf", "LAN", []),
]
shapes = [
    {"type": 0, "x": 20, "y": 10, "width": 1170, "height": 40, "text": "REDE SENAI — MATRIZ x FILIAL (tempo real)",
     "font_size": 16, "font_color": "FFFFFF", "background_color": "37474F", "border_type": 0},
    {"type": 0, "x": 20, "y": 70, "width": 450, "height": 400, "text": "MATRIZ", "text_valign": 2,
     "font_size": 12, "font_color": CINZA, "border_type": 2, "border_color": CINZA, "border_width": 1},
    {"type": 0, "x": 690, "y": 70, "width": 500, "height": 400, "text": "FILIAL", "text_valign": 2,
     "font_size": 12, "font_color": CINZA, "border_type": 2, "border_color": CINZA, "border_width": 1},
    {"type": 0, "x": 20, "y": 590, "width": 1170, "height": 30, "font_size": 10, "font_color": CINZA,
     "border_type": 0, "text": "Enlaces: verde = normal | vermelho = caído | laranja = perda de pacotes ou "
                               "instável | amarelo = previsão de degradação"},
]

for antigo in call("map.get", {"filter": {"name": [NOME]}, "output": ["sysmapid"]}):
    call("map.delete", [antigo["sysmapid"]])
mapa = call("map.create", {"name": NOME, "width": 1210, "height": 640, "highlight": 1, "expandproblem": 1,
                           "markelements": 1, "show_unack": 0, "label_type": 0, "label_location": 0,
                           "selements": selements, "links": links, "shapes": shapes})["sysmapids"][0]
print(f"[ok] mapa criado (id {mapa})")
