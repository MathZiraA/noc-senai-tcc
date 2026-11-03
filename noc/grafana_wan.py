"""Acrescenta ao painel "NOC – Redundância" do Grafana a linha dos links de internet do R-MATRIZ (VIVO e TIN).

Lê e grava o JSON provisionado (/var/lib/grafana/dashboards/noc-redundancia.json); guarde um .bak antes.
Uso, no servidor:  python3 grafana_wan.py && systemctl restart grafana-server
"""
import json

ARQ = "/var/lib/grafana/dashboards/noc-redundancia.json"
DS = {"type": "alexanderzobnin-zabbix-datasource", "uid": "zabbix-noc"}


def alvo(ref, item):
    return {"refId": ref, "datasource": DS, "queryType": "0", "group": {"filter": "Rede SENAI - Equipamentos"},
            "host": {"filter": "/^R-MATRIZ/"}, "itemTag": {"filter": ""}, "item": {"filter": item}, "functions": [],
            "options": {"showDisabledItems": False}}


def stat(pid, titulo, x, w, item, defaults):
    return {"id": pid, "type": "stat", "title": titulo, "datasource": DS, "gridPos": {"x": x, "y": 19, "w": w, "h": 5},
            "fieldConfig": {"defaults": defaults, "overrides": []}, "targets": [alvo("A", item)],
            "options": {"colorMode": "background", "graphMode": "none", "textMode": "value",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}


def faixa(de, ate, texto, cor, i):
    return {"type": "range", "options": {"from": de, "to": ate, "result": {"text": texto, "color": cor, "index": i}}}


def limiares(*passos):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in passos]}


UPDOWN = {"mappings": [faixa(0.5, 1.5, "UP", "green", 0), faixa(-0.5, 0.5, "DOWN", "red", 1)],
          "color": {"mode": "thresholds"}, "thresholds": limiares((None, "red"), (0.5, "green"))}
LAT = {"unit": "s", "decimals": 1, "color": {"mode": "thresholds"},
       "thresholds": limiares((None, "green"), (0.05, "orange"), (0.15, "red"))}

d = json.load(open(ARQ, encoding="utf-8"))
d["panels"] = [p for p in d["panels"] if p["id"] < 10]  # roda de novo sem duplicar
for p in d["panels"]:
    if p["id"] == 9:  # problemas descem para abrir espaço
        p["gridPos"]["y"] = 32

d["panels"] += [
    stat(10, "INTERNET: LINK ATIVO", 0, 6, "/^Link de internet ativo/", {
        "mappings": [faixa(0.5, 1.5, "VIVO", "green", 0), faixa(1.5, 2.5, "TIN (backup)", "orange", 1),
                     faixa(-0.5, 0.5, "SEM INTERNET", "red", 2)],
        "color": {"mode": "thresholds"}, "thresholds": limiares((None, "red"), (0.5, "green"), (1.5, "orange"))}),
    stat(11, "LINK VIVO (principal)", 6, 5, "/^LINK VIVO: internet/", UPDOWN),
    stat(12, "LINK TIN (backup)", 11, 5, "/^LINK TIN: internet/", UPDOWN),
    stat(13, "Latência VIVO", 16, 4, "/^LINK VIVO: latência/", LAT),
    stat(14, "Latência TIN", 20, 4, "/^LINK TIN: latência/", LAT),
    {"id": 15, "type": "timeseries", "title": "Download por link de internet: no failover ele sai da VIVO (ether2) e vai para o TIN (ether4)",
     "datasource": DS, "gridPos": {"x": 0, "y": 24, "w": 24, "h": 8},
     "fieldConfig": {"defaults": {"unit": "bps", "custom": {"fillOpacity": 15, "lineWidth": 2}}, "overrides": []},
     "targets": [alvo("A", "/ether2.*Bits received/"), alvo("B", "/ether4.*Bits received/")],
     "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}},
]
json.dump(d, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("painel atualizado:", len(d["panels"]), "painéis")
