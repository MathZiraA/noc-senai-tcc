"""Simula problemas nos enlaces sem precisar da bancada, passando pelo fluxo real de alertas.

Cria o host temporário SIMULACAO-FILIAL, injeta um histórico realista e acompanha:
e-mail de alerta -> Analista IA -> e-mail com a análise -> (chamado) -> normalização. Remove o host no fim.

Cenários (--cenario):
  queda       (padrão) a fibra cai e o rádio assume em 5 s; a fibra volta depois da análise
  degradacao  a fibra NÃO cai, mas fica lenta (~45 ms): alerta de fibra degradada antes da queda
  chamado     a fibra cai e não volta: para a demonstração o prazo do chamado vai de 1 h para 2 min
              (restaurado no fim); chega o e-mail formal ao cliente e o chamado entra no livro SHA-256
"""
import argparse
import subprocess
import time

import chamados
from zbx import ZbxError, call

HOST = "SIMULACAO-FILIAL"
GRUPO = "Rede SENAI - Equipamentos"
K_FIBRA, K_RADIO = "icmpping[10.0.1.2,3,,,500]", "icmpping[10.0.2.2,3,,,500]"
K_LAT_F, K_LAT_R = "icmppingsec[10.0.1.2,3,,,500]", "icmppingsec[10.0.2.2,3,,,500]"
K_LAN = "icmpping[192.168.20.1,1,,,300]"
FALHA_LAN = 5  # segundos sem resposta na troca de enlace
MACRO_PRAZO = "{$NOC_CHAMADO_APOS}"
STATUS = {"0": "pendente", "1": "ENVIADO", "2": "FALHOU", "3": "novo"}

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--cenario", choices=["queda", "degradacao", "chamado"], default="queda")
CENARIO = p.parse_args().cenario


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


def alertas(eventid):
    return call("alert.get", {"eventids": eventid, "selectMediatypes": ["name"], "output": ["status", "error", "subject"]})


def alertas_recuperacao(eventid):
    """O e-mail de recuperação fica ligado ao evento de RECUPERAÇÃO, não ao do problema."""
    r = call("event.get", {"eventids": eventid, "output": ["r_eventid"]})[0]["r_eventid"]
    return [] if r == "0" else alertas(r)


def enviado(lista, inicio, midia="Gmail Alertas SENAI"):
    """E-mails (não webhooks) com o assunto indicado já processados pelo Zabbix."""
    return [a for a in lista if a["subject"].startswith(inicio) and a["status"] in ("1", "2")
            and a["mediatypes"] and a["mediatypes"][0]["name"] == midia]


def tudo_processado(eventid):
    """Nenhum alerta pendente: apagar o host antes disso descarta os e-mails que ainda não saíram."""
    return all(a["status"] in ("1", "2") for a in alertas(eventid) + alertas_recuperacao(eventid))


grupo = call("hostgroup.get", {"filter": {"name": [GRUPO]}, "output": ["groupid"]})[0]["groupid"]
for antigo in call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid"]}):
    call("host.delete", [antigo["hostid"]])
hostid = call("host.create", {"host": HOST, "name": "SIMULAÇÃO - R-FILIAL (teste de failover)",
                              "description": "Host temporário criado por simular_queda.py para testar alertas.",
                              "groups": [{"groupid": grupo}],
                              "macros": [{"macro": "{$FIBRA_LAT_MAX}", "value": "0.02"}]})["hostids"][0]
prazo_original = None
try:
    tags = lambda e: [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": e}]
    for chave, nome, tipo_valor, unid, enl in [
            (K_FIBRA, "Enlace FIBRA - estado (simulação sfp1)", 3, "", "fibra"),
            (K_RADIO, "Enlace RÁDIO - estado (simulação ether1)", 3, "", "radio"),
            (K_LAT_F, "Enlace FIBRA - latência", 0, "s", "fibra"),
            (K_LAT_R, "Enlace RÁDIO - latência", 0, "s", "radio"),
            (K_LAN, "Alcance LAN Filial (1s)", 3, "", "lan")]:
        call("item.create", {"hostid": hostid, "type": 2, "key_": chave, "name": nome, "value_type": tipo_valor,
                             "units": unid, "tags": tags(enl)})
    if CENARIO == "degradacao":
        nome_trigger = "FIBRA degradada: latência acima do limite por 5min"
        call("trigger.create", {"description": nome_trigger, "priority": 3,
                                "expression": f"last(/{HOST}/{K_FIBRA})=1 and min(/{HOST}/{K_LAT_F},5m)>{{$FIBRA_LAT_MAX}}",
                                "comments": "A fibra responde, mas está lenta. O MikroTik desvia o tráfego para o rádio "
                                            "quando a média passa de 30 ms (netwatch).",
                                "tags": [{"tag": "component", "value": "redundancia"}]})
    else:
        nome_trigger = "Link FIBRA caiu: failover para RÁDIO ativo"
        call("trigger.create", {"description": nome_trigger, "priority": 4,
                                "expression": f"max(/{HOST}/{K_FIBRA},#2)=0 and last(/{HOST}/{K_RADIO})=1",
                                "comments": "Enlace principal fora. O tráfego está sendo roteado pelo backup (OSPF custo 100).",
                                "tags": [{"tag": "component", "value": "redundancia"}, {"tag": "chamado", "value": "sim"}]})
    if CENARIO == "chamado":
        m = call("usermacro.get", {"globalmacro": True, "filter": {"macro": MACRO_PRAZO},
                                   "output": ["globalmacroid", "value"]})[0]
        prazo_original = (m["globalmacroid"], m["value"])
        call("usermacro.updateglobal", {"globalmacroid": m["globalmacroid"], "value": "2m"})
        print(f"[ok] prazo do chamado reduzido de {m['value']} para 2m só durante a demonstração")
    print(f"[ok] host de simulação criado (cenário: {CENARIO})")
    subprocess.run(["zabbix_server", "-R", "config_cache_reload"], check=True, capture_output=True)
    time.sleep(8)

    agora = int(time.time())
    if CENARIO == "degradacao":
        # 4 min normais, depois 6 min com a fibra UP mas lenta (40-48 ms) e o rádio normal
        piora = agora - 360
        historico = []
        for t in range(agora - 600, agora + 1, 10):
            lenta = t >= piora
            historico += [(K_FIBRA, 1, t), (K_RADIO, 1, t),
                          (K_LAT_F, (0.040 + (t % 9) * 0.001) if lenta else 0.0021 + (t % 7) * 0.0001, t),
                          (K_LAT_R, 0.0089 + (t % 5) * 0.0003, t)]
        historico += [(K_LAN, 1, t) for t in range(agora - 600, agora + 1)]
        lotes = [sorted(historico, key=lambda v: v[2])]
        descricao = "histórico injetado: fibra UP mas lenta (~45 ms) há 6 minutos"
    else:
        # 10 min normais, queda da fibra 40 s atrás com 5 s de LAN sem resposta
        queda = agora - 40
        normal = []
        for t in range(agora - 600, queda, 10):
            normal += [(K_FIBRA, 1, t), (K_RADIO, 1, t), (K_LAT_F, 0.0021 + (t % 7) * 0.0001, t),
                       (K_LAT_R, 0.0089 + (t % 5) * 0.0003, t)]
        lan = [(K_LAN, 0 if queda <= t < queda + FALHA_LAN else 1, t) for t in range(agora - 600, agora + 1)]
        pos_queda = []
        for t in range(queda, agora + 1, 10):
            pos_queda += [(K_RADIO, 1, t), (K_LAT_R, 0.0124 + (t % 3) * 0.0004, t), (K_LAT_F, 0, t)]
        lotes = [sorted(normal + lan + pos_queda, key=lambda v: v[2]), [(K_FIBRA, 0, t) for t in range(queda, agora + 1, 10)]]
        descricao = "histórico injetado: fibra caiu, rádio assumiu"

    def tentar():
        try:
            for lote in lotes:
                empurrar(lote)
            return True
        except ZbxError as e:
            print(f"    aguardando o Zabbix carregar os itens... ({e})")
            return False

    esperar(descricao, tentar, limite=90, passo=10)
    evento = esperar(f"problema '{nome_trigger}' aberto",
                     lambda: call("problem.get", {"hostids": hostid, "output": ["eventid", "name"]}), limite=90)[0]
    eid = evento["eventid"]
    esperar("e-mail de alerta enviado", lambda: enviado(alertas(eid), "🚨"), limite=120)
    comentario = esperar("análise da IA publicada no evento (60 s de agrupamento + investigação)",
                         lambda: [a for a in call("event.get", {"eventids": eid, "selectAcknowledges": ["message"]})[0]
                                  ["acknowledges"] if a["message"].startswith("ANÁLISE IA")], limite=360, passo=10)
    esperar("e-mail com a análise da IA enviado", lambda: enviado(alertas(eid), "[ANÁLISE IA]"), limite=120)
    print("\n----- ANÁLISE DA IA -----\n" + comentario[0]["message"] + "\n-------------------------\n")

    if CENARIO == "chamado":
        print("    a fibra continua fora: aguardando o prazo do chamado (2 min desde a queda)...")
        esperar("e-mail formal de CHAMADO enviado ao cliente", lambda: enviado(alertas(eid), "[CHAMADO"),
                limite=300, passo=10)
        esperar(f"chamado {chamados.numero(eid)} registrado no livro", lambda: chamados.aberto(eid), limite=60)

    # Enlace normaliza
    volta = int(time.time())
    if CENARIO == "degradacao":
        empurrar([(K_LAT_F, 0.0021, volta), (K_LAT_F, 0.0020, volta + 1)])
    else:
        empurrar([(K_FIBRA, 1, volta), (K_LAT_F, 0.0022, volta), (K_FIBRA, 1, volta + 1)])
    esperar("problema resolvido (fibra normalizada)",
            lambda: not call("problem.get", {"hostids": hostid, "output": ["eventid"]}), limite=90)
    esperar("e-mail de normalização enviado", lambda: enviado(alertas_recuperacao(eid), "✅"), limite=120)
    if CENARIO == "chamado":
        esperar("e-mail de ENCERRAMENTO do chamado enviado", lambda: enviado(alertas_recuperacao(eid), "[CHAMADO"),
                limite=120)
        esperar("encerramento registrado no livro", lambda: not chamados.aberto(eid), limite=60)
        ok, msg = chamados.verificar()
        print(("[ok] " if ok else "[ALERTA] ") + msg)
    esperar("todos os e-mails processados pelo Zabbix", lambda: tudo_processado(eid), limite=180, passo=5)

    print("\nE-mails deste teste:")
    for a in alertas(eid) + alertas_recuperacao(eid):
        erro = f" — {a['error']}" if a["error"] else ""
        print(f"  - {a['mediatypes'][0]['name']}: {STATUS[a['status']]} | {a['subject'][:90]}{erro}")
finally:
    if prazo_original:
        call("usermacro.updateglobal", {"globalmacroid": prazo_original[0], "value": prazo_original[1]})
        print(f"[ok] prazo do chamado restaurado para {prazo_original[1]}")
    call("host.delete", [hostid])
    print("[ok] host de simulação removido")
