"""Chamados abertos pelas pessoas (cliente da Filial ou equipe), numerados SG-<n>.

Cada passo (abertura, comentário, nota interna, mudança de status) entra em `chamado_registros`, encadeado
por SHA-256 como o livro dos chamados automáticos: alterar ou apagar um registro quebra a cadeia.
"Nota" é a mensagem interna da equipe: o cliente não vê e ela não conta como primeira resposta no SLA.
"""
import hashlib
import json
import sqlite3
import time

from banco import coluna

STATUS = ("aberto", "em_atendimento", "resolvido")
CATEGORIAS = ("sem_acesso", "lentidao", "instavel", "outro")
IMPACTOS = ("um_pc", "setor", "filial")
IMPACTOS_NOME = {"um_pc": "um computador", "setor": "um setor", "filial": "a Filial inteira"}
# SLA 24x7 (padrão NOC): (primeira resposta, solução) em segundos, por quem é afetado
PRAZOS = {"filial": (15 * 60, 4 * 3600), "setor": (30 * 60, 8 * 3600), "um_pc": (3600, 24 * 3600)}


def criar_tabelas(con: sqlite3.Connection):
    con.execute("""create table if not exists chamados_manuais (
        id integer primary key, titulo text not null, descricao text not null, categoria text not null,
        impacto text not null, status text not null default 'aberto', contexto text,
        aberto_por integer not null, responsavel integer, criado_em integer not null, atualizado_em integer not null)""")
    con.execute("""create table if not exists chamado_registros (
        seq integer primary key, chamado_id integer not null, acao text not null, autor_id integer,
        autor_nome text, autor_papel text, texto text, em integer not null, hash_anterior text not null, hash text not null)""")
    coluna(con, "chamado_registros", "anexos", "text")
    # "Visto às": até qual registro cada pessoa já leu, e quando
    con.execute("""create table if not exists chamado_vistos (
        chamado_id integer not null, usuario_id integer not null, nome text, lado text not null, seq integer not null, em integer not null)""")


def _hash(anterior, registro):
    corpo = json.dumps(registro, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((anterior + corpo).encode()).hexdigest()


def registrar(con, chamado_id, acao, autor, texto="", anexos=None):
    ultimo = con.execute("select hash from chamado_registros order by seq desc limit 1").fetchone()
    anterior = ultimo[0] if ultimo else "0" * 64
    seq = (con.execute("select coalesce(max(seq), 0) from chamado_registros").fetchone()[0]) + 1
    r = {"seq": seq, "chamado_id": chamado_id, "acao": acao, "autor_id": autor["id"], "autor_nome": autor["nome"],
         "autor_papel": autor["papel"], "texto": texto, "em": int(time.time())}
    if anexos:  # só entra no hash quando existe: os registros antigos continuam batendo
        r["anexos"] = anexos
    h = _hash(anterior, r)
    con.execute("""insert into chamado_registros (seq,chamado_id,acao,autor_id,autor_nome,autor_papel,texto,em,hash_anterior,hash,anexos)
                   values (?,?,?,?,?,?,?,?,?,?,?)""",
                (seq, chamado_id, acao, autor["id"], autor["nome"], autor["papel"], texto, r["em"], anterior, h,
                 json.dumps(anexos, ensure_ascii=False) if anexos else None))
    if anexos:
        con.execute(f"update anexos set seq=? where id in ({','.join('?' * len(anexos))})", [seq, *[a["id"] for a in anexos]])
    con.execute("update chamados_manuais set atualizado_em=? where id=?", (r["em"], chamado_id))
    return seq


def verificar(con):
    anterior, n = "0" * 64, 0
    for row in con.execute("select * from chamado_registros order by seq"):
        r = dict(row)
        n += 1
        if anexos := r.pop("anexos", None):
            r["anexos"] = json.loads(anexos)
        if r.pop("hash_anterior") != anterior:
            return {"ok": False, "registros": n, "quebra": r["seq"], "motivo": "registro fora de ordem ou apagado"}
        h = r.pop("hash")
        if _hash(anterior, r) != h:
            return {"ok": False, "registros": n, "quebra": r["seq"], "motivo": "conteúdo alterado depois de gravado"}
        anterior = h
    return {"ok": True, "registros": n, "quebra": None, "motivo": ""}


def contexto_do_enlace(v: dict) -> str:
    """Foto do enlace na hora da abertura: o NOC vê de onde partir sem perguntar ao cliente."""
    f, r = v["enlaces"]["fibra"], v["enlaces"]["radio"]
    ms = lambda e: f"{e['latencia']:.1f} ms".replace(".", ",") if e.get("latencia") is not None else "sem resposta"
    return json.dumps({"caminho": v["caminho"], "fibra_up": f["up"], "radio_up": r["up"],
                       "fibra_ms": ms(f), "radio_ms": ms(r)}, ensure_ascii=False)


def _publico(row):
    c = dict(row)
    c["numero"] = f"SG-{c['id']}"
    c["contexto"] = json.loads(c["contexto"]) if c.get("contexto") else None
    return c


def _com_sla(con, chamados):
    """Prazo de primeira resposta e de solução (24x7). `em` = quando foi cumprido; None = ainda correndo."""
    marcos = {r[0]: (r[1], r[2]) for r in con.execute("""
        select chamado_id,
               min(case when autor_papel != 'Cliente' and acao in ('comentario', 'em_atendimento', 'resolvido') then em end),
               max(case when acao = 'resolvido' then em end)
        from chamado_registros group by chamado_id""")}
    for c in chamados:
        p1, p2 = PRAZOS[c["impacto"]]
        resposta, resolvido = marcos.get(c["id"], (None, None))
        c["sla"] = {"resposta": {"prazo": c["criado_em"] + p1, "em": resposta},
                    "solucao": {"prazo": c["criado_em"] + p2, "em": resolvido if c["status"] == "resolvido" else None}}
    return chamados


def listar(con, usuario):
    q = """select c.*, u.nome as aberto_por_nome, r.nome as responsavel_nome from chamados_manuais c
           left join usuarios u on u.id = c.aberto_por left join usuarios r on r.id = c.responsavel"""
    if usuario["papel"] == "Cliente":  # o cliente só vê os que ele abriu
        return _com_sla(con, [_publico(r) for r in con.execute(q + " where c.aberto_por=? order by c.atualizado_em desc", (usuario["id"],))])
    return _com_sla(con, [_publico(r) for r in con.execute(q + " order by (c.status='resolvido'), c.atualizado_em desc")])


def visivel(con, cid, usuario, seq=None):
    """O usuário pode ver o chamado (e, se `seq` vier, aquele registro)? Cliente: só os dele e sem notas internas."""
    if usuario["papel"] != "Cliente":
        return True
    dono = con.execute("select 1 from chamados_manuais where id=? and aberto_por=?", (cid, usuario["id"])).fetchone()
    if not dono or seq is None:
        return bool(dono)
    return not con.execute("select 1 from chamado_registros where seq=? and acao='nota'", (seq,)).fetchone()


def _lado(usuario):
    return "cliente" if usuario["papel"] == "Cliente" else "equipe"


def marcar_visto(con, cid, usuario):
    """Grava que o usuário leu até o último registro que ele enxerga. True se avançou (avisa o outro lado)."""
    nota = " and acao != 'nota'" if usuario["papel"] == "Cliente" else ""
    ultimo = con.execute(f"select max(seq) from chamado_registros where chamado_id=?{nota}", (cid,)).fetchone()[0]
    lido = con.execute("select max(seq) from chamado_vistos where chamado_id=? and usuario_id=?", (cid, usuario["id"])).fetchone()[0]
    if ultimo is None or (lido is not None and lido >= ultimo):
        return False
    con.execute("insert into chamado_vistos values (?,?,?,?,?,?)", (cid, usuario["id"], usuario["nome"], _lado(usuario), ultimo, int(time.time())))
    return True


def detalhe(con, cid, usuario):
    c = next((x for x in listar(con, usuario) if x["id"] == cid), None)
    if not c:
        return None
    nota = " and acao != 'nota'" if usuario["papel"] == "Cliente" else ""
    vistos = con.execute("select lado, seq, em, nome from chamado_vistos where chamado_id=? order by em", (cid,)).fetchall()
    c["registros"] = []
    for row in con.execute(f"select seq, acao, autor_nome, autor_papel, texto, em, hash, anexos from chamado_registros where chamado_id=?{nota} order by seq", (cid,)):
        r = dict(row)
        r["anexos"] = [{k: a[k] for k in ("id", "nome", "tipo", "tamanho")} for a in json.loads(r["anexos"])] if r["anexos"] else []
        # Mensagem visível ao outro lado: quando ele leu pela primeira vez (cliente ⇄ equipe)
        outro = "equipe" if r["autor_papel"] == "Cliente" else "cliente"
        v = next((v for v in vistos if v["lado"] == outro and v["seq"] >= r["seq"]), None) if r["acao"] in ("abertura", "comentario") else None
        r["visto"] = {"em": v["em"], "por": v["nome"]} if v else None
        c["registros"].append(r)
    return c
