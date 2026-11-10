"""Confere a bancada inteira a partir do servidor do NOC e diz o que falta, com a dica de correção.

Uso na VM/servidor:  cd /root/noc && /opt/noc-analista/bin/python validar_bancada.py
Testa: rede da Matriz, enlaces, antenas, LAN e PC da Filial, MTU 2000, SNMP, SSH de leitura, OSPF,
rota ativa e o que o Zabbix está vendo (caminho ativo, manutenção, disponibilidade SNMP).
"""
import subprocess

import config
from config import C
from zbx import call

VERDE, VERMELHO, AMARELO, FIM = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
resultado = {"ok": 0, "falha": 0}


def mostrar(ok, titulo, detalhe="", dica=""):
    resultado["ok" if ok else "falha"] += 1
    print(f"  {VERDE + '✓' if ok else VERMELHO + '✗'}{FIM} {titulo}" + (f" — {detalhe}" if detalhe else ""))
    if not ok and dica:
        print(f"      {AMARELO}dica: {dica}{FIM}")


def ping(ip, tamanho=None):
    cmd = ["ping", "-c", "2", "-W", "2", ip]
    if tamanho:
        cmd[1:1] = ["-M", "do", "-s", str(tamanho)]  # não fragmentar
    return subprocess.run(cmd, capture_output=True).returncode == 0


def ssh_mikrotik(comando):
    r = subprocess.run(["ssh", "-i", "/root/.ssh/id_ed25519_mikrotik", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
                        "-o", "StrictHostKeyChecking=accept-new", f"zabbix-ia@{C['LOOPBACK_FILIAL']}", comando],
                       capture_output=True, text=True, timeout=25)
    return r.returncode, (r.stdout + r.stderr).strip()


print("\n1. Rede da Matriz")
mostrar(ping(C["GW_MATRIZ"]), f"R-MATRIZ responde ({C['GW_MATRIZ']})",
        dica="cabo do servidor no SW-MATRIZ? VMnet0 preso à placa do cabo? R-MATRIZ configurado?")

print("\n2. Enlaces até a Filial")
fibra, radio = ping(C["FIBRA_FILIAL"]), ping(C["RADIO_FILIAL"])
mostrar(fibra, f"fibra: R-FILIAL responde em {C['FIBRA_FILIAL']}", dica="fibra/módulos SFP nas portas sfp1 dos dois roteadores")
mostrar(radio, f"rádio: R-FILIAL responde em {C['RADIO_FILIAL']}", dica="rádios associados? ether1 dos roteadores nos PoE?")
mostrar(ping(C["ANTENA_MATRIZ"]), f"antena da Matriz ({C['ANTENA_MATRIZ']})", dica="IP/gateway da antena (infra/bancada/saida/RADIOS.txt)")
mostrar(ping(C["ANTENA_FILIAL"]), f"antena da Filial ({C['ANTENA_FILIAL']})", dica="o enlace de rádio está associado?")

print("\n3. Filial")
mostrar(ping(C["LAN_FILIAL"]), f"LAN da Filial ({C['LAN_FILIAL']})", dica="OSPF não está trocando rotas (veja item 5)")
mostrar(ping(C["LOOPBACK_FILIAL"]), f"loopback do R-FILIAL ({C['LOOPBACK_FILIAL']}): monitoramento pelos dois links",
        dica="interface 'loopback' com o /32 e o interface-template passive no OSPF do R-FILIAL")
mostrar(ping("192.168.20.10"), "PC-FILIAL (192.168.20.10)", dica="rode infra/bancada/saida/pc-filial.ps1 no PC (como administrador)")

print("\n4. Acesso do NOC ao R-FILIAL")
snmp = subprocess.run(["snmpget", "-v2c", "-c", C["SNMP_COMMUNITY"], "-t", "3", "-r", "1", C["LAN_FILIAL"],
                       "1.3.6.1.2.1.1.5.0"], capture_output=True, text=True)
mostrar(snmp.returncode == 0, "SNMP responde", snmp.stdout.strip().split(" = ")[-1][:60],
        dica="colou o bloco do NOC no R-FILIAL? security=none? comunidade igual à do noc.conf?")
codigo, saida = ssh_mikrotik("/system identity print")
mostrar(codigo == 0, "SSH de leitura (usuário zabbix-ia)", saida.replace("name:", "").strip()[:40],
        dica="chave noc-analista.pub importada no usuário zabbix-ia? regra de firewall TCP 22 para o servidor?")

print("\n5. Roteamento (OSPF)")
if codigo == 0:
    _, vizinhos = ssh_mikrotik("/routing ospf neighbor print terse")
    completos = vizinhos.count("state=Full")
    mostrar(completos >= 2, f"vizinhos OSPF em Full: {completos} de 2",
            dica="com 1, só um enlace forma vizinhança: confira cabo/rádio e o 'type=ptp' nos dois lados")
    _, rota = ssh_mikrotik(f"/ip route print terse where dst-address={C['REDE_MATRIZ']} and active")
    pela_fibra = C["FIBRA_MATRIZ"] in rota
    mostrar(pela_fibra, "tráfego para a Matriz sai pela FIBRA (custo 10)",
            "via rádio" if C["RADIO_MATRIZ"] in rota else "",
            dica="custos OSPF: fibra 10, rádio 100 nos dois roteadores")
    # MTU 2000 entre os roteadores (o caminho que importa; a placa do servidor pode ficar em 1500)
    _, mtu = ssh_mikrotik(f"/ping {C['GW_MATRIZ']} size=2000 do-not-fragment count=3")
    mostrar("packet-loss=0%" in mtu.replace(" ", ""), "MTU 2000 sem fragmentar entre R-FILIAL e R-MATRIZ",
            dica="mtu=2000 nas ether1-5 e na bridge-LAN dos dois roteadores (e no rádio, se o tráfego estiver nele)")
    # Troca por qualidade: netwatch da fibra precisa estar "up" e o custo da fibra em 10
    _, nw = ssh_mikrotik('/tool netwatch print terse where comment~"qualidade"')
    mostrar("status=up" in nw, "netwatch de qualidade da fibra ativo e OK",
            "fibra degradada: tráfego desviado ao rádio" if "status=down" in nw else "",
            dica="RouterOS 7.4+? bloco 11 do script do roteador aplicado? (/tool netwatch print)")
    _, custos = ssh_mikrotik('/routing ospf interface-template print terse where comment~"PAP Fibra"')
    mostrar("cost=10" in custos.replace(" ", ""), "custo OSPF da fibra = 10 (fibra preferida)",
            "custo 200: fibra desviada por qualidade" if "cost=200" in custos.replace(" ", "") else "",
            dica="se a fibra está boa e o custo continua 200, rode o up-script do netwatch ou reaplique o custo 10")
else:
    mostrar(False, "OSPF não verificado", "sem SSH no R-FILIAL", dica="resolva o item 4 primeiro")

print("\n6. O que o Zabbix está vendo")
h = call("host.get", {"filter": {"host": [config.HOST]}, "output": ["hostid", "maintenance_status"],
                      "selectInterfaces": ["available"]})[0]
caminho = call("item.get", {"hostids": h["hostid"], "filter": {"key_": config.K_CAMINHO}, "output": ["lastvalue"]})[0]
nomes = {"0": "FILIAL ISOLADA", "1": "RÁDIO (failover)", "2": "FIBRA", "3": "FIBRA"}
mostrar(caminho["lastvalue"] in ("2", "3"), "caminho ativo no Zabbix", nomes.get(caminho["lastvalue"], "?"),
        dica="aguarde 30 s após a rede subir; se persistir, veja os itens 2 e 3")
mostrar(h["interfaces"][0]["available"] == "1", "Zabbix coletando o R-FILIAL por SNMP",
        dica="pode levar alguns minutos depois que o SNMP responde (item 4)")
mostrar(h["maintenance_status"] == "0", "manutenção da bancada encerrada (alertas por e-mail ativos)",
        dica="encerra sozinha 1 minuto depois que a fibra ou o rádio respondem")

total = resultado["ok"] + resultado["falha"]
cor = VERDE if not resultado["falha"] else AMARELO
print(f"\n{cor}{resultado['ok']} de {total} verificações OK.{FIM}")
if not resultado["falha"]:
    print("Bancada pronta. Teste de failover: no R-FILIAL, /interface disable sfp1-WAN-FIBRA")
