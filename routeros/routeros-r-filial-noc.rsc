# ====================================================================
# R-FILIAL - integração com o NOC (Zabbix + Analista IA)
# Colar no terminal do R-FILIAL DEPOIS do script principal da Filial.
# 192.168.10.50 = IP do servidor Zabbix (o instalador e o gerador da bancada trocam pelo IP do noc.conf).
# O IP vai escrito em cada linha: variáveis :local somem entre linhas coladas no terminal.
# ====================================================================

# 1. SNMP v2c somente leitura, só para o Zabbix
#    (security=none é obrigatório para v2c; "private" exige SNMPv3)
/snmp community set [find default=yes] disabled=yes
/snmp community add name=public_senai addresses=192.168.10.50/32 security=none read-access=yes write-access=no
/snmp set enabled=yes contact="NOC SENAI TCC" location="Rack Filial"

# 2. Firewall: liberar SNMP e SSH apenas para o Zabbix (antes do drop final)
/ip firewall filter add chain=input action=accept protocol=udp dst-port=161 src-address=192.168.10.50 comment="NOC: Zabbix SNMP"
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=22 src-address=192.168.10.50 comment="NOC: Analista IA SSH (leitura)"
/ip firewall filter move [find comment="NOC: Zabbix SNMP"] destination=0
/ip firewall filter move [find comment="NOC: Analista IA SSH (leitura)"] destination=1

# 3. Usuário SOMENTE LEITURA para o Analista IA, com login por chave
#    Troque a senha abaixo por uma senha forte sua (com chave cadastrada,
#    o RouterOS bloqueia login por senha desse usuário por padrão).
/user add name=zabbix-ia group=read password="TROQUE_POR_UMA_SENHA_FORTE" comment="Analista IA - somente leitura"
/user ssh-keys add user=zabbix-ia key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ6p8g/oAtn3KK0x8Tze43LoZ5JZ6vePhG3ihVcCquum noc-analista@zabbix"
# Se a linha acima der erro na sua versão do RouterOS: envie o arquivo noc-analista.pub ao roteador
# (Winbox > Files) e use:  /user ssh-keys import public-key-file=noc-analista.pub user=zabbix-ia
