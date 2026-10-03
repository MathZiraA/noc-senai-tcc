"""Encerra a manutenção 'Montagem da bancada - TCC' assim que fibra ou rádio responderem.
Roda via cron a cada minuto; depois de encerrar, não faz mais nada."""
import sys
import time
from zbx import call

MAINT = "Montagem da bancada - TCC"
dry = "--teste" in sys.argv

m = call("maintenance.get", {"filter": {"name": [MAINT]}, "output": ["maintenanceid", "active_since", "active_till"]})
now = int(time.time())
if not m or int(m[0]["active_till"]) <= now:
    sys.exit(0)

links = call("item.get", {"host": "R-FILIAL", "search": {"name": "estado"}, "output": ["name", "lastvalue"]})
up = [i["name"] for i in links if i["lastvalue"] == "1"]
print(f"links UP: {up or 'nenhum'}")
if up and not dry:
    call("maintenance.update", {"maintenanceid": m[0]["maintenanceid"], "active_till": now})
    print("manutenção encerrada: alertas por e-mail ativos")
