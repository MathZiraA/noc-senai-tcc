"""Teste ponta a ponta: cria um host temporário, dispara um problema real no Zabbix e acompanha
webhook -> analista -> comentário -> e-mail. Remove o host no final. Requer /root/noc/MODO_TESTE
(ou uma chave de IA) e o serviço noc-analista rodando."""
import subprocess
import time

from zbx import ZbxError, call

HOST = "NOC-TESTE"
CHAVE_ITEM = "noc.teste"
STATUS_ALERTA = {"0": "pendente", "1": "ENVIADO", "2": "FALHOU", "3": "novo"}


def esperar(descricao, funcao, limite=180, passo=5):
    fim = time.time() + limite
    while time.time() < fim:
        resultado = funcao()
        if resultado:
            print(f"[ok] {descricao}")
            return resultado
        time.sleep(passo)
    raise SystemExit(f"[FALHOU] {descricao}: nada após {limite}s")


def empurrar(valor):
    try:
        call("history.push", [{"host": HOST, "key": CHAVE_ITEM, "value": valor}])
        return True
    except ZbxError as e:
        print(f"    aguardando o Zabbix carregar o item... ({e})")
        return False


grupo = call("hostgroup.get", {"filter": {"name": ["Rede SENAI - Equipamentos"]}, "output": ["groupid"]})[0]["groupid"]
for antigo in call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid"]}):
    call("host.delete", [antigo["hostid"]])
hostid = call("host.create", {"host": HOST, "name": "NOC-TESTE (temporário)", "groups": [{"groupid": grupo}]})["hostids"][0]
try:
    call("item.create", {"hostid": hostid, "name": "Teste integração", "key_": CHAVE_ITEM, "type": 2, "value_type": 3})
    call("trigger.create", {"description": "TESTE INTEGRAÇÃO - Analista IA", "priority": 4,
                            "expression": f"last(/{HOST}/{CHAVE_ITEM})=1"})
    print("[ok] host/item/trigger temporários criados")

    subprocess.run(["zabbix_server", "-R", "config_cache_reload"], check=True, capture_output=True)
    time.sleep(5)

    def disparar():
        empurrar(1)  # reenvia até o trigger (recém-carregado no cache) avaliar o valor
        return call("problem.get", {"hostids": hostid, "output": ["eventid", "name"]})

    evento = esperar("problema aberto no Zabbix", disparar, limite=120, passo=10)[0]
    print(f"    evento {evento['eventid']}: {evento['name']}")

    def alertas():
        return call("alert.get", {"eventids": evento["eventid"], "output": ["mediatypeid", "status", "error", "subject"],
                                  "selectMediatypes": ["name"]})

    esperar("webhook entregue ao analista", lambda: [a for a in alertas()
                                                      if a["mediatypes"][0]["name"] == "Analista IA" and a["status"] == "1"])
    comentario = esperar("comentário da análise publicado no evento (janela de 60s + análise)",
                         lambda: [a for a in call("event.get", {"eventids": evento["eventid"],
                                                                "selectAcknowledges": ["message"]})[0]["acknowledges"]
                                  if a["message"].startswith("ANÁLISE IA")], limite=240)
    print("    comentário:", comentario[0]["message"][:160].replace("\n", " | "), "...")
    esperar("e-mail com a análise enviado",
            lambda: [a for a in alertas() if a["subject"].startswith("[ANÁLISE IA]") and a["status"] in ("1", "2")],
            limite=120)
    print("\nAlertas gerados por este evento:")
    for a in alertas():
        erro = f" — {a['error']}" if a["error"] else ""
        print(f"  - {a['mediatypes'][0]['name']}: {STATUS_ALERTA[a['status']]} | {a['subject'][:70]}{erro}")

    esperar("problema resolvido", lambda: empurrar(0) and not call("problem.get", {"hostids": hostid,
                                                                                    "output": ["eventid"]}), limite=60)
    time.sleep(15)  # deixa a notificação de recuperação sair antes de apagar o host
finally:
    call("host.delete", [hostid])
    print("[ok] host temporário removido")
