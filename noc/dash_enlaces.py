"""Adiciona ao dashboard OFICIAL a faixa de estado dos enlaces Fibra/Rádio (idempotente)."""
from zbx import call

DASH = "NOC - Monitoramento de Redundância (OFICIAL)"
ROW_H = 5

d = call("dashboard.get", {"filter": {"name": [DASH]}, "selectPages": "extend"})[0]
page = d["pages"][0]
if any(w["name"].startswith("ENLACE") for w in page["widgets"]):
    print("[ok] faixa de enlaces já existe")
    raise SystemExit

hid = call("host.get", {"filter": {"host": ["R-FILIAL"]}, "output": ["hostid"]})[0]["hostid"]
items = {i["key_"]: i["itemid"] for i in call("item.get", {"hostids": hid, "search": {"key_": "icmpping"},
                                                             "output": ["key_"]})}

def status(name, key, x):
    return {"type": "item", "name": name, "x": x, "y": 0, "width": 18, "height": ROW_H, "view_mode": 0,
            "fields": [
                {"type": 4, "name": "itemid.0", "value": items[key]},
                {"type": 1, "name": "thresholds.0.color", "value": "E53935"},
                {"type": 1, "name": "thresholds.0.threshold", "value": "0"},
                {"type": 1, "name": "thresholds.1.color", "value": "43A047"},
                {"type": 1, "name": "thresholds.1.threshold", "value": "1"},
            ]}

graph = {"type": "svggraph", "name": "ENLACES - LATÊNCIA FIBRA x RÁDIO", "x": 36, "y": 0, "width": 36,
         "height": ROW_H, "fields": [
             {"type": 1, "name": "ds.0.hosts.0", "value": "R-FILIAL"},
             {"type": 1, "name": "ds.0.items.0", "value": "Enlace FIBRA - latência"},
             {"type": 1, "name": "ds.0.color", "value": "1E88E5"},
             {"type": 1, "name": "ds.1.hosts.0", "value": "R-FILIAL"},
             {"type": 1, "name": "ds.1.items.0", "value": "Enlace RÁDIO - latência"},
             {"type": 1, "name": "ds.1.color", "value": "FB8C00"},
         ]}

kept = []
for w in page["widgets"]:
    w = {k: w[k] for k in ("widgetid", "type", "name", "x", "y", "width", "height", "view_mode", "fields")}
    w["y"] = int(w["y"]) + ROW_H
    kept.append(w)

new = [status("ENLACE FIBRA (principal)", "icmpping[10.0.1.2,3,,,500]", 0),
       status("ENLACE RÁDIO (backup)", "icmpping[10.0.2.2,3,,,500]", 18), graph]
call("dashboard.update", {"dashboardid": d["dashboardid"],
                          "pages": [{"dashboard_pageid": page["dashboard_pageid"], "name": page["name"],
                                     "widgets": new + kept}]})
print("[ok] faixa de estado dos enlaces adicionada ao topo do dashboard")
