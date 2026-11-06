"""Atualização em tempo real por Server-Sent Events.

Cada canal (visao, alertas, chamados, manutencao…) tem um número de versão. Quem muda um dado chama
`avisar(canal)`; cada navegador conectado em /api/eventos recebe o nome do canal e recarrega só aquilo.
SSE passa pelo Apache como uma resposta HTTP comum, sem WebSocket.
"""
import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

import auth

VERSOES: dict[str, int] = {}
router = APIRouter()


def avisar(*canais: str):
    for c in canais:
        VERSOES[c] = VERSOES.get(c, 0) + 1


@router.get("/api/eventos")
async def eventos(request: Request, _=auth.exigir("visao")):
    async def fluxo():
        visto = dict(VERSOES)
        yield "retry: 5000\n\n"
        ociosos = 0
        while not await request.is_disconnected():
            mudou = False
            for canal, versao in list(VERSOES.items()):
                if visto.get(canal) != versao:
                    visto[canal] = versao
                    mudou = True
                    yield f"event: {canal}\ndata: {versao}\n\n"
            ociosos = 0 if mudou else ociosos + 1
            if ociosos >= 15:  # comentário a cada 15 s mantém a conexão viva no Apache
                ociosos = 0
                yield ": ping\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(fluxo(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
