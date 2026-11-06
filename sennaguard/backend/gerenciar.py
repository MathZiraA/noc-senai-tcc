"""Tarefas de administração pela linha de comando (usadas pelo instalador).

Uso:  python gerenciar.py criar-admin --nome "Fulano" --email fulano@x.com   (pede a senha sem mostrar)
      python gerenciar.py redefinir-senha --email fulano@x.com
"""
import argparse
import getpass
import sys
import time

import auth
import main


def _senha():
    s = getpass.getpass("Senha (mínimo 8): ")
    if len(s) < 8 or s != getpass.getpass("Repita a senha: "):
        sys.exit("Senha curta ou não confere.")
    return auth.hash_senha(s)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("acao", choices=["criar-admin", "redefinir-senha"])
    p.add_argument("--nome", default="Administrador NOC")
    p.add_argument("--email", required=True)
    a = p.parse_args()
    main.iniciar()
    with main.db() as con:
        existe = con.execute("select id from usuarios where lower(email)=?", (a.email.lower(),)).fetchone()
        if a.acao == "criar-admin":
            if existe:
                sys.exit(f"{a.email} já existe. Use redefinir-senha.")
            con.execute("insert into usuarios (nome,email,papel,ativo,alerta_email,chamado_email,criado_em,senha_hash) values (?,?,?,?,?,?,?,?)",
                        (a.nome, a.email, "Administrador", 1, 1, 1, int(time.time()), _senha()))
        else:
            if not existe:
                sys.exit(f"{a.email} não existe.")
            con.execute("update usuarios set senha_hash=?, ativo=1 where id=?", (_senha(), existe["id"]))
            con.execute("delete from sessoes where usuario_id=?", (existe["id"],))
    print("Pronto.")
