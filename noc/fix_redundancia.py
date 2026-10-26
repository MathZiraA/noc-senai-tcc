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
                         "delay": "5s", "history": "90d", "trends": "365d",
                         "tags": [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": enlace}]})
print("[ok] itens de estado/latência dos enlaces (coleta a cada 5s)")

# 4b. Caminho ativo calculado: fibra*2 + rádio -> 3/2 = FIBRA, 1 = RÁDIO, 0 = ISOLADA
if K_CAMINHO not in existing:
    vm = call("valuemap.get", {"hostids": hid, "filter": {"name": ["Caminho Ativo"]}, "output": ["valuemapid"]})
    vm_caminho = vm[0]["valuemapid"] if vm else call("valuemap.create", {
        "hostid": hid, "name": "Caminho Ativo",
        "mappings": [{"value": "0", "newvalue": "FILIAL ISOLADA"}, {"value": "1", "newvalue": "RÁDIO (failover)"},
                     {"value": "2", "newvalue": "FIBRA"}, {"value": "3", "newvalue": "FIBRA"}]})["valuemapids"][0]
    call("item.create", {"hostid": hid, "type": 15, "key_": K_CAMINHO, "name": "Caminho ativo Matriz-Filial",
                         "value_type": 3, "delay": "5s", "history": "90d", "trends": "365d",
                         "params": f"last(//{K_FIBRA})*2+last(//{K_RADIO})", "valuemapid": vm_caminho,
                         "description": "3 ou 2 = tráfego pela fibra, 1 = pelo rádio (failover), 0 = Filial isolada",
                         "tags": [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": "caminho"}]})
print("[ok] item calculado 'Caminho ativo Matriz-Filial'")

# 4c. Alcance da LAN da Filial a cada 1 s: a falha contínua durante uma troca de enlace = tempo de failover
#     Perda de pacotes por enlace: base da previsão de degradação do rádio
extras = [
    (K_LAN, "Alcance LAN Filial (1s)", 3, "", vmid, "1s", "30d", "lan"),
    (K_PERDA_FIBRA, "Enlace FIBRA - perda de pacotes", 0, "%", "0", "5s", "90d", "fibra"),
    (K_PERDA_RADIO, "Enlace RÁDIO - perda de pacotes", 0, "%", "0", "5s", "90d", "radio"),
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

# 5b. Antenas do rádio como hosts próprios: separa "antena com defeito" de "roteador com defeito".
#     Ubiquiti PowerBeam M5 (airOS 6, XW): ping + SNMP do MIB UBNT-AirMAX (enterprise 41112), tabela ubntWlStat.
#     Pedido da CTI: sinal adequado entre -60 e -50 dBm.
tpl_icmp = call("template.get", {"filter": {"host": ["ICMP Ping"]}, "output": ["templateid"]})[0]["templateid"]
UBNT = "1.3.6.1.4.1.41112.1.4"
ITENS_ANTENA = [  # (chave, nome, OID, unidade, só na estação?)
    ("ubnt.sinal", "Rádio - sinal recebido", f"{UBNT}.5.1.5.1", "dBm", True),
    ("ubnt.ruido", "Rádio - ruído de fundo", f"{UBNT}.5.1.8.1", "dBm", False),
    ("ubnt.ccq", "Rádio - CCQ (qualidade da transmissão)", f"{UBNT}.5.1.7.1", "%", False),
    ("ubnt.estacoes", "Rádio - estações conectadas", f"{UBNT}.5.1.15.1", "", False),
    ("ubnt.airmax.qualidade", "Rádio - qualidade airMAX", f"{UBNT}.6.1.3.1", "%", False),
    ("ubnt.airmax.capacidade", "Rádio - capacidade airMAX", f"{UBNT}.6.1.4.1", "%", False),
]
MACROS_ANTENA = [
    ("{$RADIO_SINAL_MIN}", config.C["RADIO_SINAL_MIN_DBM"], "Abaixo disso: sinal fraco (CTI: adequado entre -60 e -50 dBm)"),
    ("{$RADIO_SINAL_CRIT}", config.C["RADIO_SINAL_CRIT_DBM"], "Abaixo disso: enlace instável"),
    ("{$RADIO_SINAL_SAT}", config.C["RADIO_SINAL_SAT_DBM"], "Acima disso: sinal forte demais, satura o receptor"),
    ("{$RADIO_CCQ_MIN}", config.C["RADIO_CCQ_MIN"], "Abaixo disso: muitas retransmissões"),
    ("{$SNMP_COMMUNITY}", config.C["SNMP_COMMUNITY"], "Comunidade SNMP configurada na aba SERVICES da antena"),
]
antenas = []
for nome, ip, visivel, estacao in (("RADIO-P2P-MATRIZ", config.C["ANTENA_MATRIZ"], "Rádio P2P Matriz (AP)", False),
                                   ("RADIO-P2P-FILIAL", config.C["ANTENA_FILIAL"], "Rádio P2P Filial (Station)", True)):
    a = call("host.get", {"filter": {"host": [nome]}, "output": ["hostid"],
                          "selectInterfaces": ["interfaceid", "type", "details"], "selectMacros": ["hostmacroid", "macro", "value"]})
    if a:
        aid = a[0]["hostid"]
    else:
        aid = call("host.create", {
            "host": nome, "name": visivel, "groups": [{"groupid": grupo_id}], "templates": [{"templateid": tpl_icmp}],
            "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": ip, "dns": "", "port": "10050"}],
            "description": "Antena Ubiquiti PowerBeam M5 do enlace de backup: ping e SNMP (sinal, ruído, CCQ, airMAX).",
            "tags": [{"tag": "component", "value": "radio"}]})["hostids"][0]
        a = call("host.get", {"hostids": aid, "output": ["hostid"], "selectInterfaces": ["interfaceid", "type", "details"],
                              "selectMacros": ["hostmacroid", "macro", "value"]})
    antenas.append(aid)
    # Interface SNMP (o protótipo criou as antenas só com ping)
    # O airOS 6 (XW) só responde SNMP v1: em v2c o agente fica mudo (testado em 20/10/2026)
    snmp = [i for i in a[0]["interfaces"] if i["type"] == "2"]
    detalhes = {"version": 1, "community": "{$SNMP_COMMUNITY}"}
    if not snmp:
        snmp_if = call("hostinterface.create", {"hostid": aid, "type": 2, "main": 1, "useip": 1, "ip": ip, "dns": "",
                                                "port": "161", "details": detalhes})["interfaceids"]
    else:
        snmp_if = [snmp[0]["interfaceid"]]
        if str(snmp[0].get("details", {}).get("version")) != "1":
            call("hostinterface.update", {"interfaceid": snmp_if[0], "details": detalhes})
    atuais_m = {m["macro"]: m for m in a[0]["macros"]}
    for macro, valor, desc in MACROS_ANTENA:
        if macro not in atuais_m:
            call("usermacro.create", {"hostid": aid, "macro": macro, "value": valor, "description": desc})
        elif atuais_m[macro]["value"] != valor:
            call("usermacro.update", {"hostmacroid": atuais_m[macro]["hostmacroid"], "value": valor})
    existentes = {i["key_"] for i in call("item.get", {"hostids": aid, "output": ["key_"]})}
    for chave, nome_item, oid, unid, so_estacao in ITENS_ANTENA:
        if (so_estacao and not estacao) or chave in existentes:
            continue
        call("item.create", {"hostid": aid, "interfaceid": snmp_if[0], "type": 20, "key_": chave, "name": nome_item,
                             "snmp_oid": oid, "value_type": 3 if unid in ("%", "") else 0, "units": unid,
                             "delay": "30s", "history": "90d", "trends": "365d",
                             "tags": [{"tag": "component", "value": "radio"}]})
    # Alertas: o sinal só existe na estação (a AP vê várias estações); a AP avisa quando ficar sem nenhuma
    if estacao:
        s = f"/{nome}/ubnt.sinal"
        regras = [
            ("Sinal do rádio fraco: abaixo de {$RADIO_SINAL_MIN} dBm por 5min",
             f"max({s},5m)<{{$RADIO_SINAL_MIN}} and last({s})<0", 2,
             "Fora da faixa pedida pela CTI (-60 a -50 dBm): conferir alinhamento, obstáculos e potência de saída."),
            ("Sinal do rádio crítico: abaixo de {$RADIO_SINAL_CRIT} dBm por 5min",
             f"max({s},5m)<{{$RADIO_SINAL_CRIT}} and last({s})<0", 3,
             "Com esse sinal o enlace perde pacotes e cai com chuva ou desalinhamento."),
            ("Sinal do rádio forte demais: acima de {$RADIO_SINAL_SAT} dBm por 10min",
             f"min({s},10m)>{{$RADIO_SINAL_SAT}} and last({s})<0", 1,
             "Receptor saturado (comum com antenas muito próximas): reduzir a potência de saída."),
            (f"CCQ do rádio baixo: abaixo de {{$RADIO_CCQ_MIN}}% por 10min",
             f"max(/{nome}/ubnt.ccq,10m)<{{$RADIO_CCQ_MIN}} and last(/{nome}/ubnt.ccq)>0", 2,
             "Muitas retransmissões no rádio: interferência ou sinal fora da faixa."),
        ]
    else:
        regras = [("Rádio sem estação conectada (enlace de backup desassociado)",
                   f"max(/{nome}/ubnt.estacoes,#3)=0", 3,
                   "A antena da Matriz está ligada, mas a da Filial não está conectada: o backup não existe agora.")]
    atuais_r = {t["description"] for t in call("trigger.get", {"hostids": aid, "inherited": False, "output": ["description"]})}
    for desc, expr, sev, comment in regras:
        if desc not in atuais_r:
            call("trigger.create", {"description": desc, "expression": expr, "priority": sev, "comments": comment,
                                    "tags": [{"tag": "component", "value": "radio"}]})
print("[ok] antenas RADIO-P2P-MATRIZ e RADIO-P2P-FILIAL: ping + SNMP (sinal, ruído, CCQ, airMAX) e alertas de sinal")

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
