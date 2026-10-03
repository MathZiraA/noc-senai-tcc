"""Provedor Google Gemini (camada gratuita do Google AI Studio) para o Analista NOC."""
import logging
import time
from pathlib import Path

from google import genai
from google.genai import errors, types

CHAVE = Path("/root/.gemini_key")
# Aliases da camada gratuita, em ordem de preferência (versões fixas antigas saem do ar).
# A camada gratuita costuma responder 503/429 em horário de pico: aí tenta o próximo.
MODELOS = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]
TENTATIVAS_POR_MODELO = 2

log = logging.getLogger("analista")


def disponivel():
    return CHAVE.exists()


def analisar(system, pedido, funcoes):
    """Tenta cada modelo da lista até um responder. Retorna (relatorio, metadados)."""
    cliente = genai.Client(api_key=CHAVE.read_text().strip())
    ultimo_erro = None
    for modelo in MODELOS:
        for tentativa in range(TENTATIVAS_POR_MODELO):
            try:
                return _analisar(cliente, modelo, system, pedido, funcoes)
            except errors.APIError as e:
                if e.code not in (429, 500, 503):
                    raise
                ultimo_erro = e
                log.warning("Gemini %s indisponível (%s), tentativa %d", modelo, e.code, tentativa + 1)
                time.sleep(10)
    raise RuntimeError(f"todos os modelos Gemini indisponíveis no momento: {ultimo_erro}")


def _analisar(cliente, modelo, system, pedido, funcoes):
    """Roda a investigação com chamada automática das funções Python."""
    inicio = time.time()
    chat = cliente.chats.create(
        model=modelo,
        config=types.GenerateContentConfig(
            system_instruction=system,
            tools=funcoes,
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=15),
        ),
    )
    resp = chat.send_message(pedido)
    texto = (resp.text or "").strip()
    if not texto:
        motivo = resp.candidates[0].finish_reason if resp.candidates else "sem candidatos"
        raise RuntimeError(f"resposta sem texto ({motivo})")
    chamadas = [f"{p.function_call.name}({dict(p.function_call.args or {})})"
                for c in chat.get_history() for p in (c.parts or []) if p.function_call]
    uso = resp.usage_metadata
    return texto, {"modelo": resp.model_version or modelo, "segundos": round(time.time() - inicio, 1),
                   "tokens_entrada": uso.prompt_token_count if uso else 0,
                   "tokens_saida": uso.candidates_token_count if uso else 0, "ferramentas": chamadas}
