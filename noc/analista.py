"""Analista NOC com IA (Gemini gratuito ou Claude).

Recebe eventos do Zabbix (webhook -> POST http://127.0.0.1:8765/evento), agrupa eventos do mesmo
host numa janela de 60s, deixa a IA investigar com ferramentas somente leitura e publica o
relatório como comentário no evento. A ação "Analista IA" do Zabbix envia esse comentário por e-mail.

Uso:
  analista.py --servico                 roda o receptor (systemd)
  analista.py --simular [--publicar]    analisa o problema ativo mais grave do R-FILIAL agora
"""
import argparse
import json
import logging
import queue
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

import config
import ferramentas
from config import C
import provedor_gemini
import provedor_teste
from zbx import TOKEN_ANALISTA, call

PORTA = 8765
JANELA_CORRELACAO = 60          # segundos para juntar eventos do mesmo host num incidente só
COOLDOWN_TRIGGER = 15 * 60      # não reanalisa o mesmo problema (link oscilando) antes disso
MAX_ANALISES_HORA = 12          # teto de custo
LIMITE_COMENTARIO = 2000        # acknowledges.message no Zabbix 7.0 é varchar(2048)
MODELO = "claude-opus-5-5"
CHAVE = Path("/root/.anthropic_key")
DIR_RELATORIOS = Path("/var/lib/noc-analista")

log = logging.getLogger("analista")

SYSTEM = """Você é o Analista NOC de plantão da rede do TCC SENAI 2026 (Matriz e Filial). Quando o Zabbix \
abre um incidente, você investiga com as ferramentas disponíveis e escreve um relatório curto e útil \
para o técnico que vai ler o e-mail.

TOPOLOGIA
""" + f"""- R-MATRIZ (MikroTik RouterOS v7, router-id 1.1.1.1): LAN {C['REDE_MATRIZ']}, gateway {C['GW_MATRIZ']}.
- {config.HOST} (MikroTik RouterOS v7, router-id 2.2.2.2): LAN {C['REDE_FILIAL']}, gateway {C['LAN_FILIAL']}. \
É o host monitorado.
- Enlace PRINCIPAL Fibra óptica: {C['REDE_FIBRA']} (Matriz {C['FIBRA_MATRIZ']}, Filial {C['FIBRA_FILIAL']}), \
portas ether2-WAN-FIBRA, OSPF custo 10.
- Enlace BACKUP Rádio P2P: {C['REDE_RADIO']} (Matriz {C['RADIO_MATRIZ']}, Filial {C['RADIO_FILIAL']}; antenas em \
bridge L2 com IPs {C['ANTENA_MATRIZ']} e {C['ANTENA_FILIAL']}), portas ether3-WAN-RADIO, OSPF custo 100.
- OSPF área 0 entre os roteadores; se a fibra cai, o OSPF converge e o tráfego passa pelo rádio.
- MTU 2000 em todas as interfaces dos roteadores.
- A rede não tem saída para a internet: o impacto de uma queda é a comunicação Matriz <-> Filial.
- O Zabbix fica NA MATRIZ ({config.SERVIDOR_IP}). Ele mede cada enlace pingando o IP da Filial daquele enlace \
({C['FIBRA_FILIAL']} e {C['RADIO_FILIAL']}) a cada 10s e coleta o {config.HOST} por SNMP no IP da LAN {C['LAN_FILIAL']}.
""" + """
COMO INTERPRETAR OS DADOS
- Latência 0 ms com o enlace DOWN significa "sem resposta", não um enlace rápido.
- Se os dois enlaces estão DOWN, o Zabbix perde toda a visibilidade da Filial: não dá para saber se \
foi queda dos enlaces, do roteador ou de energia. Diga isso e liste o que verificar fisicamente.
- Se o SNMP está indisponível mas um enlace responde ping, suspeite de configuração SNMP/firewall, \
não de queda de rede.
- Quedas repetidas da fibra em pouco tempo indicam problema físico (conector, cordão, transceptor).
- O host pode estar em manutenção (bancada em montagem); nesse caso mencione isso.
- Se a PRIMEIRA amostra do histórico já é DOWN, você não sabe quando caiu: escreva "já estava DOWN \
desde o início da medição (hh:mm:ss)", nunca "caiu às hh:mm:ss".
- Confiança alta só quando a evidência aponta para UMA causa. Se você lista causas alternativas \
que os dados não conseguem distinguir, a confiança é baixa ou média.

COMO INVESTIGAR
Comece por estado_atual e eventos_recentes. Use historico_item nos enlaces para montar a linha do \
tempo. Se a fibra caiu ou voltou, use medir_failover: ele dá em segundos quanto tempo a LAN da Filial \
ficou sem resposta na troca de enlace (ping a cada 1 s); cite esse número na linha do tempo e no impacto \
(até ~10 s é um failover saudável de OSPF). Alertas "PREVISÃO" e "acima do normal" significam que o \
rádio ainda funciona mas está piorando: trate como risco futuro, não como queda. Se algum enlace está de pé, consultar_mikrotik (vizinhos_ospf, \
rotas, interfaces, log_recente, erros_ethernet) confirma por onde o tráfego passa. Pare de investigar \
quando já tiver o suficiente; não repita consultas.

RELATÓRIO (texto puro, sem markdown, sem # nem **, no máximo 1700 caracteres), exatamente nestas seções:
RESUMO: uma ou duas frases dizendo o que aconteceu e se a redundância funcionou.
LINHA DO TEMPO: marcadores "- hh:mm:ss  fato" só com fatos observados.
CAUSA PROVÁVEL: hipótese principal com confiança (alta/média/baixa) e a evidência que a sustenta.
IMPACTO: o que os usuários da Filial sentem e como está a redundância agora.
AÇÕES RECOMENDADAS: lista numerada, concreta, na ordem em que o técnico deve fazer.

Afirme apenas o que os dados mostram. Se faltou dado (SNMP sem resposta, SSH indisponível), diga \
qual e como isso limita a conclusão. Nunca invente valores, horários ou comandos executados."""


def provedor():
    """Claude tem prioridade se houver chave; senão, Gemini (gratuito). MODO_TESTE sobrepõe ambos."""
    if provedor_teste.disponivel():
        return "teste"
    if CHAVE.exists():
        return "claude"
    if provedor_gemini.disponivel():
        return "gemini"
    return None


def analisar(eventos):
    """Roda a investigação da IA sobre um lote de eventos. Retorna (relatorio, metadados)."""
    host = eventos[0]["host"]
    lista = "\n".join(f"- evento {e['eventid']} | início {e.get('horario', '?')} | {e.get('severidade', '?')} | {e['nome']}"
                      for e in eventos)
    pedido = (f"Host: {host}\nAgora: {datetime.now():%d/%m/%Y %H:%M:%S}\n"
              f"Problemas abertos pelo Zabbix e agrupados como um incidente:\n{lista}\n\n"
              "Investigue e escreva o relatório.")
    qual = provedor()
    if qual == "teste":
        return provedor_teste.analisar(SYSTEM, pedido, ferramentas.FUNCOES)
    if qual == "gemini":
        return provedor_gemini.analisar(SYSTEM, pedido, ferramentas.FUNCOES)
    if qual is None:
        raise RuntimeError(f"nenhuma chave de IA: crie {provedor_gemini.CHAVE} (Gemini) ou {CHAVE} (Claude)")
    return _analisar_claude(pedido)


def _analisar_claude(pedido):
    inicio = time.time()
    runner = anthropic.Anthropic(api_key=CHAVE.read_text().strip()).beta.messages.tool_runner(
        model=MODELO,
        max_tokens=16000,
        system=SYSTEM,
        tools=ferramentas.TODAS,
        messages=[{"role": "user", "content": pedido}],
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        max_iterations=15,
    )
    ultima, chamadas, tok_in, tok_out = None, [], 0, 0
    for msg in runner:
        ultima = msg
        tok_in += msg.usage.input_tokens
        tok_out += msg.usage.output_tokens
        chamadas += [f"{b.name}({json.dumps(b.input, ensure_ascii=False)})" for b in msg.content if b.type == "tool_use"]
    if ultima is None:
        raise RuntimeError("a API não devolveu nenhuma mensagem")
    if ultima.stop_reason == "refusal":
        raise RuntimeError(f"o modelo recusou a análise: {ultima.stop_details}")
    if ultima.stop_reason == "tool_use":
        raise RuntimeError("limite de iterações atingido antes do relatório final")
    texto = "\n".join(b.text for b in ultima.content if b.type == "text").strip()
    if not texto:
        raise RuntimeError(f"resposta sem texto (stop_reason={ultima.stop_reason})")
    meta = {"modelo": ultima.model, "segundos": round(time.time() - inicio, 1), "tokens_entrada": tok_in,
            "tokens_saida": tok_out, "ferramentas": chamadas, "stop_reason": ultima.stop_reason}
    return texto, meta


def publicar(eventos, relatorio, meta):
    """Salva o relatório em disco e comenta no evento principal (o que dispara o e-mail)."""
    principal = max(eventos, key=lambda e: int(e.get("severidade_num", 0)))
    DIR_RELATORIOS.mkdir(parents=True, exist_ok=True)
    base = DIR_RELATORIOS / f"{datetime.now():%Y%m%d-%H%M%S}-evento{principal['eventid']}"
    base.with_suffix(".txt").write_text(relatorio + "\n")
    base.with_suffix(".json").write_text(json.dumps({"eventos": eventos, **meta}, ensure_ascii=False, indent=1))
    comentario = f"ANÁLISE IA ({meta['modelo']})\n\n{relatorio}"
    if len(comentario) > LIMITE_COMENTARIO:
        aviso = f"\n[...] relatório completo em {base.with_suffix('.txt')}"
        comentario = comentario[:LIMITE_COMENTARIO - len(aviso)] + aviso
    call("event.acknowledge", {"eventids": [principal["eventid"]], "action": 4, "message": comentario},
         token=TOKEN_ANALISTA.read_text().strip())
    log.info("relatório publicado no evento %s (%s)", principal["eventid"], base.name)


class Correlador:
    """Junta eventos do mesmo host que chegam dentro da janela e entrega o lote para análise."""

    def __init__(self, fila):
        self.fila, self.lotes, self.trava = fila, {}, threading.Lock()

    def adicionar(self, evento):
        with self.trava:
            lote = self.lotes.get(evento["host"])
            if lote is None:
                lote = self.lotes[evento["host"]] = []
                threading.Timer(JANELA_CORRELACAO, self._fechar, [evento["host"]]).start()
            lote.append(evento)

    def _fechar(self, host):
        with self.trava:
            lote = self.lotes.pop(host, [])
        if lote:
            self.fila.put(lote)


def trabalhador(fila):
    """Processa um incidente por vez, aplicando cooldown por problema e teto de análises por hora."""
    ultimas, por_problema = [], {}
    while True:
        lote = fila.get()
        agora = time.time()
        lote = [e for e in lote if agora - por_problema.get((e["host"], e["nome"]), 0) > COOLDOWN_TRIGGER]
        if not lote:
            log.info("lote ignorado: problemas já analisados nos últimos %d min", COOLDOWN_TRIGGER // 60)
            continue
        ultimas[:] = [t for t in ultimas if agora - t < 3600]
        if len(ultimas) >= MAX_ANALISES_HORA:
            log.warning("teto de %d análises/hora atingido; lote descartado: %s", MAX_ANALISES_HORA,
                        [e["nome"] for e in lote])
            continue
        ultimas.append(agora)
        for e in lote:
            por_problema[(e["host"], e["nome"])] = agora
        log.info("analisando incidente em %s: %s", lote[0]["host"], [e["nome"] for e in lote])
        try:
            relatorio, meta = analisar(lote)
            log.info("análise concluída em %ss, %d+%d tokens, ferramentas: %s", meta["segundos"],
                     meta["tokens_entrada"], meta["tokens_saida"], meta["ferramentas"])
            publicar(lote, relatorio, meta)
        except Exception:
            log.exception("falha ao analisar o incidente")


def servir():
    fila = queue.Queue()
    correlador = Correlador(fila)
    threading.Thread(target=trabalhador, args=(fila,), daemon=True).start()

    class Receptor(BaseHTTPRequestHandler):
        def _responder(self, codigo, corpo):
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(corpo).encode())

        def do_GET(self):
            if self.path == "/saude":
                self._responder(200, {"ok": True, "provedor": provedor()})
            else:
                self._responder(404, {"erro": "rota inexistente"})

        def do_POST(self):
            if self.path != "/evento":
                return self._responder(404, {"erro": "rota inexistente"})
            try:
                evento = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                faltando = {"eventid", "host", "nome", "status"} - evento.keys()
                if faltando:
                    return self._responder(400, {"erro": f"campos ausentes: {sorted(faltando)}"})
            except (ValueError, json.JSONDecodeError):
                return self._responder(400, {"erro": "JSON inválido"})
            # Só problemas novos; recuperações e atualizações (inclusive o próprio comentário da IA) são ignoradas
            if evento["status"] == "PROBLEM" and evento.get("atualizacao") != "1":
                correlador.adicionar(evento)
                log.info("evento %s recebido: %s / %s", evento["eventid"], evento["host"], evento["nome"])
                return self._responder(202, {"aceito": True})
            return self._responder(202, {"aceito": False, "motivo": "não é abertura de problema"})

        def log_message(self, formato, *args):
            log.debug(formato, *args)

    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Receptor)
    log.info("Analista NOC ouvindo em 127.0.0.1:%d (provedor de IA: %s)", PORTA, provedor() or "NENHUMA CHAVE")
    servidor.serve_forever()


def simular(publicar_resultado):
    """Analisa agora o problema ativo mais grave do host da Filial, sem passar pelo webhook."""
    problemas = call("problem.get", {"hostids": ferramentas._host(config.HOST)["hostid"],
                                     "output": ["eventid", "name", "severity", "clock"],
                                     "sortfield": ["eventid"], "sortorder": "DESC"})
    if not problemas:
        raise SystemExit("Nenhum problema ativo no R-FILIAL para simular.")
    eventos = [{"eventid": p["eventid"], "host": config.HOST, "nome": p["name"], "status": "PROBLEM",
                "severidade": ferramentas.SEVERIDADES[int(p["severity"])], "severidade_num": p["severity"],
                "horario": ferramentas._hora(p["clock"])} for p in problemas]
    relatorio, meta = analisar(eventos)
    print(relatorio)
    print(f"\n--- {len(relatorio)} caracteres | {json.dumps(meta, ensure_ascii=False)}")
    if publicar_resultado:
        publicar(eventos, relatorio, meta)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = p.add_mutually_exclusive_group(required=True)
    modo.add_argument("--servico", action="store_true")
    modo.add_argument("--simular", action="store_true")
    p.add_argument("--publicar", action="store_true", help="com --simular: comenta no evento e dispara o e-mail")
    a = p.parse_args()
    servir() if a.servico else simular(a.publicar)
