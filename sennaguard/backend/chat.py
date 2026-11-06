"""Chat com a IA sobre a rede: perguntas em português respondidas com os dados do Zabbix e do SennaGuard.

Todas as ferramentas são somente leitura. O cliente da Filial recebe um conjunto menor (estado do enlace,
os próprios chamados, manutenções e a base de conhecimento), sem dados internos do NOC.
"""
import json
import time
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import atendimento
import auth
import conhecimento
import fonte
import ia
from banco import db

router = APIRouter()
_uso: dict[int, list[float]] = defaultdict(list)
LIMITE = 20  # perguntas por usuário a cada 10 min (custo e abuso)


def _h(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m %H:%M") if ts else "-"


def _ferramentas(u):
    def estado_enlace() -> str:
        """Estado atual da rede Matriz-Filial: caminho ativo (fibra ou rádio), latência e perda de cada enlace, último failover."""
        v = fonte.visao()
        f, r = v["enlaces"]["fibra"], v["enlaces"]["radio"]
        ult = v.get("ultimo_failover")
        return json.dumps({"caminho_ativo": v["caminho"], "fibra": {"no_ar": f["up"], "latencia_ms": f["latencia"]},
                           "radio": {"no_ar": r["up"], "latencia_ms": r["latencia"], "sinal_dbm": r.get("sinal")},
                           "ultimo_failover": {"quando": _h(ult["em"]), "segundos": ult["segundos"]} if ult else None}, ensure_ascii=False)

    def resumo_periodo(horas: int = 24) -> str:
        """Resumo de um período: disponibilidade da fibra e do rádio, quantas quedas da fibra e quanto tempo a rede ficou no rádio.

        Args:
            horas: Quantas horas para trás olhar (1 a 744). Ex.: 24 = hoje, 168 = semana, 720 = mês.
        """
        import relatorio
        horas = max(1, min(int(horas), 744))
        agora = int(time.time())
        m = relatorio.metricas(agora - horas * 3600, agora)
        return json.dumps({k: m[k] for k in ("disponibilidade", "latencia_media", "quedas_fibra", "tempo_no_radio", "alertas", "por_severidade", "mttr")}
                          | {"tempo_no_radio_min": round(m["tempo_no_radio"] / 60)}, ensure_ascii=False)

    def alertas_recentes(horas: int = 24) -> str:
        """Alertas do Zabbix no período, com severidade, início, fim e se ainda estão ativos.

        Args:
            horas: Quantas horas para trás (1 a 168).
        """
        lista = fonte.alertas(max(1, min(int(horas), 168)))
        return json.dumps([{"problema": a["nome"], "severidade": a["severidade"], "inicio": _h(a["inicio"]),
                            "fim": _h(a["fim"]) if a["fim"] else "ativo"} for a in lista[:30]], ensure_ascii=False)

    def chamados(apenas_abertos: bool = True) -> str:
        """Chamados abertos pelas pessoas (SG-xxx) com situação, prazo de SLA e responsável.

        Args:
            apenas_abertos: True para ver só os que ainda não foram resolvidos.
        """
        with db() as con:
            lista = atendimento.listar(con, u)
        if apenas_abertos:
            lista = [c for c in lista if c["status"] != "resolvido"]
        return json.dumps([{"numero": c["numero"], "titulo": c["titulo"], "situacao": c["status"], "aberto_em": _h(c["criado_em"]),
                            "prazo_solucao": _h(c["sla"]["solucao"]["prazo"]), "responsavel": c.get("responsavel_nome")} for c in lista[:20]],
                          ensure_ascii=False)

    def manutencoes() -> str:
        """Janelas de manutenção em andamento ou programadas."""
        with db() as con:
            rs = con.execute("select titulo, inicio, fim, descricao from manutencoes where cancelada_em is null and fim>? order by inicio",
                             (int(time.time()),)).fetchall()
        return json.dumps([{"titulo": r["titulo"], "inicio": _h(r["inicio"]), "fim": _h(r["fim"]), "aviso": r["descricao"]} for r in rs], ensure_ascii=False)

    def equipamentos() -> str:
        """Hosts monitorados (roteadores, switches, antenas, servidor) e se estão respondendo."""
        return json.dumps([{k: e.get(k) for k in ("nome", "tipo", "ip", "local", "up", "latencia", "sinal")} for e in fonte.equipamentos()], ensure_ascii=False)

    def buscar_solucao(assunto: str) -> str:
        """Procura na base de conhecimento do NOC soluções de problemas parecidos já resolvidos.

        Args:
            assunto: Palavras do problema, ex.: "internet lenta setor financeiro".
        """
        return json.dumps([{k: a[k] for k in ("titulo", "problema", "causa", "solucao")} for a in conhecimento.buscar(assunto, 3)], ensure_ascii=False)

    if u["papel"] == "Cliente":
        return [estado_enlace, chamados, manutencoes, buscar_solucao]
    return [estado_enlace, resumo_periodo, alertas_recentes, chamados, manutencoes, equipamentos, buscar_solucao]


def _system(u):
    base = (f"Você é o assistente do NOC SennaGuard (SENAI), que monitora o enlace Matriz-Filial: fibra principal (sfp1) e rádio "
            f"de backup (ether1, antenas Ubiquiti), com OSPF. Agora são {datetime.now():%d/%m/%Y %H:%M}. Responda em português do Brasil, "
            "curto e direto, com os números que as ferramentas devolverem. Use as ferramentas antes de afirmar qualquer dado; "
            "se um dado não existir, diga que não há esse dado. Nunca invente valores.")
    if u["papel"] == "Cliente":
        return base + (" Quem pergunta é um usuário da Filial: explique em linguagem simples, sem jargão técnico. "
                       "Se ele relatar um problema que não está resolvido, sugira abrir um chamado no painel.")
    return base + f" Quem pergunta é da equipe do NOC ({u['papel']}): pode usar termos técnicos."


class Mensagem(BaseModel):
    papel: str = Field(pattern="^(usuario|ia)$")
    texto: str = Field(min_length=1, max_length=4000)


class Conversa(BaseModel):
    mensagens: list[Mensagem] = Field(min_length=1, max_length=20)


@router.get("/api/chat/estado")
def estado(_=auth.exigir("chat")):
    return {"provedor": ia.provedor()}


@router.post("/api/chat")
def perguntar(c: Conversa, u=auth.exigir("chat")):
    if c.mensagens[-1].papel != "usuario":
        raise HTTPException(422, "A última mensagem precisa ser a pergunta.")
    agora = time.time()
    _uso[u["id"]] = [t for t in _uso[u["id"]] if agora - t < 600]
    if len(_uso[u["id"]]) >= LIMITE:
        raise HTTPException(429, "Muitas perguntas seguidas. Espere alguns minutos.")
    _uso[u["id"]].append(agora)
    try:
        resposta = ia.conversar(_system(u), [m.model_dump() for m in c.mensagens], _ferramentas(u))
    except ia.IaIndisponivel as e:
        raise HTTPException(503, str(e))
    return {"resposta": resposta or "Não consegui montar uma resposta. Tente perguntar de outro jeito.", "provedor": ia.provedor()}
