"""Conexão com o SQLite do SennaGuard (usuários, sessões, chamados SG, preferências e afins)."""
import os
import sqlite3
from pathlib import Path

BANCO = Path(os.environ.get("SENNAGUARD_BANCO", Path(__file__).parent / "dados" / "sennaguard.db"))
# Fotos de perfil e anexos dos chamados (no servidor: /var/lib/sennaguard/arquivos, dentro do backup diário)
ARQUIVOS = Path(os.environ.get("SENNAGUARD_ARQUIVOS", BANCO.parent / "arquivos"))


def db():
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BANCO, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def coluna(con, tabela, nome, tipo):
    """Acrescenta a coluna se ainda não existir (migração simples de bancos antigos)."""
    if nome not in [c[1] for c in con.execute(f"pragma table_info({tabela})")]:
        con.execute(f"alter table {tabela} add column {nome} {tipo}")
