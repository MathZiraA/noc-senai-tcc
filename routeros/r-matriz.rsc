# ====================================================================
# PROJETO SENAI REDE-CONECTIVIDADE - SCRIPT MATRIZ
# EQUIPAMENTO: MikroTik RouterOS v7 (R-MATRIZ)
# Transcrito do documento da topologia. Senha substituída por <SENHA_ADMIN_MATRIZ>.
# ====================================================================

# 1. IDENTIFICAÇÃO E NOMEAÇÃO DO SISTEMA
/system identity set name="R-MATRIZ"

# 2. IDENTIFICAÇÃO DAS INTERFACES
/interface set [find default-name=ether1] name="ether1-LAN" comment="Rede Interna Matriz (192.168.10.0/24)"
/interface set [find default-name=ether2] name="ether2-WAN-FIBRA" comment="PAP Principal Fibra Optica (/30)"
/interface set [find default-name=ether3] name="ether3-WAN-RADIO" comment="PAP Backup Radio (/29)"

# 3. CONFIGURAÇÃO DE MTU DE 2000 BYTES (SUPORTE A JUMBO FRAMES)
/interface set ether1-LAN mtu=2000
/interface set ether2-WAN-FIBRA mtu=2000
/interface set ether3-WAN-RADIO mtu=2000

# 4. PLANO DE ENDEREÇAMENTO IP
/ip address add address=192.168.10.1/24 interface=ether1-LAN comment="Gateway LAN Matriz"
/ip address add address=10.0.1.1/30 interface=ether2-WAN-FIBRA comment="PAP Fibra Matriz"
/ip address add address=10.0.2.1/29 interface=ether3-WAN-RADIO comment="PAP Radio Matriz"

# 5. GERENCIAMENTO DE USUÁRIOS E SENHAS SEGURAS
/user add name="admin_senai" group=full password="<SENHA_ADMIN_MATRIZ>" comment="Usuario Administrativo"
/user disable admin

# 6. HARDENING DE SERVIÇOS E RESTRIÇÃO DE ACESSO
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
/ip service set api disabled=yes
/ip service set api-ssl disabled=yes
/ip service set www-ssl disabled=yes

/ip service set ssh port=22 address=192.168.10.0/24,192.168.20.0/24 disabled=no
/ip service set winbox address=192.168.10.0/24,192.168.20.0/24 disabled=no

# 7. DESATIVAR DESCOBERTA DE VIZINHOS (MNDP) NAS WANS
/interface list add name="LAN_MGMT"
/interface list add name="WAN_PUBLIC"
/interface list member add interface=ether1-LAN list=LAN_MGMT
/interface list member add interface=ether2-WAN-FIBRA list=WAN_PUBLIC
/interface list member add interface=ether3-WAN-RADIO list=WAN_PUBLIC

/ip neighbor discovery-settings set discover-interface-list=LAN_MGMT
/tool mac-server set allowed-interface-list=LAN_MGMT
/tool mac-server mac-winbox set allowed-interface-list=LAN_MGMT

# 8. ROUTING OSPF V7 COM CUSTOS DE PRIORIDADE
/routing ospf instance add name="ospf-matriz" router-id=1.1.1.1
/routing ospf area add name="area-0" instance=ospf-matriz area-id=0.0.0.0

/routing ospf interface-template add area=area-0 interfaces=ether2-WAN-FIBRA cost=10 type=ptp comment="PAP Fibra - Custo 10 (Prioritario)"
/routing ospf interface-template add area=area-0 interfaces=ether3-WAN-RADIO cost=100 type=ptp comment="PAP Radio - Custo 100 (Backup)"
/routing ospf interface-template add area=area-0 interfaces=ether1-LAN passive=yes comment="Anunciar LAN Matriz sem enviar pacotes OSPF"

# 9. FIREWALL STATEFUL COM PROTEÇÃO E LIBERAÇÃO DO OSPF
/ip firewall filter
add chain=input action=accept connection-state=established,related comment="1. Aceitar conexoes estabelecidas e relacionadas"
add chain=input action=drop connection-state=invalid comment="2. Bloquear conexoes invalidas"
add chain=input action=accept protocol=icmp comment="3. Permitir ICMP (Ping)"
add chain=input action=accept protocol=ospf comment="4. Permitir OSPF (Protocolo 89)"
add chain=input action=accept src-address-list=REDES_AUTORIZADAS in-interface-list=LAN_MGMT comment="5. Acesso Gerencia"
add chain=input action=drop comment="6. Bloquear restante"

/ip firewall address-list add list=REDES_AUTORIZADAS address=192.168.10.0/24
/ip firewall address-list add list=REDES_AUTORIZADAS address=192.168.20.0/24

/ip firewall filter
add chain=forward action=accept connection-state=established,related
add chain=forward action=drop connection-state=invalid
add chain=forward action=accept src-address=192.168.10.0/24 dst-address=192.168.20.0/24 comment="Matriz -> Filial"
add chain=forward action=accept src-address=192.168.20.0/24 dst-address=192.168.10.0/24 comment="Filial -> Matriz"
add chain=forward action=drop in-interface-list=WAN_PUBLIC

# 10. BACKUP AUTOMÁTICO E NETWATCH
/system script add name="script_backup_automatico" source="/system backup save name=(\"backup_matriz_\" . [/system clock get date])"
/system scheduler add name="agendador_backup" interval=1d start-time=00:00:00 on-event="script_backup_automatico"

# Aspas internas escapadas (no documento original estavam sem escape e o comando falharia)
/tool netwatch add host=10.0.1.2 interval=5s timeout=2s \
    up-script=":log warning \"[ALERTA OSPF] Link FIBRA RESTABELECIDO!\"" \
    down-script=":log error \"[ALERTA OSPF] Link FIBRA CAIU! Comutando para RADIO...\""
