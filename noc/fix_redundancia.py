"""Monitoramento de redundância do R-FILIAL: grupo, host, itens, triggers e manutenção (idempotente).
Os endereços vêm de /etc/noc/noc.conf (config.py)."""
import time

import config
from config import (HOST, K_CAMINHO, K_FAILOVER, K_FIBRA, K_LAN, K_LAT_FIBRA, K_LAT_RADIO, K_LOOPBACK,
                    K_PERDA_FIBRA, K_PERDA_RADIO, K_RADIO, PORTA_FIBRA_CURTA, PORTA_RADIO_CURTA)
from zbx import call

LAN_IP = config.LAN_FILIAL
# Revisão CTI: o R-FILIAL é monitorado pela loopback /32, alcançável pela fibra OU pelo rádio
MON_IP = config.LOOPBACK_FILIAL

# 0. Grupo e host (num servidor novo ainda não existem)
g = call("hostgroup.get", {"filter": {"name": [config.GRUPO]}, "output": ["groupid"]})
grupo_id = g[0]["groupid"] if g else call("hostgroup.create", {"name": config.GRUPO})["groupids"][0]
if not call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid"]}):
    call("host.create", {
        "host": HOST, "name": config.C["NOME_FILIAL"], "groups": [{"groupid": grupo_id}],
        "interfaces": [{"type": 2, "main": 1, "useip": 1, "ip": MON_IP, "dns": "", "port": "161",
                        "details": {"version": 2, "bulk": 1, "community": "{$SNMP_COMMUNITY}"}}],
        "macros": [{"macro": "{$SNMP_COMMUNITY}", "value": config.C["SNMP_COMMUNITY"]}]})
print(f"[ok] grupo '{config.GRUPO}' e host '{HOST}'")

h = call("host.get", {"filter": {"host": [HOST]}, "selectInterfaces": ["interfaceid", "ip"],
                      "selectParentTemplates": ["templateid", "host"], "selectGroups": ["groupid"]})[0]
hid, iface = h["hostid"], h["interfaces"][0]

# 1. Monitorar pela loopback (anunciada no OSPF: responde enquanto houver fibra OU rádio)
if iface["ip"] != MON_IP:
    call("hostinterface.update", {"interfaceid": iface["interfaceid"], "ip": MON_IP})
print(f"[ok] interface SNMP/ICMP -> loopback {MON_IP}")

# Limites de qualidade como macros do host (ajustáveis no Zabbix sem mexer nos triggers)
macros = {"{$FIBRA_LAT_MAX}": str(float(config.C["FIBRA_LAT_MAX_MS"]) / 1000),
          "{$FIBRA_PERDA_MAX}": config.C["FIBRA_PERDA_MAX"]}
atuais = {m["macro"]: m for m in call("usermacro.get", {"hostids": hid, "output": ["hostmacroid", "macro", "value"]})}
for nome_macro, valor in macros.items():
    if nome_macro not in atuais:
        call("usermacro.create", {"hostid": hid, "macro": nome_macro, "value": valor})
    elif atuais[nome_macro]["value"] != valor:
        call("usermacro.update", {"hostmacroid": atuais[nome_macro]["hostmacroid"], "value": valor})
print(f"[ok] limites: fibra degradada acima de {config.C['FIBRA_LAT_MAX_MS']} ms ou {config.C['FIBRA_PERDA_MAX']}% de perda")

# 2. Vincular o template MikroTik genérico
tpl = call("template.get", {"filter": {"host": ["Mikrotik by SNMP"]}, "output": ["templateid"]})[0]
linked = [t["templateid"] for t in h["parentTemplates"]]
if tpl["templateid"] not in linked:
    # O template MikroTik já inclui ping ICMP: substitui o 'ICMP Ping' avulso
    icmp = [t["templateid"] for t in h["parentTemplates"] if t["host"] == "ICMP Ping"]
    keep = [t for t in linked if t not in icmp]
    call("host.update", {"hostid": hid, "templates": [{"templateid": t} for t in keep + [tpl["templateid"]]],
                         "templates_clear": [{"templateid": t} for t in icmp]})
print("[ok] template 'Mikrotik by SNMP' vinculado (substituiu 'ICMP Ping')")

# 3. Desativar a ação duplicada sem filtro
for a in call("action.get", {"filter": {"name": ["Notificação de Redundância - Link Fibra/Rádio"]}, "output": ["actionid", "status"]}):
    if a["status"] == "0":
        call("action.update", {"actionid": a["actionid"], "status": 1})
print("[ok] ação duplicada desativada")

# 4. Value map + itens de enlace (independem da descoberta SNMP)
vm = call("valuemap.get", {"hostids": hid, "filter": {"name": ["Estado do Enlace"]}, "output": ["valuemapid"]})
vmid = vm[0]["valuemapid"] if vm else call("valuemap.create", {
    "hostid": hid, "name": "Estado do Enlace",
    "mappings": [{"value": "0", "newvalue": "DOWN"}, {"value": "1", "newvalue": "UP"}]})["valuemapids"][0]

items = [
    (K_FIBRA, f"Enlace FIBRA - estado ({HOST} {PORTA_FIBRA_CURTA})", 3, "", vmid, "fibra"),
    (K_RADIO, f"Enlace RÁDIO - estado ({HOST} {PORTA_RADIO_CURTA})", 3, "", vmid, "radio"),
    (K_LAT_FIBRA, "Enlace FIBRA - latência", 0, "s", "0", "fibra"),
    (K_LAT_RADIO, "Enlace RÁDIO - latência", 0, "s", "0", "radio"),
    (K_LOOPBACK, f"Alcance loopback {HOST} (fibra OU rádio)", 3, "", vmid, "loopback"),
]
existentes = {i["key_"]: i for i in call("item.get", {"hostids": hid, "output": ["itemid", "key_", "name"]})}
existing = set(existentes)
for key, name, vtype, units, vmap, enlace in items:
    if key in existing:
        if existentes[key]["name"] != name:  # ex.: porta do rádio mudou de ether3 para ether1
            call("item.update", {"itemid": existentes[key]["itemid"], "name": name})
        continue
    call("item.create", {"hostid": hid, "interfaceid": iface["interfaceid"], "type": 3, "key_": key,
                         "name": name, "value_type": vtype, "units": units, "valuemapid": vmap,
                         "delay": "10s", "history": "90d", "trends": "365d",
                         "tags": [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": enlace}]})
print("[ok] itens de estado/latência dos enlaces (coleta a cada 10s)")

# 4b. Caminho ativo calculado: fibra*2 + rádio -> 3/2 = FIBRA, 1 = RÁDIO, 0 = ISOLADA
if K_CAMINHO not in existing:
    vm = call("valuemap.get", {"hostids": hid, "filter": {"name": ["Caminho Ativo"]}, "output": ["valuemapid"]})
    vm_caminho = vm[0]["valuemapid"] if vm else call("valuemap.create", {
        "hostid": hid, "name": "Caminho Ativo",
        "mappings": [{"value": "0", "newvalue": "FILIAL ISOLADA"}, {"value": "1", "newvalue": "RÁDIO (failover)"},
                     {"value": "2", "newvalue": "FIBRA"}, {"value": "3", "newvalue": "FIBRA"}]})["valuemapids"][0]
    call("item.create", {"hostid": hid, "type": 15, "key_": K_CAMINHO, "name": "Caminho ativo Matriz-Filial",
                         "value_type": 3, "delay": "10s", "history": "90d", "trends": "365d",
                         "params": f"last(//{K_FIBRA})*2+last(//{K_RADIO})", "valuemapid": vm_caminho,
                         "description": "3 ou 2 = tráfego pela fibra, 1 = pelo rádio (failover), 0 = Filial isolada",
                         "tags": [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": "caminho"}]})
print("[ok] item calculado 'Caminho ativo Matriz-Filial'")

# 4c. Alcance da LAN da Filial a cada 1 s: a falha contínua durante uma troca de enlace = tempo de failover
#     Perda de pacotes por enlace: base da previsão de degradação do rádio
extras = [
    (K_LAN, "Alcance LAN Filial (1s)", 3, "", vmid, "1s", "30d", "lan"),
    (K_PERDA_FIBRA, "Enlace FIBRA - perda de pacotes", 0, "%", "0", "10s", "90d", "fibra"),
    (K_PERDA_RADIO, "Enlace RÁDIO - perda de pacotes", 0, "%", "0", "10s", "90d", "radio"),
]
for key, name, vtype, units, vmap, delay, hist, enlace in extras:
    if key in existing:
        continue
    call("item.create", {"hostid": hid, "interfaceid": iface["interfaceid"], "type": 3, "key_": key,
                         "name": name, "value_type": vtype, "units": units, "valuemapid": vmap,
                         "delay": delay, "history": hist, "trends": "365d",
                         "tags": [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": enlace}]})
print("[ok] alcance da LAN a cada 1s e perda de pacotes por enlace")

# 4d. Último tempo de failover medido (preenchido por failover_registro.py via history.push)
if K_FAILOVER not in existing:
    call("item.create", {"hostid": hid, "type": 2, "key_": K_FAILOVER,
                         "name": "Tempo de failover medido", "value_type": 3, "units": "s",
                         "history": "365d", "trends": "365d",
                         "description": "Segundos que a LAN da Filial ficou sem resposta em cada queda da fibra",
                         "tags": [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": "failover"}]})
print("[ok] item 'Tempo de failover medido'")

# 5. Triggers de redundância
f_down = f"max(/{HOST}/{K_FIBRA},#2)=0"
r_down = f"max(/{HOST}/{K_RADIO},#2)=0"
f_up = f"last(/{HOST}/{K_FIBRA})=1"
r_up = f"last(/{HOST}/{K_RADIO})=1"
triggers = [
    ("FILIAL ISOLADA: Fibra e Rádio indisponíveis", f"{f_down} and {r_down}", 5,
     "Os dois enlaces estão fora. A Filial está sem comunicação com a Matriz."),
    ("Link FIBRA caiu: failover para RÁDIO ativo", f"{f_down} and {r_up}", 4,
     "Enlace principal fora. O tráfego está sendo roteado pelo backup (OSPF custo 100)."),
    ("Link RÁDIO (backup) caiu: rede sem redundância", f"{r_down} and {f_up}", 3,
     "Fibra operando, mas não há caminho de backup caso ela caia."),
    ("Link FIBRA instável: 3+ quedas na última hora", f"changecount(/{HOST}/{K_FIBRA},1h)>=6", 2,
     "A fibra está oscilando, o que costuma indicar problema físico (conector/cordão óptico)."),
    ("Latência alta no RÁDIO (>50ms por 5min)", f"min(/{HOST}/{K_LAT_RADIO},5m)>0.05", 2,
     "Possível degradação do enlace de rádio (interferência/alinhamento)."),
    # Previsão: avisa ANTES da queda, enquanto o rádio ainda responde
    ("PREVISÃO: latência do RÁDIO deve passar de 50ms em 30min",
     f"{r_up} and min(/{HOST}/{K_LAT_RADIO},5m)<=0.05 and forecast(/{HOST}/{K_LAT_RADIO},1h,30m)>0.05", 2,
     "Tendência linear da última hora aponta degradação do rádio. Verificar alinhamento, interferência e "
     "obstáculos antes que o backup falhe."),
    ("RÁDIO acima do normal: latência 2x maior que a média de 24h",
     f"{r_up} and avg(/{HOST}/{K_LAT_RADIO},24h)>0.0005 and "
     f"avg(/{HOST}/{K_LAT_RADIO},15m)>2*avg(/{HOST}/{K_LAT_RADIO},24h)", 2,
     "O rádio está respondendo bem pior que o seu próprio normal, mesmo sem passar do limite fixo."),
    ("RÁDIO com perda de pacotes (>5% por 5min)", f"{r_up} and min(/{HOST}/{K_PERDA_RADIO},5m)>5", 3,
     "O rádio responde, mas perde pacotes: sinal fraco ou interferência. Costuma anteceder a queda."),
    ("Filial sem comunicação há mais de 10s (failover lento ou queda)", f"max(/{HOST}/{K_LAN},10s)=0", 3,
     f"A LAN da Filial ({LAN_IP}) não responde há 10 s. Num failover saudável o OSPF troca de "
     "enlace antes disso."),
    # Revisão CTI: fibra com problema mesmo SEM cair (lenta, perdendo pacotes ou piorando)
    ("FIBRA degradada: latência acima do limite por 5min", f"{f_up} and min(/{HOST}/{K_LAT_FIBRA},5m)>{{$FIBRA_LAT_MAX}}", 3,
     "A fibra responde, mas está lenta. O MikroTik desvia o tráfego para o rádio sozinho quando a média passa "
     "de 30 ms ou a perda passa de 10% (netwatch 'qualidade da fibra'). Verificar atenuação, conectores e a operadora."),
    ("FIBRA com perda de pacotes acima do limite por 5min",
     f"{f_up} and min(/{HOST}/{K_PERDA_FIBRA},5m)>{{$FIBRA_PERDA_MAX}}", 3,
     "A fibra responde, mas perde pacotes: interferência, atenuação ou problema no transceptor."),
    ("FIBRA acima do normal: latência 2x maior que a média de 24h",
     f"{f_up} and avg(/{HOST}/{K_LAT_FIBRA},24h)>0.0002 and "
     f"avg(/{HOST}/{K_LAT_FIBRA},15m)>2*avg(/{HOST}/{K_LAT_FIBRA},24h)", 2,
     "A fibra está bem pior que o seu próprio normal, mesmo sem passar do limite fixo."),
    ("PREVISÃO: latência da FIBRA deve passar do limite em 30min",
     f"{f_up} and min(/{HOST}/{K_LAT_FIBRA},5m)<={{$FIBRA_LAT_MAX}} and "
     f"forecast(/{HOST}/{K_LAT_FIBRA},1h,30m)>{{$FIBRA_LAT_MAX}}", 2,
     "A tendência da última hora indica que a fibra vai ficar degradada: agir antes que os usuários sintam."),
]
# Quedas que viram chamado com e-mail ao cliente se durarem mais que CHAMADO_APOS (setup_chamados.py)
GERAM_CHAMADO = ("FILIAL ISOLADA", "Link FIBRA caiu", "Link RÁDIO (backup) caiu")
atuais_t = {t["description"]: t for t in call("trigger.get", {"hostids": hid, "inherited": False,
                                                               "output": ["triggerid", "description"],
                                                               "selectTags": ["tag", "value"]})}
for desc, expr, sev, comment in triggers:
    tags = [{"tag": "component", "value": "redundancia"}]
    if desc.startswith(GERAM_CHAMADO):
        tags.append({"tag": "chamado", "value": "sim"})
    if desc not in atuais_t:
        call("trigger.create", {"description": desc, "expression": expr, "priority": sev, "comments": comment,
                                "manual_close": 0, "tags": tags})
    elif sorted((t["tag"], t["value"]) for t in atuais_t[desc]["tags"]) != sorted((t["tag"], t["value"]) for t in tags):
        call("trigger.update", {"triggerid": atuais_t[desc]["triggerid"], "tags": tags})
print(f"[ok] {len(triggers)} triggers de redundância e qualidade (quedas marcadas com chamado=sim)")

# 5b. Antenas do rádio como hosts próprios: separa "antena com defeito" de "roteador com defeito"
tpl_icmp = call("template.get", {"filter": {"host": ["ICMP Ping"]}, "output": ["templateid"]})[0]["templateid"]
antenas = []
for nome, ip, visivel in (("RADIO-P2P-MATRIZ", config.C["ANTENA_MATRIZ"], "Rádio P2P Matriz (AP)"),
                          ("RADIO-P2P-FILIAL", config.C["ANTENA_FILIAL"], "Rádio P2P Filial (Station)")):
    a = call("host.get", {"filter": {"host": [nome]}, "output": ["hostid"]})
    if a:
        antenas.append(a[0]["hostid"])
        continue
    antenas.append(call("host.create", {
        "host": nome, "name": visivel, "groups": [{"groupid": grupo_id}], "templates": [{"templateid": tpl_icmp}],
        "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": ip, "dns": "", "port": "10050"}],
        "macros": [{"macro": "{$RADIO_SINAL_MIN}", "value": config.C["RADIO_SINAL_MIN_DBM"],
                    "description": "Sinal adequado: entre -60 e -50 dBm (leitura depende do fabricante, ver documentação)"}],
        "description": "Antena do enlace de backup. Ping, perda e latência; sinal em dBm depende do modelo do rádio.",
        "tags": [{"tag": "component", "value": "radio"}]})["hostids"][0])
print("[ok] antenas RADIO-P2P-MATRIZ e RADIO-P2P-FILIAL monitoradas por ping")

# 6. Manutenção até a bancada ficar pronta (coleta continua, e-mails suprimidos)
NOME_MANUT = "Montagem da bancada - TCC"
manut = call("maintenance.get", {"filter": {"name": [NOME_MANUT]}, "selectHosts": ["hostid"],
                                 "output": ["maintenanceid", "active_till"]})
if not manut:
    now = int(time.time())
    call("maintenance.create", {
        "name": NOME_MANUT, "maintenance_type": 0,
        "active_since": now, "active_till": now + 90 * 86400,
        "description": "Rede física ainda não montada. Encerra sozinha quando um enlace responder.",
        "hosts": [{"hostid": h} for h in [hid] + antenas],
        "timeperiods": [{"timeperiod_type": 0, "start_date": now, "period": 90 * 86400}]})
elif int(manut[0]["active_till"]) > time.time():
    hosts_manut = {h["hostid"] for h in manut[0]["hosts"]}
    if not set([hid] + antenas) <= hosts_manut:
        call("maintenance.update", {"maintenanceid": manut[0]["maintenanceid"],
                                    "hosts": [{"hostid": h} for h in hosts_manut | set([hid] + antenas)]})
print("[ok] hosts em manutenção (sem e-mails) até a bancada ficar pronta")
