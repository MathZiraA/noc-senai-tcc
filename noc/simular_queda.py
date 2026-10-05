"""Simula uma queda da fibra com failover para o rádio, sem precisar da bancada.

Cria o host temporário SIMULACAO-FILIAL (mesmos itens e trigger de failover do R-FILIAL), injeta um histórico
realista (10 min normais, depois a fibra cai e a LAN fica 5 s sem resposta) e acompanha o fluxo real:
e-mail de alerta -> Analista IA (provedor configurado) -> e-mail com a análise -> normalização.
No fim, religa a fibra, espera o e-mail de normalização e remove o host.
"""
import subprocess
import time

from zbx import ZbxError, call

HOST = "SIMULACAO-FILIAL"
GRUPO = "Rede SENAI - Equipamentos"
K_FIBRA, K_RADIO = "icmpping[10.0.1.2,3,,,500]", "icmpping[10.0.2.2,3,,,500]"
K_LAT_F, K_LAT_R = "icmppingsec[10.0.1.2,3,,,500]", "icmppingsec[10.0.2.2,3,,,500]"
K_LAN = "icmpping[192.168.20.1,1,,,300]"
FALHA_LAN = 5  # segundos sem resposta na troca de enlace
STATUS = {"0": "pendente", "1": "ENVIADO", "2": "FALHOU", "3": "novo"}


def esperar(descricao, funcao, limite=240, passo=5):
    fim = time.time() + limite
    while time.time() < fim:
        r = funcao()
        if r:
            print(f"[ok] {descricao}")
            return r
        time.sleep(passo)
    raise SystemExit(f"[FALHOU] {descricao}: nada após {limite}s")


def empurrar(valores):
    """valores = [(chave, valor, clock), ...] em ordem de tempo."""
    for i in range(0, len(valores), 500):
        call("history.push", [{"host": HOST, "key": k, "value": v, "clock": c} for k, v, c in valores[i:i + 500]])


grupo = call("hostgroup.get", {"filter": {"name": [GRUPO]}, "output": ["groupid"]})[0]["groupid"]
for antigo in call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid"]}):
    call("host.delete", [antigo["hostid"]])
hostid = call("host.create", {"host": HOST, "name": "SIMULAÇÃO - R-FILIAL (teste de failover)",
                              "description": "Host temporário criado por simular_queda.py para testar alertas.",
                              "groups": [{"groupid": grupo}]})["hostids"][0]
try:
    tags = lambda e: [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": e}]
    for chave, nome, tipo_valor, unid, enl in [
            (K_FIBRA, "Enlace FIBRA - estado (simulação ether2)", 3, "", "fibra"),
            (K_RADIO, "Enlace RÁDIO - estado (simulação ether3)", 3, "", "radio"),
            (K_LAT_F, "Enlace FIBRA - latência", 0, "s", "fibra"),
            (K_LAT_R, "Enlace RÁDIO - latência", 0, "s", "radio"),
            (K_LAN, "Alcance LAN Filial (1s)", 3, "", "lan")]:
        call("item.create", {"hostid": hostid, "type": 2, "key_": chave, "name": nome, "value_type": tipo_valor,
                             "units": unid, "tags": tags(enl)})
    call("trigger.create", {"description": "Link FIBRA caiu: failover para RÁDIO ativo", "priority": 4,
                            "expression": f"max(/{HOST}/{K_FIBRA},#2)=0 and last(/{HOST}/{K_RADIO})=1",
                            "comments": "Enlace principal fora. O tráfego está sendo roteado pelo backup (OSPF custo 100).",
                            "tags": [{"tag": "component", "value": "redundancia"}]})
    print("[ok] host de simulação criado com itens e trigger de failover")
    subprocess.run(["zabbix_server", "-R", "config_cache_reload"], check=True, capture_output=True)
    time.sleep(8)

    # Histórico: 10 min normais, queda da fibra 40 s atrás com 5 s de LAN sem resposta
    agora = int(time.time())
    queda = agora - 40
    normal = []
    for t in range(agora - 600, queda, 10):
        normal += [(K_FIBRA, 1, t), (K_RADIO, 1, t), (K_LAT_F, 0.0021 + (t % 7) * 0.0001, t),
                   (K_LAT_R, 0.0089 + (t % 5) * 0.0003, t)]
    lan = [(K_LAN, 0 if queda <= t < queda + FALHA_LAN else 1, t) for t in range(agora - 600, agora + 1)]
    pos_queda = []
    for t in range(queda, agora + 1, 10):
        pos_queda += [(K_RADIO, 1, t), (K_LAT_R, 0.0124 + (t % 3) * 0.0004, t), (K_LAT_F, 0, t)]
    fibra_caida = [(K_FIBRA, 0, t) for t in range(queda, agora + 1, 10)]

    def tentar():
        try:
            empurrar(sorted(normal + lan + pos_queda, key=lambda v: v[2]))
            empurrar(fibra_caida)
            return True
        except ZbxError as e:
            print(f"    aguardando o Zabbix carregar os itens... ({e})")
            return False

    esperar("histórico injetado: fibra caiu, rádio assumiu", tentar, limite=90, passo=10)
    evento = esperar("problema 'Link FIBRA caiu' aberto",
                     lambda: call("problem.get", {"hostids": hostid, "output": ["eventid", "name"]}), limite=90)[0]

    def alertas():
        return call("alert.get", {"eventids": evento["eventid"], "selectMediatypes": ["name"],
                                  "output": ["status", "error", "subject"]})

    esperar("e-mail de alerta enviado", lambda: [a for a in alertas() if a["subject"].startswith("🚨")
                                                 and a["status"] in ("1", "2")], limite=120)
    comentario = esperar("análise da IA publicada no evento (60 s de agrupamento + investigação)",
                         lambda: [a for a in call("event.get", {"eventids": evento["eventid"],
                                                                "selectAcknowledges": ["message"]})[0]["acknowledges"]
                                  if a["message"].startswith("ANÁLISE IA")], limite=300, passo=10)
    esperar("e-mail com a análise da IA enviado",
            lambda: [a for a in alertas() if a["subject"].startswith("[ANÁLISE IA]") and a["status"] in ("1", "2")],
            limite=120)
    print("\n----- ANÁLISE DA IA -----\n" + comentario[0]["message"] + "\n-------------------------\n")

    # Fibra volta
    volta = int(time.time())
    empurrar([(K_FIBRA, 1, volta), (K_LAT_F, 0.0022, volta), (K_FIBRA, 1, volta + 1)])
    esperar("problema resolvido (fibra de volta)",
            lambda: not call("problem.get", {"hostids": hostid, "output": ["eventid"]}), limite=90)
    esperar("e-mail de normalização enviado",
            lambda: [a for a in alertas() if a["subject"].startswith("✅") and a["status"] in ("1", "2")], limite=120)
    print("\nE-mails deste teste:")
    for a in alertas():
        erro = f" — {a['error']}" if a["error"] else ""
        print(f"  - {a['mediatypes'][0]['name']}: {STATUS[a['status']]} | {a['subject'][:80]}{erro}")
finally:
    call("host.delete", [hostid])
    print("[ok] host de simulação removido")
