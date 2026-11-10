"""Cria o host NOC-SERVIDOR no Zabbix: o servidor passa a se auto-monitorar (Fase 1).

Coleta a saúde (CPU, RAM, disco, carga) e os sinais de ataque (conexões TCP, SYN_RECV,
workers do Apache, banimentos do fail2ban, falhas de SSH e descartes do firewall) pelo
próprio zabbix-agent2 em 127.0.0.1, com gatilhos que avisam quando algo parece um ataque.

Pré-requisitos no servidor (ver infra/servidor/monitoramento/aplicar-monitoramento.sh):
  - /usr/local/bin/noc-metricas.sh + UserParameter noc.srv[*] no zabbix-agent2
  - mod_status do Apache em 127.0.0.1 e as regras de sudo das métricas

Uso, no servidor:  python3 monitorar_servidor.py   (token em /root/.zabbix_token)
Roda de novo sem duplicar: se o host já existir, apenas avisa e sai.
"""
import json
import ssl
import urllib.request

URL = "https://127.0.0.1/zabbix/api_jsonrpc.php"
TOKEN = open("/root/.zabbix_token").read().strip()
CTX = ssl._create_unverified_context()

HOST = "NOC-SERVIDOR"
GRUPO = "Rede SENAI - Equipamentos"   # mesmo grupo do R-FILIAL/R-MATRIZ: o e-mail e o Analista IA já o cobrem

# Limites de alerta — ajustáveis por macro no host, sem mexer no código.
MACROS = {
    "{$NOC_SYN_MAX}": "200",        # conexões SYN_RECV (meia-abertas): acima disso = possível SYN flood
    "{$NOC_HTTP_MAX}": "500",       # conexões estabelecidas em 80/443
    "{$NOC_TOPTALKER_MAX}": "100",  # conexões vindas de um único IP
    "{$NOC_APACHE_MAX}": "150",     # MaxRequestWorkers do Apache (prefork padrão)
    "{$NOC_APACHE_PCT}": "90",      # % dos workers ocupados que dispara "saturado"
    "{$NOC_CPU_MAX}": "90",         # % de CPU
    "{$NOC_LOAD_MAX}": "4",         # carga média de 1 min
    "{$NOC_RAM_MAX}": "90",         # % de RAM usada
    "{$NOC_DISK_MAX}": "90",        # % do disco / usado
    "{$NOC_SSHFAIL_MAX}": "20",     # falhas de SSH por minuto
    "{$NOC_DROPS_MAX}": "50",       # pacotes/s descartados pelo firewall
}


def api(metodo, params):
    req = urllib.request.Request(URL, json.dumps({"jsonrpc": "2.0", "method": metodo, "params": params, "id": 1}).encode(),
                                 {"Content-Type": "application/json-rpc", "Authorization": f"Bearer {TOKEN}"})
    r = json.load(urllib.request.urlopen(req, context=CTX))
    if "error" in r:
        raise SystemExit(f"{metodo}: {r['error']}")
    return r["result"]


if api("host.get", {"filter": {"host": HOST}}):
    raise SystemExit(f"{HOST} já existe no Zabbix")

grupo = api("hostgroup.get", {"filter": {"name": GRUPO}})
groupid = grupo[0]["groupid"] if grupo else api("hostgroup.create", {"name": GRUPO})["groupids"][0]

hostid = api("host.create", {
    "host": HOST, "name": "NOC-SERVIDOR (Zabbix + SennaGuard)",
    "groups": [{"groupid": groupid}],
    "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": "127.0.0.1", "dns": "", "port": "10050"}],
    "macros": [{"macro": k, "value": v} for k, v in MACROS.items()],
    "tags": [{"tag": "local", "value": "Matriz"}, {"tag": "papel", "value": "servidor"}],
})["hostids"][0]
ifid = api("hostinterface.get", {"hostids": hostid})[0]["interfaceid"]

POR_SEG = [{"type": 10, "params": "", "error_handler": 0, "error_handler_params": ""}]       # mudança por segundo

TAG_SEG = [{"tag": "scope", "value": "seguranca"}]
TAG_SAU = [{"tag": "scope", "value": "saude"}]

# value_type: 0 = float, 1 = char, 3 = inteiro sem sinal, 4 = texto
itens = [
    # Saúde do servidor
    {"name": "CPU utilizada", "key_": "system.cpu.util", "value_type": 0, "units": "%", "delay": "30s", "tags": TAG_SAU},
    {"name": "Carga média (1 min)", "key_": "system.cpu.load[all,avg1]", "value_type": 0, "delay": "30s", "tags": TAG_SAU},
    {"name": "RAM usada", "key_": "vm.memory.size[pused]", "value_type": 0, "units": "%", "delay": "1m", "tags": TAG_SAU},
    {"name": "Swap usada", "key_": "system.swap.size[,pused]", "value_type": 0, "units": "%", "delay": "1m", "tags": TAG_SAU},
    {"name": "Disco / usado", "key_": "vfs.fs.size[/,pused]", "value_type": 0, "units": "%", "delay": "5m", "tags": TAG_SAU},
    {"name": "Tempo ligado", "key_": "system.uptime", "value_type": 3, "units": "uptime", "delay": "5m", "tags": TAG_SAU},
    # Sinais de ataque (coletor noc-metricas.sh)
    {"name": "Conexões estabelecidas", "key_": "noc.srv[estab]", "value_type": 3, "delay": "30s", "tags": TAG_SEG},
    {"name": "Conexões SYN_RECV (meia-abertas)", "key_": "noc.srv[synrecv]", "value_type": 3, "delay": "30s", "tags": TAG_SEG},
    {"name": "Conexões TIME_WAIT", "key_": "noc.srv[timewait]", "value_type": 3, "delay": "30s", "tags": TAG_SEG},
    {"name": "Conexões no site (80/443)", "key_": "noc.srv[http]", "value_type": 3, "delay": "30s", "tags": TAG_SEG},
    {"name": "Conexões do IP mais frequente", "key_": "noc.srv[toptalker]", "value_type": 3, "delay": "30s", "tags": TAG_SEG},
    {"name": "IP mais frequente", "key_": "noc.srv[toptalker_ip]", "value_type": 1, "delay": "30s", "trends": "0", "tags": TAG_SEG},
    {"name": "Apache: workers ocupados", "key_": "noc.srv[apache_busy]", "value_type": 3, "delay": "30s", "tags": TAG_SEG},
    {"name": "Apache: workers livres", "key_": "noc.srv[apache_idle]", "value_type": 3, "delay": "30s", "tags": TAG_SEG},
    {"name": "Apache: requisições por segundo", "key_": "noc.srv[apache_rps]", "value_type": 0, "delay": "30s", "tags": TAG_SEG},
    {"name": "fail2ban: IPs banidos agora", "key_": "noc.srv[fail2ban]", "value_type": 3, "delay": "1m", "tags": TAG_SEG},
    {"name": "SSH: falhas de login (último minuto)", "key_": "noc.srv[ssh_fail]", "value_type": 3, "delay": "1m", "tags": TAG_SEG},
    {"name": "Firewall: pacotes descartados por segundo", "key_": "noc.srv[nft_drops]", "value_type": 0, "units": "pps",
     "delay": "1m", "preprocessing": POR_SEG, "tags": TAG_SEG},
]
for i in itens:
    i["type"] = 0            # Zabbix agent (passivo)
    i["interfaceid"] = ifid
    i["hostid"] = hostid
api("item.create", itens)

H = HOST
gatilhos = [
    # Ataques de rede / web
    {"description": "Possível SYN flood: conexões SYN_RECV acima do normal", "priority": 4,
     "expression": f"min(/{H}/noc.srv[synrecv],1m)>{{$NOC_SYN_MAX}}", "tags": TAG_SEG},
    {"description": "Possível flood HTTP: muitas conexões no site (80/443)", "priority": 4,
     "expression": f"min(/{H}/noc.srv[http],1m)>{{$NOC_HTTP_MAX}}", "tags": TAG_SEG},
    {"description": "Flood de origem única: um IP concentra muitas conexões", "priority": 4,
     "expression": f"min(/{H}/noc.srv[toptalker],1m)>{{$NOC_TOPTALKER_MAX}}", "tags": TAG_SEG},
    {"description": "Apache saturado: workers ocupados perto do limite", "priority": 4,
     "expression": f"min(/{H}/noc.srv[apache_busy],1m)>{{$NOC_APACHE_MAX}}*{{$NOC_APACHE_PCT}}/100", "tags": TAG_SEG},
    {"description": "Firewall descartando muito tráfego (varredura ou flood)", "priority": 2,
     "expression": f"min(/{H}/noc.srv[nft_drops],2m)>{{$NOC_DROPS_MAX}}", "tags": TAG_SEG},
    {"description": "SSH sob força bruta: muitas falhas de login por minuto", "priority": 3,
     "expression": f"min(/{H}/noc.srv[ssh_fail],3m)>{{$NOC_SSHFAIL_MAX}}", "tags": TAG_SEG},
    # Saúde / esgotamento de recursos (consequência comum de um ataque)
    {"description": "CPU alta por 5 min", "priority": 3,
     "expression": f"min(/{H}/system.cpu.util,5m)>{{$NOC_CPU_MAX}}", "tags": TAG_SAU},
    {"description": "Carga do servidor alta por 5 min", "priority": 3,
     "expression": f"min(/{H}/system.cpu.load[all,avg1],5m)>{{$NOC_LOAD_MAX}}", "tags": TAG_SAU},
    {"description": "RAM alta por 5 min", "priority": 3,
     "expression": f"min(/{H}/vm.memory.size[pused],5m)>{{$NOC_RAM_MAX}}", "tags": TAG_SAU},
    {"description": "Disco / quase cheio", "priority": 4,
     "expression": f"last(/{H}/vfs.fs.size[/,pused])>{{$NOC_DISK_MAX}}", "tags": TAG_SAU},
    # Telemetria
    {"description": "NOC-SERVIDOR sem telemetria (agente fora)", "priority": 4,
     "expression": f"nodata(/{H}/system.cpu.util,3m)=1", "tags": TAG_SAU},
]
api("trigger.create", gatilhos)
print(f"{HOST} criado: hostid {hostid} · {len(itens)} itens · {len(gatilhos)} gatilhos")
