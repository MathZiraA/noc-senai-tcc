"""Cria no host "Zabbix server" o item que recebe o aviso do backup diário e o alerta se ele faltar (idempotente)."""
from zbx import call

HOST = "Zabbix server"
CHAVE = "noc.backup.mb"

h = call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid"]})[0]
if not call("item.get", {"hostids": h["hostid"], "filter": {"key_": CHAVE}, "output": ["itemid"]}):
    call("item.create", {"hostid": h["hostid"], "type": 2, "key_": CHAVE, "name": "Backup NOC - tamanho total",
                         "value_type": 3, "units": "MB", "history": "90d", "trends": "365d",
                         "description": "Enviado por backup_noc.sh ao fim de cada backup diário",
                         "tags": [{"tag": "component", "value": "backup"}]})
desc = "Backup diário do NOC não rodou nas últimas 26h"
if not call("trigger.get", {"hostids": h["hostid"], "filter": {"description": [desc]}, "output": ["triggerid"]}):
    call("trigger.create", {"description": desc, "priority": 3, "expression": f"nodata(/{HOST}/{CHAVE},26h)=1",
                            "comments": "Verifique /var/log/noc_backup.log e o espaço em disco da VM.",
                            "tags": [{"tag": "component", "value": "backup"}]})
print("[ok] item e alerta do backup no host 'Zabbix server'")
