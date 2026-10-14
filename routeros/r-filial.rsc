# ====================================================================
# PROJETO SENAI REDE-CONECTIVIDADE - SCRIPT FILIAL
# EQUIPAMENTO: MikroTik RouterOS v7.4 ou superior (R-FILIAL)
# Revisão 14/10/2026 (reunião com a CTI): porta 1 = rádio, porta 2 = fibra, portas 3-5 = LAN em bridge,
# loopback /32 e troca automática para o rádio quando a fibra DEGRADA (não só quando cai).
# Senha substituída por <SENHA_ADMIN_FILIAL>. Depois, colar também routeros-r-filial-noc.rsc (integração com o NOC).
# ====================================================================

# 1. IDENTIFICAÇÃO
/system identity set name="R-FILIAL"

# 2. PORTAS
#    ether1 = rádio (backup) | ether2 = fibra (principal) | ether3, ether4, ether5 = rede local (bridge)
/interface set [find default-name=ether1] name="ether1-WAN-RADIO" comment="PAP Backup Radio (/29)" mtu=2000
/interface set [find default-name=ether2] name="ether2-WAN-FIBRA" comment="PAP Principal Fibra Optica (/30)" mtu=2000
/interface set [find default-name=ether3] name="ether3-LAN" comment="Rede Interna Filial" mtu=2000
/interface set [find default-name=ether4] name="ether4-LAN" comment="Rede Interna Filial" mtu=2000
/interface set [find default-name=ether5] name="ether5-LAN" comment="Rede Interna Filial" mtu=2000
/interface bridge add name="bridge-LAN" mtu=2000 comment="Rede Interna Filial (192.168.20.0/24) - portas 3, 4 e 5"
/interface bridge port add bridge=bridge-LAN interface=ether3-LAN
/interface bridge port add bridge=bridge-LAN interface=ether4-LAN
/interface bridge port add bridge=bridge-LAN interface=ether5-LAN

# 3. LOOPBACK /32: endereço fixo do roteador, alcançável pela fibra OU pelo rádio (router-id do OSPF)
/interface bridge add name="loopback" comment="Loopback /32 - identificacao e monitoramento"
/ip address add address=10.255.255.2/32 interface=loopback comment="Loopback R-FILIAL"

# 4. ENDEREÇAMENTO IP
/ip address add address=192.168.20.1/24 interface=bridge-LAN comment="Gateway LAN Filial"
/ip address add address=10.0.1.2/30 interface=ether2-WAN-FIBRA comment="PAP Fibra Filial"
/ip address add address=10.0.2.2/29 interface=ether1-WAN-RADIO comment="PAP Radio Filial"

# 5. USUÁRIOS
/user add name="admin_senai" group=full password="<SENHA_ADMIN_FILIAL>" comment="Usuario Administrativo"
/user disable admin

# 6. HARDENING DE SERVIÇOS
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
/ip service set api disabled=yes
/ip service set api-ssl disabled=yes
/ip service set www-ssl disabled=yes
/ip service set ssh port=22 address=192.168.10.0/24,192.168.20.0/24 disabled=no
/ip service set winbox address=192.168.10.0/24,192.168.20.0/24 disabled=no

# 7. DESCOBERTA DE VIZINHOS SÓ NA LAN
/interface list add name="LAN_MGMT"
/interface list add name="WAN_PUBLIC"
/interface list member add interface=bridge-LAN list=LAN_MGMT
/interface list member add interface=ether2-WAN-FIBRA list=WAN_PUBLIC
/interface list member add interface=ether1-WAN-RADIO list=WAN_PUBLIC
/ip neighbor discovery-settings set discover-interface-list=LAN_MGMT
/tool mac-server set allowed-interface-list=LAN_MGMT
/tool mac-server mac-winbox set allowed-interface-list=LAN_MGMT

# 8. OSPF v7: fibra custo 10 (preferida), rádio custo 100 (backup), LAN e loopback anunciadas
/routing ospf instance add name="ospf-filial" router-id=10.255.255.2
/routing ospf area add name="area-0" instance=ospf-filial area-id=0.0.0.0
/routing ospf interface-template add area=area-0 interfaces=ether2-WAN-FIBRA cost=10 type=ptp comment="PAP Fibra - Custo 10 (Prioritario)"
/routing ospf interface-template add area=area-0 interfaces=ether1-WAN-RADIO cost=100 type=ptp comment="PAP Radio - Custo 100 (Backup)"
/routing ospf interface-template add area=area-0 interfaces=bridge-LAN passive=yes comment="Anunciar LAN Filial sem enviar pacotes OSPF"
/routing ospf interface-template add area=area-0 interfaces=loopback passive=yes comment="Anunciar loopback /32"

# 9. FIREWALL STATEFUL
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
add chain=forward action=accept src-address=192.168.20.0/24 dst-address=192.168.10.0/24 comment="Filial -> Matriz"
add chain=forward action=accept src-address=192.168.10.0/24 dst-address=192.168.20.0/24 comment="Matriz -> Filial"
add chain=forward action=drop in-interface-list=WAN_PUBLIC

# 10. BACKUP AUTOMÁTICO
/system script add name="script_backup_automatico" source="/system backup save name=(\"backup_filial_\" . [/system clock get date])"
/system scheduler add name="agendador_backup" interval=1d start-time=00:00:00 on-event="script_backup_automatico"

# 11. QUALIDADE DA FIBRA -> TROCA AUTOMÁTICA PARA O RÁDIO (RouterOS 7.4+)
#     A cada 10 s, 20 pings para a ponta da Matriz na fibra. Se a média passar de 30 ms OU a perda passar
#     de 10%, a fibra é considerada degradada: o custo OSPF dela sobe para 200 (acima dos 100 do rádio) e
#     o tráfego vai para o rádio SEM a fibra cair. Quando a fibra volta a ficar boa, o custo volta a 10.
/tool netwatch add host=10.0.1.1 type=icmp interval=10s packet-count=20 packet-interval=100ms \
    thr-avg=30ms thr-loss-percent=10% comment="NOC: qualidade da fibra (troca para o radio se degradar)" \
    down-script="/routing ospf interface-template set [find comment~\"PAP Fibra\"] cost=200; :log warning \"[NOC] FIBRA DEGRADADA ou CAIDA: trafego desviado para o RADIO\"" \
    up-script="/routing ospf interface-template set [find comment~\"PAP Fibra\"] cost=10; :log warning \"[NOC] FIBRA OK: trafego de volta para a FIBRA\""
