"""Senhas (scrypt), sessões em cookie HttpOnly e permissões por papel.

O token da sessão é aleatório e só o hash dele fica no banco: quem copiar o banco não consegue
se passar por ninguém. O cookie é SameSite=Strict, o que bloqueia CSRF vindo de outro site.
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, Response

COOKIE = "sg_sessao"
DURACAO = 12 * 3600  # um plantão
COOKIE_SEGURO = os.environ.get("COOKIE_SEGURO") == "1"  # 1 em produção (HTTPS pelo Apache)

# O que cada papel pode fazer. O cliente da Filial só vê o estado do enlace e os chamados.
# Quem abre chamado é o cliente; a equipe do NOC atende. Teste de failover derruba a fibra: só o Analista pede
# e só o Administrador aprova. Operador é o plantão (acompanha, reconhece alertas e atende chamados).
_EQUIPE = {"visao", "alertas", "reconhecer", "chamados", "atender_chamado", "equipamentos", "conhecimento", "chat"}
PERMISSOES = {
    "Administrador": _EQUIPE | {"usuarios", "relatorios", "manutencao", "backups", "testes", "aprovar_teste",
                                "editar_conhecimento"},
    "Analista": _EQUIPE | {"relatorios", "manutencao", "backups", "testes", "editar_conhecimento"},
    "Operador": set(_EQUIPE),
    "Cliente": {"visao", "chamados", "abrir_chamado", "conhecimento", "chat"},
}


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=2**14, r=8, p=1)
    return f"scrypt${sal.hex()}${h.hex()}"


def confere_senha(senha: str, guardado: str | None) -> bool:
    if not guardado:
        return False
    _, sal, h = guardado.split("$")
    return hmac.compare_digest(hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=2**14, r=8, p=1).hex(), h)


# Bloqueio contra tentativa e erro: 5 falhas em 5 min por IP+e-mail.
_falhas: dict[str, list[float]] = defaultdict(list)


def bloqueado(chave: str, limite: int = 5) -> bool:
    agora = time.time()
    _falhas[chave] = [t for t in _falhas[chave] if agora - t < 300]
    return len(_falhas[chave]) >= limite


def falhou(chave: str):
    _falhas[chave].append(time.time())


def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def derrubar_outras_sessoes(con: sqlite3.Connection, req: Request, uid: int):
    """Depois de trocar senha ou e-mail: só a sessão de quem trocou continua (um cookie roubado deixa de valer)."""
    con.execute("delete from sessoes where usuario_id=? and token_hash!=?", (uid, _th(req.cookies.get(COOKIE, ""))))


def abrir_sessao(con: sqlite3.Connection, resp: Response, uid: int, ip: str):
    token = secrets.token_urlsafe(32)
    con.execute("delete from sessoes where expira < ?", (int(time.time()),))
    con.execute("insert into sessoes (token_hash, usuario_id, expira, ip) values (?,?,?,?)",
                (_th(token), uid, int(time.time()) + DURACAO, ip))
    resp.set_cookie(COOKIE, token, max_age=DURACAO, httponly=True, samesite="strict", secure=COOKIE_SEGURO, path="/")


def fechar_sessao(con: sqlite3.Connection, req: Request, resp: Response):
    if token := req.cookies.get(COOKIE):
        con.execute("delete from sessoes where token_hash=?", (_th(token),))
    resp.delete_cookie(COOKIE, path="/")


def usuario_da_sessao(con: sqlite3.Connection, req: Request):
    token = req.cookies.get(COOKIE)
    if not token:
        return None
    r = con.execute("""select u.* from sessoes s join usuarios u on u.id = s.usuario_id
                       where s.token_hash=? and s.expira>? and u.ativo=1""", (_th(token), int(time.time()))).fetchone()
    return dict(r) if r else None


def exigir(permissao: str):
    """Dependência do FastAPI: 401 sem sessão, 403 se o papel não tem a permissão."""
    from banco import db

    def checar(req: Request):
        with db() as con:
            u = usuario_da_sessao(con, req)
        if not u:
            raise HTTPException(401, "Sessão expirada. Entre novamente.")
        if permissao not in PERMISSOES.get(u["papel"], set()):
            raise HTTPException(403, "Seu perfil não tem acesso a isso.")
        return u
    return Depends(checar)
