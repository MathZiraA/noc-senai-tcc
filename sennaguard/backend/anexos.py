"""Anexos dos chamados SG: prints, fotos e PDFs (até 5 MB cada, 5 por mensagem).

O arquivo sobe antes da mensagem e fica "solto", visível só para quem enviou. Ao enviar a mensagem ele é
preso ao chamado e o SHA-256 dele entra no registro encadeado: trocar o arquivo depois quebra a prova.
O tipo é conferido pelos primeiros bytes, não pelo nome nem pelo que o navegador declarou.
"""
import hashlib
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

import atendimento
import auth
from banco import ARQUIVOS, db

LIMITE = 5 * 1024 * 1024
POR_MENSAGEM = 5
PASTA = ARQUIVOS / "anexos"
router = APIRouter()


def criar_tabelas(con):
    con.execute("""create table if not exists anexos (
        id integer primary key, chamado_id integer, seq integer, nome text not null, tipo text not null,
        tamanho integer not null, sha256 text not null, enviado_por integer not null, em integer not null)""")


def tipo_real(b: bytes):
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if b.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if b.startswith(b"%PDF-"):
        return "application/pdf"
    return None


async def ler_corpo(req: Request, limite: int) -> bytes:
    """Corpo cru da requisição, recusando antes de ler quando o tamanho declarado já passa do limite."""
    if int(req.headers.get("content-length") or 0) > limite:
        raise HTTPException(413, f"Arquivo maior que {limite // (1024 * 1024)} MB.")
    # Lê em blocos e para ao passar do limite: sem Content-Length (envio "chunked") o corpo inteiro iria para a memória
    corpo = bytearray()
    async for parte in req.stream():
        corpo += parte
        if len(corpo) > limite:
            raise HTTPException(413, f"Arquivo maior que {limite // (1024 * 1024)} MB.")
    corpo = bytes(corpo)
    if not corpo:
        raise HTTPException(400, "Arquivo vazio.")
    return corpo


def _limpar_soltos(con):
    """Anexos enviados há mais de 1 dia e nunca presos a uma mensagem."""
    for (aid,) in con.execute("select id from anexos where chamado_id is null and em < ?", (int(time.time()) - 86400,)).fetchall():
        (PASTA / str(aid)).unlink(missing_ok=True)
        con.execute("delete from anexos where id=?", (aid,))


@router.post("/api/anexos", status_code=201)
async def enviar(req: Request, nome: str = "arquivo", u=auth.exigir("chamados")):
    corpo = await ler_corpo(req, LIMITE)
    tipo = tipo_real(corpo)
    if not tipo:
        raise HTTPException(415, "Envie uma imagem (PNG, JPG ou WEBP) ou um PDF.")
    nome = (Path(nome).name or "arquivo")[:120]
    with db() as con:
        _limpar_soltos(con)
        # Cota: no máximo 20 anexos ainda não enviados por pessoa (impede encher o disco com uploads soltos)
        if con.execute("select count(*) from anexos where enviado_por=? and chamado_id is null", (u["id"],)).fetchone()[0] >= 20:
            raise HTTPException(429, "Muitos anexos esperando envio. Envie a mensagem ou aguarde e tente de novo.")
        aid = con.execute("insert into anexos (nome,tipo,tamanho,sha256,enviado_por,em) values (?,?,?,?,?,?)",
                          (nome, tipo, len(corpo), hashlib.sha256(corpo).hexdigest(), u["id"], int(time.time()))).lastrowid
        PASTA.mkdir(parents=True, exist_ok=True)
        (PASTA / str(aid)).write_bytes(corpo)
    return {"id": aid, "nome": nome, "tipo": tipo, "tamanho": len(corpo)}


def prender(con, ids, usuario, chamado_id):
    """Prende ao chamado os anexos soltos de `usuario`; devolve o que entra no registro (com o SHA-256)."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    if len(ids) > POR_MENSAGEM:
        raise HTTPException(422, f"No máximo {POR_MENSAGEM} anexos por mensagem.")
    linhas = con.execute(f"""select id, nome, tipo, tamanho, sha256 from anexos
                             where enviado_por=? and chamado_id is null and id in ({','.join('?' * len(ids))})""",
                         [usuario["id"], *ids]).fetchall()
    if len(linhas) != len(ids):
        raise HTTPException(422, "Um dos anexos não foi encontrado. Envie o arquivo de novo.")
    con.execute(f"update anexos set chamado_id=? where id in ({','.join('?' * len(ids))})", [chamado_id, *ids])
    return [dict(r) for r in linhas]


@router.get("/api/anexos/{aid}")
def baixar(aid: int, u=auth.exigir("chamados")):
    with db() as con:
        a = con.execute("select * from anexos where id=?", (aid,)).fetchone()
        visivel = a and (a["enviado_por"] == u["id"] if a["chamado_id"] is None
                         else atendimento.visivel(con, a["chamado_id"], u, a["seq"]))
    if not visivel or not (PASTA / str(aid)).is_file():
        raise HTTPException(404, "Anexo não encontrado.")
    imagem = a["tipo"].startswith("image/")
    # Imagem abre no navegador; PDF baixa. "sandbox" impede que um arquivo enviado rode qualquer coisa no painel.
    return FileResponse(PASTA / str(aid), media_type=a["tipo"], filename=a["nome"],
                        content_disposition_type="inline" if imagem else "attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox",
                                 "Cache-Control": "private, max-age=86400"})
