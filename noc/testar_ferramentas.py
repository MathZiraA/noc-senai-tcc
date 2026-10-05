"""Roda cada ferramenta uma vez contra o Zabbix real e mostra a saída (não chama a IA)."""
import json

import config
import ferramentas as f

HOST = config.HOST
print(f.estado_atual(HOST), "\n====")
print(f.historico_item(HOST, "Enlace FIBRA", 30), "\n====")
print(f.historico_item(HOST, "latência", 30), "\n====")
print(f.eventos_recentes(HOST, 24), "\n====")
print(f.listar_itens(HOST)[:1200], "\n====")
print(f.consultar_mikrotik("rotas"), "\n====")
print(json.dumps(f.TODAS[4].to_dict(), ensure_ascii=False, indent=1))
