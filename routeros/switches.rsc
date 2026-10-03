# ====================================================================
# SWITCHES GERENCIÁVEIS (opcional: com switch não gerenciável, nada a configurar)
# Transcrito do documento da topologia. Senhas substituídas por placeholders.
# ====================================================================

# ---------------- SW-MATRIZ ----------------
/system identity set name="SW-MATRIZ"
/interface bridge add name="bridge1" mtu=2000
/interface bridge port add bridge=bridge1 interface=ether1 comment="Conexão com R-MATRIZ"
/interface bridge port add bridge=bridge1 interface=ether2 comment="Estação de Trabalho PC-MATRIZ-01"
/interface bridge port add bridge=bridge1 interface=ether3 comment="Estação de Trabalho PC-MATRIZ-02"
/ip address add address=192.168.10.2/24 interface=bridge1 comment="IP Gerência SW-MATRIZ"
/ip route add gateway=192.168.10.1
/user add name="admin_senai" group=full password="<SENHA_ADMIN_MATRIZ>"
/user disable admin
# Observação: o notebook com a VM do Zabbix (192.168.10.50) vai em uma porta livre desta bridge.

# ---------------- SW-FILIAL ----------------
/system identity set name="SW-FILIAL"
/interface bridge add name="bridge1" mtu=2000
/interface bridge port add bridge=bridge1 interface=ether1 comment="Conexão com R-FILIAL"
/interface bridge port add bridge=bridge1 interface=ether2 comment="Estação de Trabalho PC-FILIAL-01"
/interface bridge port add bridge=bridge1 interface=ether3 comment="Estação de Trabalho PC-FILIAL-02"
/ip address add address=192.168.20.2/24 interface=bridge1 comment="IP Gerência SW-FILIAL"
/ip route add gateway=192.168.20.1
/user add name="admin_senai" group=full password="<SENHA_ADMIN_FILIAL>"
/user disable admin
