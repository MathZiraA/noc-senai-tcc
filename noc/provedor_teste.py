"""Provedor de TESTE: roda as ferramentas de verdade, mas monta o relatório sem IA.
Ativado só quando existe /root/noc/MODO_TESTE — serve para validar o fluxo Zabbix -> e-mail."""
import time
from pathlib import Path

FLAG = Path("/root/noc/MODO_TESTE")


def disponivel():
    return FLAG.exists()


def analisar(system, pedido, funcoes):
    inicio = time.time()
    host = pedido.splitlines()[0].removeprefix("Host: ").strip()
    por_nome = {f.__name__: f for f in funcoes}
    estado = por_nome["estado_atual"](host)
    eventos = por_nome["eventos_recentes"](host, 1)
    relatorio = ("RESUMO: TESTE DE INTEGRAÇÃO do Analista NOC (nenhuma IA foi chamada).\n"
                 "Se este texto chegou por e-mail, o caminho Zabbix -> webhook -> analista -> comentário -> "
                 "e-mail está funcionando.\n\n"
                 f"DADOS COLETADOS PELAS FERRAMENTAS:\n{estado}\n\n{eventos}")
    return relatorio, {"modelo": "teste-sem-ia", "segundos": round(time.time() - inicio, 1), "tokens_entrada": 0,
                       "tokens_saida": 0, "ferramentas": ["estado_atual", "eventos_recentes"]}
