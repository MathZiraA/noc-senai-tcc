"""Configuração do NOC, lida de /etc/noc/noc.conf (linhas CHAVE=VALOR, o mesmo formato que o bash lê).

Tudo o que muda de uma rede para outra fica no arquivo; sem ele, valem os padrões do protótipo do TCC.
Senhas e tokens NUNCA vão neste arquivo: ficam em /root/.zabbix_token, /root/.gemini_key etc.
"""
from pathlib import Path

ARQUIVO = Path("/etc/noc/noc.conf")
PADRAO = {
    # Servidor do NOC
    "SERVIDOR_IP": "192.168.10.50",          # IP do servidor na LAN da Matriz (SNMP/SSH dos roteadores liberam este IP)
    "SERVIDOR_IPS_EXTRAS": "192.168.137.50",  # outros IPs pelos quais o servidor é acessado (vão no certificado)
    "SERVIDOR_NOME": "noc.senai.local",
    # Rede
    "GRUPO": "Rede SENAI - Equipamentos",
    "HOST_FILIAL": "R-FILIAL",
    "NOME_FILIAL": "R-FILIAL (RouterOS Filial SENAI)",
    "REDE_MATRIZ": "192.168.10.0/24",
    "GW_MATRIZ": "192.168.10.1",
    "REDE_FILIAL": "192.168.20.0/24",
    "LAN_FILIAL": "192.168.20.1",             # IP do R-FILIAL na LAN: coleta SNMP e alcance a cada 1 s
    "REDE_FIBRA": "10.0.1.0/30",
    "FIBRA_MATRIZ": "10.0.1.1",
    "FIBRA_FILIAL": "10.0.1.2",
    "REDE_RADIO": "10.0.2.0/29",
    "RADIO_MATRIZ": "10.0.2.1",
    "RADIO_FILIAL": "10.0.2.2",
    "ANTENA_MATRIZ": "10.0.2.3",
    "ANTENA_FILIAL": "10.0.2.4",
    "SNMP_COMMUNITY": "public_senai",
    # E-mail (a senha de app fica só dentro do Zabbix)
    "EMAIL": "matheus.ziravello@aluno.senai.br",
    "SMTP_SERVIDOR": "smtp.gmail.com",
    "SMTP_PORTA": "587",
    "FUSO": "America/Sao_Paulo",
}


def _ler():
    if not ARQUIVO.exists():
        return {}
    valores = {}
    for linha in ARQUIVO.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


C = {**PADRAO, **_ler()}

SERVIDOR_IP = C["SERVIDOR_IP"]
SERVIDOR_IPS = [SERVIDOR_IP] + [ip.strip() for ip in C["SERVIDOR_IPS_EXTRAS"].split(",") if ip.strip()]
GRUPO, HOST = C["GRUPO"], C["HOST_FILIAL"]
LAN_FILIAL, FIBRA_FILIAL, RADIO_FILIAL = C["LAN_FILIAL"], C["FIBRA_FILIAL"], C["RADIO_FILIAL"]

# Chaves dos itens criados por fix_redundancia.py (usadas por todos os outros scripts)
K_FIBRA = f"icmpping[{FIBRA_FILIAL},3,,,500]"
K_RADIO = f"icmpping[{RADIO_FILIAL},3,,,500]"
K_LAT_FIBRA = f"icmppingsec[{FIBRA_FILIAL},3,,,500]"
K_LAT_RADIO = f"icmppingsec[{RADIO_FILIAL},3,,,500]"
K_PERDA_FIBRA = f"icmppingloss[{FIBRA_FILIAL},3,,,500]"
K_PERDA_RADIO = f"icmppingloss[{RADIO_FILIAL},3,,,500]"
K_LAN = f"icmpping[{LAN_FILIAL},1,,,300]"
K_CAMINHO = "noc.caminho_ativo"
K_FAILOVER = "noc.failover.segundos"


def url(caminho=""):
    """Endereço web do NOC para mensagens e documentação."""
    return f"https://{SERVIDOR_IPS[-1] if len(SERVIDOR_IPS) > 1 else SERVIDOR_IP}{caminho}"
