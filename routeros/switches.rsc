# ====================================================================
# SWITCHES GERENCIÁVEIS MIKROTIK (RouterOS v7) - SW-MATRIZ e SW-FILIAL
# Revisão 19/10/2026: mesmo padrão dos roteadores (MTU 2000, só SSH/WinBox, SNMP para o Zabbix,
# a Matriz gerencia tudo e a Filial não gerencia a Matriz). Senhas substituídas por placeholders.
# Para switch MikroTik com SwOS (linha CSS) ou switch não gerenciável, este arquivo não se aplica.
# Aplicar num switch de fábrica: bancada\gerar_configs.py (responda "s" nos switches) e
#   bancada\enviar_mikrotik.ps1 -Equipamento SW-MATRIZ   (ou SW-FILIAL)
# A porta 1 do switch liga numa porta de LAN do roteador (3, 4 ou 5); as demais são para os PCs.
# ====================================================================

# ---------------- SW-MATRIZ ----------------
# 1. IDENTIFICAÇÃO
/system identity set name="SW-MATRIZ"

# 2. PORTAS: todas na mesma bridge (switch puro). O L2MTU máximo muda conforme o modelo: tenta 2026 e,
#    se o chip não aceitar, mantém o de fábrica.
:do { /interface ethernet set [find] l2mtu=2026 } on-error={ :log warning "SW: L2MTU 2026 nao suportado" }
:do { /interface ethernet set [find] mtu=2000 } on-error={ :log warning "SW: MTU 2000 nao suportado" }
/interface bridge add name="bridge-SW" mtu=2000 comment="Switch da Matriz (192.168.10.0/24)"
:foreach i in=[/interface ethernet find] do={ /interface bridge port add bridge=bridge-SW interface=$i }
/interface ethernet set [find default-name=ether1] comment="Uplink: R-MATRIZ (porta 3, 4 ou 5 do roteador)"

# 3. GERÊNCIA: IP fixo fora da faixa do DHCP (.100 a .199). O switch não distribui IP: quem faz isso é o R-MATRIZ.
/ip address add address=192.168.10.2/24 interface=bridge-SW comment="IP Gerencia SW-MATRIZ"
/ip route add gateway=192.168.10.1 comment="Gateway: R-MATRIZ"

# 4. USUÁRIOS
/user add name="admin_senai" group=full password="<SENHA_ADMIN_MATRIZ>" comment="Usuario Administrativo"
/user disable admin

# 5. SERVIÇOS: só SSH e WinBox, só da rede da Matriz (pedido da CTI)
/ip service set telnet,ftp,www,www-ssl,api,api-ssl disabled=yes
:do { /ip service set reverse-proxy disabled=yes } on-error={}
/ip service set ssh,winbox address=192.168.10.0/24 disabled=no
/tool bandwidth-server set enabled=no

# 6. SNMP somente leitura para o Zabbix (192.168.10.50)
/snmp community set [find default=yes] disabled=yes
/snmp community add name=public_senai addresses=192.168.10.50/32 security=none read-access=yes write-access=no
/snmp set enabled=yes contact="NOC SENAI TCC" location="Rack Matriz"

# 7. FIREWALL DO PRÓPRIO SWITCH (só protege a gerência; o tráfego dos PCs passa pela bridge sem ser filtrado)
/ip firewall filter
add chain=input action=accept connection-state=established,related comment="1. Aceitar conexoes estabelecidas"
add chain=input action=drop connection-state=invalid comment="2. Bloquear conexoes invalidas"
add chain=input action=accept protocol=icmp comment="3. Permitir ICMP (Ping)"
add chain=input action=accept protocol=udp dst-port=161 src-address=192.168.10.50 comment="4. SNMP do Zabbix"
add chain=input action=accept protocol=tcp dst-port=22,8291 src-address=192.168.10.0/24 comment="5. Gerencia (SSH e WinBox) da Matriz"
add chain=input action=drop comment="6. Bloquear restante"

# 8. BACKUP AUTOMÁTICO
/system script add name="script_backup_automatico" source="/system backup save name=(\"backup_sw_matriz_\" . [/system clock get date])"
/system scheduler add name="agendador_backup" interval=1d start-time=00:00:00 on-event="script_backup_automatico"

# ---------------- SW-FILIAL ----------------
# 1. IDENTIFICAÇÃO
/system identity set name="SW-FILIAL"

# 2. PORTAS: todas na mesma bridge (switch puro)
:do { /interface ethernet set [find] l2mtu=2026 } on-error={ :log warning "SW: L2MTU 2026 nao suportado" }
:do { /interface ethernet set [find] mtu=2000 } on-error={ :log warning "SW: MTU 2000 nao suportado" }
/interface bridge add name="bridge-SW" mtu=2000 comment="Switch da Filial (192.168.20.0/24)"
:foreach i in=[/interface ethernet find] do={ /interface bridge port add bridge=bridge-SW interface=$i }
/interface ethernet set [find default-name=ether1] comment="Uplink: R-FILIAL (porta 3, 4 ou 5 do roteador)"

# 3. GERÊNCIA
/ip address add address=192.168.20.2/24 interface=bridge-SW comment="IP Gerencia SW-FILIAL"
/ip route add gateway=192.168.20.1 comment="Gateway: R-FILIAL"

# 4. USUÁRIOS
/user add name="admin_senai" group=full password="<SENHA_ADMIN_FILIAL>" comment="Usuario Administrativo"
/user disable admin

# 5. SERVIÇOS: só SSH e WinBox, da rede da Filial e da Matriz (a Matriz gerencia tudo)
/ip service set telnet,ftp,www,www-ssl,api,api-ssl disabled=yes
:do { /ip service set reverse-proxy disabled=yes } on-error={}
/ip service set ssh,winbox address=192.168.10.0/24,192.168.20.0/24 disabled=no
/tool bandwidth-server set enabled=no

# 6. SNMP somente leitura para o Zabbix (192.168.10.50)
/snmp community set [find default=yes] disabled=yes
/snmp community add name=public_senai addresses=192.168.10.50/32 security=none read-access=yes write-access=no
/snmp set enabled=yes contact="NOC SENAI TCC" location="Rack Filial"

# 7. FIREWALL DO PRÓPRIO SWITCH
/ip firewall filter
add chain=input action=accept connection-state=established,related comment="1. Aceitar conexoes estabelecidas"
add chain=input action=drop connection-state=invalid comment="2. Bloquear conexoes invalidas"
add chain=input action=accept protocol=icmp comment="3. Permitir ICMP (Ping)"
add chain=input action=accept protocol=udp dst-port=161 src-address=192.168.10.50 comment="4. SNMP do Zabbix"
add chain=input action=accept protocol=tcp dst-port=22,8291 src-address=192.168.10.0/24 comment="5. Gerencia (SSH e WinBox) da Matriz"
add chain=input action=accept protocol=tcp dst-port=22,8291 src-address=192.168.20.0/24 comment="5b. Gerencia local da Filial"
add chain=input action=drop comment="6. Bloquear restante"

# 8. BACKUP AUTOMÁTICO
/system script add name="script_backup_automatico" source="/system backup save name=(\"backup_sw_filial_\" . [/system clock get date])"
/system scheduler add name="agendador_backup" interval=1d start-time=00:00:00 on-event="script_backup_automatico"
