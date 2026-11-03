"""Cadastra o R-MATRIZ no Zabbix (igual ao R-FILIAL) + monitoramento dos links de internet VIVO e TIN.

Os IPs de teste ficam presos a cada link no roteador (rotas /32 + blackhole, ver routeros/wan-redundancia.rsc):
1.0.0.1 só sai pela VIVO e 9.9.9.9 só pelo TIN. Pingando esses IPs do servidor, o Zabbix vê cada link
separado, e o link ativo segue a mesma regra do roteador (VIVO se responder, senão TIN).
Uso, no servidor:  python3 monitorar_matriz.py   (token em /root/.zabbix_token)
"""
import json
import ssl
import urllib.request

URL = "https://127.0.0.1/zabbix/api_jsonrpc.php"
TOKEN = open("/root/.zabbix_token").read().strip()
CTX = ssl._create_unverified_context()

LINKS = [("VIVO", "1.0.0.1", "ether2-INTERNET", 4), ("TIN", "9.9.9.9", "ether4-TIN", 3)]  # 4 = Alta, 3 = Média


def api(metodo, params):
    req = urllib.request.Request(URL, json.dumps({"jsonrpc": "2.0", "method": metodo, "params": params, "id": 1}).encode(),
                                 {"Content-Type": "application/json-rpc", "Authorization": f"Bearer {TOKEN}"})
    r = json.load(urllib.request.urlopen(req, context=CTX))
    if "error" in r:
        raise SystemExit(f"{metodo}: {r['error']}")
    return r["result"]


filial = api("host.get", {"filter": {"host": "R-FILIAL"}, "selectInterfaces": "extend", "selectMacros": "extend",
                          "selectParentTemplates": ["templateid"], "selectHostGroups": ["groupid"]})[0]
if api("host.get", {"filter": {"host": "R-MATRIZ"}}):
    raise SystemExit("R-MATRIZ já existe no Zabbix")

snmp = next(i for i in filial["interfaces"] if i["type"] == "2")
hostid = api("host.create", {
    "host": "R-MATRIZ", "name": "R-MATRIZ (RouterOS Matriz SENAI)",
    "groups": filial["hostgroups"], "templates": filial["parentTemplates"],
    "macros": [{"macro": m["macro"], "value": m["value"]} for m in filial["macros"] if m["type"] == "0"],
    "interfaces": [{"type": 2, "main": 1, "useip": 1, "ip": "192.168.10.1", "dns": "", "port": snmp["port"],
                    "details": snmp["details"]}],
    "tags": [{"tag": "local", "value": "Matriz"}],
})["hostids"][0]
ifid = api("hostinterface.get", {"hostids": hostid})[0]["interfaceid"]

vm = api("valuemap.create", {"hostid": hostid, "name": "Link de internet ativo", "mappings": [
    {"value": "0", "newvalue": "SEM INTERNET"}, {"value": "1", "newvalue": "VIVO"}, {"value": "2", "newvalue": "TIN"}]})["valuemapids"][0]
updown = api("valuemap.create", {"hostid": hostid, "name": "Link UP/DOWN", "mappings": [
    {"value": "0", "newvalue": "DOWN"}, {"value": "1", "newvalue": "UP"}]})["valuemapids"][0]

itens = []
for nome, ip, porta, _ in LINKS:
    tag = [{"tag": "link", "value": nome}]
    itens += [
        {"name": f"LINK {nome}: internet", "key_": f"icmpping[{ip},3,,,500]", "type": 3, "value_type": 3, "delay": "5s",
         "valuemapid": updown, "tags": tag},
        {"name": f"LINK {nome}: latência", "key_": f"icmppingsec[{ip},3,,,500]", "type": 3, "value_type": 0, "delay": "5s",
         "units": "s", "tags": tag},
        {"name": f"LINK {nome}: perda", "key_": f"icmppingloss[{ip},3,,,500]", "type": 3, "value_type": 0, "delay": "5s",
         "units": "%", "tags": tag},
    ]
itens.append({"name": "Link de internet ativo", "key_": "noc.wan_ativo", "type": 15, "value_type": 3, "delay": "5s",
              "valuemapid": vm, "tags": [{"tag": "link", "value": "WAN"}],
              "params": "last(//icmpping[1.0.0.1,3,,,500])+(1-last(//icmpping[1.0.0.1,3,,,500]))*last(//icmpping[9.9.9.9,3,,,500])*2"})
# IP (DHCP) de cada link: lido da tabela de endereços do roteador
itens.append({"name": "Tabela de IPs do roteador", "key_": "noc.ips", "type": 20, "value_type": 4, "delay": "5m",
              "interfaceid": ifid, "snmp_oid": "walk[1.3.6.1.2.1.4.20.1.2]", "history": "1d"})
for i in itens:
    if i["type"] != 15:
        i.setdefault("interfaceid", ifid)
    i["hostid"] = hostid
api("item.create", itens)

mestre = api("item.get", {"hostids": hostid, "filter": {"key_": "noc.ips"}})[0]["itemid"]
for nome, ip, porta, _ in LINKS:
    ifindex = {"ether2-INTERNET": 3, "ether4-TIN": 5}[porta]  # ifIndex SNMP das portas no R-MATRIZ
    js = ("var m = value.match(/1\\.3\\.6\\.1\\.2\\.1\\.4\\.20\\.1\\.2\\.([0-9.]+) = INTEGER: " + str(ifindex) + "\\b/);"
          " return m ? m[1] : 'sem IP';")
    api("item.create", {"hostid": hostid, "name": f"LINK {nome}: IP ({porta})", "key_": f"noc.ip.{nome.lower()}",
                        "type": 18, "master_itemid": mestre, "value_type": 1, "tags": [{"tag": "link", "value": nome}],
                        "preprocessing": [{"type": 21, "params": js, "error_handler": 0, "error_handler_params": ""},
                                          {"type": 20, "params": "1h", "error_handler": 0, "error_handler_params": ""}]})

H = "R-MATRIZ"
gatilhos = []
for nome, ip, porta, sev in LINKS:
    k = f"icmpping[{ip},3,,,500]"
    extra = ": internet pelo LINK TIN" if nome == "VIVO" else " (backup indisponível)"
    gatilhos.append({"description": f"LINK {nome} caiu{extra}", "priority": sev,
                     "expression": f"max(/{H}/{k},15s)=0", "recovery_mode": 1,
                     "recovery_expression": f"min(/{H}/{k},15s)=1",
                     "tags": [{"tag": "link", "value": nome}, {"tag": "scope", "value": "availability"}]})
gatilhos.append({"description": "SEM INTERNET: LINK VIVO e LINK TIN fora", "priority": 5,
                 "expression": f"max(/{H}/icmpping[1.0.0.1,3,,,500],15s)=0 and max(/{H}/icmpping[9.9.9.9,3,,,500],15s)=0",
                 "tags": [{"tag": "link", "value": "WAN"}]})
api("trigger.create", gatilhos)
print("R-MATRIZ cadastrado: hostid", hostid)
