"""Ferramentas SOMENTE LEITURA que o Analista NOC (Claude) usa para investigar incidentes."""
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from anthropic import beta_tool

import config
from zbx import call

MIKROTIK_IP = config.LOOPBACK_FILIAL  # loopback: alcançável pela fibra ou pelo rádio
MIKROTIK_USER = "zabbix-ia"
MIKROTIK_KEY = Path("/root/.ssh/id_ed25519_mikrotik")
SEVERIDADES = ["Não classificada", "Informação", "Aviso", "Média", "Alta", "Desastre"]
DISPONIBILIDADE = {"0": "desconhecida", "1": "DISPONÍVEL", "2": "INDISPONÍVEL"}
CONSULTAS_MIKROTIK = {
    "interfaces": "/interface print without-paging",
    "erros_ethernet": "/interface ethernet print stats without-paging",
    "vizinhos_ospf": "/routing ospf neighbor print detail without-paging",
    "rotas": "/ip route print without-paging",
    "log_recente": "/log print without-paging",
    "recursos": "/system resource print",
    "netwatch": "/tool netwatch print detail without-paging",
    "ospf_custos": "/routing ospf interface-template print detail without-paging",
}


def _hora(ts):
    return datetime.fromtimestamp(int(ts)).strftime("%d/%m %H:%M:%S")


def _host(nome):
    h = call("host.get", {"filter": {"host": [nome]}, "output": ["hostid", "host", "maintenance_status"],
                          "selectInterfaces": ["type", "ip", "available", "error"]})
    if not h:
        raise ValueError(f"host '{nome}' não existe no Zabbix")
    return h[0]


def estado_atual(host: str) -> str:
    """Retrato do host agora: disponibilidade SNMP, estado de cada enlace (fibra/rádio) e problemas ativos.

    Args:
        host: Nome técnico do host no Zabbix, ex.: R-FILIAL.
    """
    h = _host(host)
    linhas = [f"Host {h['host']} | em manutenção: {'sim' if h['maintenance_status'] == '1' else 'não'}"]
    for i in h["interfaces"]:
        erro = f" (erro: {i['error']})" if i["error"] else ""
        linhas.append(f"Interface de coleta {i['ip']}: {DISPONIBILIDADE.get(i['available'], '?')}{erro}")
    linhas.append("Enlaces (medidos por ping a partir da Matriz, a cada 10s):")
    for it in call("item.get", {"hostids": h["hostid"], "tags": [{"tag": "component", "value": "enlace"}],
                                "output": ["name", "lastvalue", "lastclock", "units"], "selectValueMap": ["mappings"]}):
        valor = it["lastvalue"]
        for m in (it["valuemap"] or {}).get("mappings", []):
            if m["value"] == valor:
                valor = m["newvalue"]
        if it["units"] == "s":
            valor = f"{float(it['lastvalue']) * 1000:.1f} ms"
        quando = _hora(it["lastclock"]) if it["lastclock"] != "0" else "nunca coletado"
        linhas.append(f"  - {it['name']}: {valor} (em {quando})")
    problemas = call("problem.get", {"hostids": h["hostid"], "output": ["name", "severity", "clock"],
                                     "sortfield": ["eventid"], "sortorder": "DESC"})
    linhas.append(f"Problemas ativos: {len(problemas)}")
    for p in problemas:
        linhas.append(f"  - [{SEVERIDADES[int(p['severity'])]}] {p['name']} (desde {_hora(p['clock'])})")
    return "\n".join(linhas)


def historico_item(host: str, nome_item: str, minutos: int = 60) -> str:
    """Histórico de itens cujo nome contém o texto informado. Para itens de estado (UP/DOWN) devolve
    as transições; para métricas devolve mínimo/média/máximo e amostras.

    Args:
        host: Nome técnico do host, ex.: R-FILIAL.
        nome_item: Trecho do nome do item, ex.: "Enlace FIBRA", "latência", "perda", "ether2", "CPU".
        minutos: Janela de tempo para trás, em minutos (1 a 1440).
    """
    minutos = max(1, min(int(minutos), 1440))
    h = _host(host)
    itens = call("item.get", {"hostids": h["hostid"], "search": {"name": nome_item}, "limit": 4,
                              "output": ["itemid", "name", "key_", "value_type", "units"]})
    if not itens:
        return f"Nenhum item com '{nome_item}' no nome. Use listar_itens para ver os disponíveis."
    desde = int(time.time()) - minutos * 60
    blocos = []
    for it in itens:
        hist = call("history.get", {"itemids": it["itemid"], "history": int(it["value_type"]),
                                    "time_from": desde, "sortfield": "clock", "sortorder": "ASC", "limit": 5000})
        cab = f"{it['name']} — últimos {minutos} min, {len(hist)} amostras"
        if not hist:
            blocos.append(f"{cab}: sem dados no período.")
            continue
        if it["key_"].startswith("icmpping["):
            estado = lambda v: "UP" if v["value"] == "1" else "DOWN"
            trans, anterior = [], hist[0]["value"]
            for v in hist[1:]:
                if v["value"] != anterior:
                    trans.append(f"{_hora(v['clock'])} mudou para {estado(v)}")
                    anterior = v["value"]
            inicio = (f"Primeira amostra da janela ({_hora(hist[0]['clock'])}): {estado(hist[0])} "
                      "(o que aconteceu antes disso não aparece aqui)")
            mudancas = "\n  ".join(trans[-30:]) if trans else "nenhuma mudança de estado na janela"
            blocos.append(f"{cab}.\n  {inicio}\n  {mudancas}")
        elif it["value_type"] in ("0", "3"):
            vals = [float(v["value"]) for v in hist]
            fator, un = (1000, "ms") if it["units"] == "s" else (1, it["units"])
            passo = max(1, len(hist) // 12)
            amostras = ", ".join(f"{_hora(v['clock'])[6:]}={float(v['value']) * fator:.1f}" for v in hist[::passo])
            blocos.append(f"{cab} ({un}): min={min(vals) * fator:.2f} média={sum(vals) / len(vals) * fator:.2f} "
                          f"max={max(vals) * fator:.2f} última={vals[-1] * fator:.2f}\n  amostras: {amostras}")
        else:
            blocos.append(f"{cab}:\n  " + "\n  ".join(f"{_hora(v['clock'])}: {v['value']}" for v in hist[-10:]))
    return "\n\n".join(blocos)


def eventos_recentes(host: str, horas: int = 24) -> str:
    """Problemas que começaram no host nas últimas horas, com duração ou indicação de ainda ativos.
    Útil para detectar quedas repetidas (link instável) e correlacionar eventos.

    Args:
        host: Nome técnico do host, ex.: R-FILIAL.
        horas: Janela de tempo para trás, em horas (1 a 168).
    """
    horas = max(1, min(int(horas), 168))
    h = _host(host)
    evs = call("event.get", {"hostids": h["hostid"], "source": 0, "object": 0, "value": 1,
                             "time_from": int(time.time()) - horas * 3600, "sortfield": ["clock"],
                             "sortorder": "DESC", "limit": 60,
                             "output": ["eventid", "clock", "name", "severity", "r_eventid"]})
    if not evs:
        return f"Nenhum problema registrado nas últimas {horas}h."
    rec_ids = [e["r_eventid"] for e in evs if e["r_eventid"] != "0"]
    recs = {r["eventid"]: int(r["clock"]) for r in
            (call("event.get", {"eventids": rec_ids, "output": ["eventid", "clock"]}) if rec_ids else [])}
    linhas = [f"{len(evs)} problemas nas últimas {horas}h (mais recentes primeiro):"]
    for e in evs:
        if e["r_eventid"] in recs:
            dur = recs[e["r_eventid"]] - int(e["clock"])
            fim = f"resolvido após {dur // 60}min{dur % 60:02d}s"
        else:
            fim = "AINDA ATIVO"
        linhas.append(f"  - {_hora(e['clock'])} [{SEVERIDADES[int(e['severity'])]}] {e['name']} — {fim}")
    return "\n".join(linhas)


def listar_itens(host: str, filtro: str = "") -> str:
    """Lista itens monitorados do host (nome, último valor). Use para descobrir o que existe
    (tráfego por interface, CPU, temperatura, estado OSPF...) antes de pedir histórico.

    Args:
        host: Nome técnico do host, ex.: R-FILIAL.
        filtro: Trecho do nome para filtrar; vazio lista os primeiros 60 itens.
    """
    h = _host(host)
    params = {"hostids": h["hostid"], "output": ["name", "lastvalue", "units", "state"], "limit": 60,
              "sortfield": "name"}
    if filtro:
        params["search"] = {"name": filtro}
    itens = call("item.get", params)
    if not itens:
        return "Nenhum item encontrado (se o SNMP ainda não respondeu, a descoberta de interfaces não rodou)."
    return "\n".join(f"- {i['name']}: {i['lastvalue']}{i['units']}" + (" [NÃO SUPORTADO]" if i["state"] == "1" else "")
                     for i in itens)


def _historico(itemid, value_type, desde, ate=None):
    params = {"itemids": itemid, "history": int(value_type), "time_from": desde, "sortfield": "clock",
              "sortorder": "ASC", "limit": 100000}
    if ate:
        params["time_till"] = ate
    return [(int(v["clock"]), v["value"]) for v in call("history.get", params)]


def _item(hostid, chave):
    return call("item.get", {"hostids": hostid, "filter": {"key_": chave}, "output": ["itemid", "value_type"]})[0]


def failovers(host, horas=24):
    """Lista de trocas da fibra (queda e retorno) com o tempo que a LAN da Filial ficou sem resposta.
    Cada item: {"evento": "queda"|"retorno", "inicio": ts, "segundos": int|None, "voltou": bool}."""
    h = _host(host)
    fibra, lan = _item(h["hostid"], config.K_FIBRA), _item(h["hostid"], config.K_LAN)
    desde = int(time.time()) - horas * 3600
    estados = _historico(fibra["itemid"], fibra["value_type"], desde)
    trocas = [(t, "queda" if v == "0" else "retorno") for (t, v), (_, ant) in zip(estados[1:], estados) if v != ant]
    resultado = []
    for t, tipo in trocas:
        # a fibra é medida a cada 10 s com confirmação em 2 amostras: a interrupção real começa até ~30 s antes
        janela = _historico(lan["itemid"], lan["value_type"], t - 40, t + 180)
        falhas, atual = [], None
        for ts, v in janela:
            if v == "0":
                atual = [ts, ts] if atual is None else [atual[0], ts]
            elif atual:
                falhas.append(atual)
                atual = None
        if atual:  # ainda sem resposta no fim da janela
            resultado.append({"evento": tipo, "inicio": atual[0], "segundos": None, "voltou": False})
        elif falhas:
            maior = max(falhas, key=lambda f: f[1] - f[0])
            resultado.append({"evento": tipo, "inicio": maior[0], "segundos": maior[1] - maior[0] + 1, "voltou": True})
        else:
            resultado.append({"evento": tipo, "inicio": t, "segundos": 0, "voltou": True})
    return resultado


def medir_failover(host: str, horas: int = 24) -> str:
    """Mede, para cada queda e retorno da fibra, quantos segundos a LAN da Filial ficou sem resposta
    (ping a cada 1 s). É o tempo real de failover/failback do OSPF percebido pelos usuários.

    Args:
        host: Nome técnico do host, ex.: R-FILIAL.
        horas: Janela de tempo para trás, em horas (1 a 168).
    """
    lista = failovers(host, max(1, min(int(horas), 168)))
    if not lista:
        return f"Nenhuma queda ou retorno da fibra nas últimas {horas}h."
    linhas = []
    for f in lista:
        nome = "Queda da fibra (failover para o rádio)" if f["evento"] == "queda" else "Retorno da fibra (failback)"
        if not f["voltou"]:
            medida = "a LAN da Filial NÃO voltou a responder na janela de 3 min (failover não aconteceu)"
        elif f["segundos"] == 0:
            medida = "nenhuma interrupção medida na LAN da Filial (troca transparente)"
        else:
            medida = f"LAN da Filial sem resposta por {f['segundos']} s a partir de {_hora(f['inicio'])}"
        linhas.append(f"- {nome}: {medida}")
    return "\n".join(linhas)


def consultar_mikrotik(consulta: Literal["interfaces", "erros_ethernet", "vizinhos_ospf", "rotas",
                                        "log_recente", "recursos", "netwatch", "ospf_custos"]) -> str:
    """Executa uma consulta de LEITURA no RouterOS do R-FILIAL via SSH (usuário sem permissão de escrita).
    Só funciona se algum enlace estiver de pé.

    Args:
        consulta: interfaces (estado/link), erros_ethernet (CRC/FCS por porta), vizinhos_ospf (adjacências),
            rotas (tabela de rotas e por onde a Matriz é alcançada), log_recente (últimas linhas do log),
            recursos (CPU, memória, uptime), netwatch (teste de qualidade da fibra: up/down e latência),
            ospf_custos (custo atual de cada enlace: fibra 200 = desviada para o rádio por qualidade).
    """
    if not MIKROTIK_KEY.exists():
        return "Acesso SSH ao MikroTik ainda não configurado (chave ausente). Baseie-se nos dados do Zabbix."
    cmd = ["ssh", "-i", str(MIKROTIK_KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
           "-o", "StrictHostKeyChecking=accept-new", f"{MIKROTIK_USER}@{MIKROTIK_IP}", CONSULTAS_MIKROTIK[consulta]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        return "Tempo esgotado: o roteador não respondeu via SSH (provavelmente inalcançável)."
    if r.returncode != 0:
        return f"Falha no SSH (código {r.returncode}): {r.stderr.strip()[:300]}"
    saida = r.stdout.strip().splitlines()
    if consulta == "log_recente":
        saida = saida[-40:]
    return "\n".join(saida)[-4000:]


FUNCOES = [estado_atual, historico_item, eventos_recentes, listar_itens, medir_failover, consultar_mikrotik]
TODAS = [beta_tool(f) for f in FUNCOES]
