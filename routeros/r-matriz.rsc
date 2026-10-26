# ====================================================================
# PROJETO SENAI REDE-CONECTIVIDADE - SCRIPT MATRIZ
# EQUIPAMENTO: MikroTik RouterOS v7.4 ou superior (R-MATRIZ)
# Revisão 14/10/2026 (reunião com a CTI + montagem real): porta 1 = rádio, sfp1 = fibra, portas 3-5 = LAN em bridge,
# loopback /32 e troca automática para o rádio quando a fibra DEGRADA (não só quando cai).
# Senha substituída por <SENHA_ADMIN_MATRIZ>.
# ====================================================================

# 1. IDENTIFICAÇÃO
/system identity set name="R-MATRIZ"

# 2. PORTAS
#    ether1 = rádio (backup) | sfp1 = fibra óptica (principal, módulo SFP) | ether3, ether4, ether5 = rede local (bridge)
#    ether2 = internet da escola (DHCP + NAT): só para o servidor do NOC instalar pacotes, enviar e-mail e usar a IA
# hEX S (RB760iGS): o MTU nao pode passar do L2MTU (1596 de fabrica). 2026 e o maximo do chip.
/interface ethernet set [find where default-name~"ether"] l2mtu=2026
/interface set [find default-name=ether1] name="ether1-WAN-RADIO" comment="PAP Backup Radio (/29)" mtu=2000
/interface set [find default-name=ether2] name="ether2-INTERNET" comment="Internet da escola (DHCP)" mtu=2000
/interface ethernet set [find default-name=sfp1] name="sfp1-WAN-FIBRA" comment="PAP Principal Fibra Optica (/30) - SFP" l2mtu=2026 mtu=2000
/interface set [find default-name=ether3] name="ether3-LAN" comment="Rede Interna Matriz" mtu=2000
/interface set [find default-name=ether4] name="ether4-LAN" comment="Rede Interna Matriz" mtu=2000
/interface set [find default-name=ether5] name="ether5-LAN" comment="Rede Interna Matriz" mtu=2000
/interface bridge add name="bridge-LAN" mtu=2000 comment="Rede Interna Matriz (192.168.10.0/24) - portas 3, 4 e 5"
/interface bridge port add bridge=bridge-LAN interface=ether3-LAN
/interface bridge port add bridge=bridge-LAN interface=ether4-LAN
/interface bridge port add bridge=bridge-LAN interface=ether5-LAN

# 3. LOOPBACK /32: endereço fixo do roteador, alcançável pela fibra OU pelo rádio (router-id do OSPF)
/interface bridge add name="loopback" comment="Loopback /32 - identificacao e monitoramento"
/ip address add address=10.255.255.1/32 interface=loopback comment="Loopback R-MATRIZ"

# 4. ENDEREÇAMENTO IP
/ip address add address=192.168.10.1/24 interface=bridge-LAN comment="Gateway LAN Matriz"
/ip address add address=10.0.1.1/30 interface=sfp1-WAN-FIBRA comment="PAP Fibra Matriz"
/ip address add address=10.0.2.1/29 interface=ether1-WAN-RADIO comment="PAP Radio Matriz"

# 4b. DHCP NA LAN: notebooks e PCs pegam IP sozinhos (.100 a .199). IPs fixos ficam fora da faixa:
#     roteador .1, switch .2, PCs do projeto .10, servidor Zabbix .50
/ip pool add name=pool-LAN ranges=192.168.10.100-192.168.10.199
/ip dhcp-server add name=dhcp-LAN interface=bridge-LAN address-pool=pool-LAN lease-time=1h disabled=no
# Opção 121 (rotas sem classe): os PCs aprendem que as redes do projeto vão pelo cabo e o resto (internet)
# pelo Wi-Fi deles; sem isso o Windows manda os pacotes para a outra unidade pelo Wi-Fi
/ip dhcp-server option add name=rotas-projeto code=121 value=0x18c0a814c0a80a01080ac0a80a01
/ip dhcp-server network add address=192.168.10.0/24 gateway=192.168.10.1 dns-server=192.168.10.1 dhcp-option=rotas-projeto comment="LAN Matriz"

# 4c. INTERNET (ether2): IP da rede da escola por DHCP, NAT para a Matriz e a Filial, DNS para a LAN.
#     A rede do projeto funciona sem isto; o servidor do NOC precisa (pacotes, e-mail e IA).
/ip dhcp-client add interface=ether2-INTERNET add-default-route=yes use-peer-dns=yes comment="Internet da escola"
/ip firewall nat add chain=srcnat out-interface=ether2-INTERNET action=masquerade comment="NAT: Matriz e Filial para a internet"
/ip dns set allow-remote-requests=yes

# 5. USUÁRIOS
/user add name="admin_senai" group=full password="<SENHA_ADMIN_MATRIZ>" comment="Usuario Administrativo"
/user disable admin

# 6. HARDENING DE SERVIÇOS
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
/ip service set api disabled=yes
/ip service set api-ssl disabled=yes
/ip service set www-ssl disabled=yes
# A Matriz gerencia tudo; a Filial não gerencia a Matriz
/ip service set ssh port=22 address=192.168.10.0/24 disabled=no
/ip service set winbox address=192.168.10.0/24 disabled=no
# Serviços que vêm ligados no RouterOS 7 e não são usados (pedido da CTI: só o necessário)
/ip service set reverse-proxy disabled=yes
/tool bandwidth-server set enabled=no

# 7. DESCOBERTA DE VIZINHOS SÓ NA LAN
/interface list add name="LAN_MGMT"
/interface list add name="WAN_PUBLIC"
/interface list member add interface=bridge-LAN list=LAN_MGMT
/interface list member add interface=sfp1-WAN-FIBRA list=WAN_PUBLIC
/interface list member add interface=ether2-INTERNET list=WAN_PUBLIC
/interface list member add interface=ether1-WAN-RADIO list=WAN_PUBLIC
/ip neighbor discovery-settings set discover-interface-list=LAN_MGMT
/tool mac-server set allowed-interface-list=LAN_MGMT
/tool mac-server mac-winbox set allowed-interface-list=LAN_MGMT

# 8. OSPF v7: fibra custo 10 (preferida), rádio custo 100 (backup), LAN e loopback anunciadas
/routing ospf instance add name="ospf-matriz" router-id=10.255.255.1 originate-default=if-installed
/routing ospf area add name="area-0" instance=ospf-matriz area-id=0.0.0.0
/routing ospf interface-template add area=area-0 interfaces=sfp1-WAN-FIBRA cost=10 type=ptp comment="PAP Fibra - Custo 10 (Prioritario)"
/routing ospf interface-template add area=area-0 interfaces=ether1-WAN-RADIO cost=100 type=ptp comment="PAP Radio - Custo 100 (Backup)"
/routing ospf interface-template add area=area-0 interfaces=bridge-LAN passive comment="Anunciar LAN Matriz sem enviar pacotes OSPF"
/routing ospf interface-template add area=area-0 interfaces=loopback passive comment="Anunciar loopback /32"

# 9. FIREWALL STATEFUL
/ip firewall filter
add chain=input action=accept connection-state=established,related comment="1. Aceitar conexoes estabelecidas e relacionadas"
add chain=input action=drop connection-state=invalid comment="2. Bloquear conexoes invalidas"
add chain=input action=accept protocol=icmp comment="3. Permitir ICMP (Ping)"
add chain=input action=accept protocol=ospf comment="4. Permitir OSPF (Protocolo 89)"
add chain=input action=accept protocol=tcp dst-port=22,8291 src-address-list=REDES_AUTORIZADAS in-interface-list=LAN_MGMT comment="5. Acesso Gerencia (SSH e WinBox)"
add chain=input action=accept protocol=udp dst-port=53 in-interface-list=LAN_MGMT comment="5c. DNS para a rede local"
add chain=input action=accept protocol=tcp dst-port=53 in-interface-list=LAN_MGMT comment="5c. DNS para a rede local (TCP)"
add chain=input action=accept protocol=udp dst-port=53 src-address=192.168.20.0/24 comment="5d. DNS para a LAN da Filial"
add chain=input action=accept protocol=tcp dst-port=53 src-address=192.168.20.0/24 comment="5d. DNS para a LAN da Filial (TCP)"
add chain=input action=accept protocol=udp dst-port=123 src-address=10.0.0.0/8 comment="5e. NTP para o R-FILIAL (fibra, radio e loopback)"
add chain=input action=drop comment="6. Bloquear restante"
/ip firewall address-list add list=REDES_AUTORIZADAS address=192.168.10.0/24
/ip firewall address-list add list=REDES_AUTORIZADAS address=192.168.20.0/24
/ip firewall filter
add chain=forward action=accept connection-state=established,related
add chain=forward action=drop connection-state=invalid
add chain=forward action=accept src-address=192.168.10.0/24 dst-address=192.168.20.0/24 comment="Matriz -> Filial"
add chain=forward action=accept src-address=192.168.20.0/24 dst-address=192.168.10.0/24 comment="Filial -> Matriz"
add chain=forward action=accept src-address=192.168.20.0/24 out-interface=ether2-INTERNET comment="Filial -> internet"
add chain=forward action=drop in-interface-list=WAN_PUBLIC

# 9b. HORA CERTA (NTP): pega do ntp.br e serve para o R-FILIAL
/system clock set time-zone-name=America/Sao_Paulo
/system ntp client set enabled=yes servers=a.ntp.br,b.ntp.br,c.ntp.br
/system ntp server set enabled=yes

# 10. BACKUP AUTOMÁTICO
/system script add name="script_backup_automatico" source="/system backup save name=(\"backup_matriz_\" . [/system clock get date])"
/system scheduler add name="agendador_backup" interval=1d start-time=00:00:00 on-event="script_backup_automatico"

# 11. QUALIDADE DA FIBRA -> TROCA AUTOMÁTICA PARA O RÁDIO (RouterOS 7.4+)
#     A cada 10 s, 20 pings para a ponta da Filial na fibra. Se a média passar de 30 ms OU a perda passar
#     de 10%, a fibra é considerada degradada: o custo OSPF dela sobe para 200 (acima dos 100 do rádio) e
#     o tráfego vai para o rádio SEM a fibra cair. Quando a fibra volta a ficar boa, o custo volta a 10.
/tool netwatch add host=10.0.1.2 type=icmp interval=10s packet-count=20 packet-interval=100ms \
    thr-avg=30ms thr-loss-percent=10% comment="NOC: qualidade da fibra (troca para o radio se degradar)" \
    down-script="/routing ospf interface-template set [find comment~\"PAP Fibra\"] cost=200; :log warning \"[NOC] FIBRA DEGRADADA ou CAIDA: trafego desviado para o RADIO\"" \
    up-script="/routing ospf interface-template set [find comment~\"PAP Fibra\"] cost=10; :log warning \"[NOC] FIBRA OK: trafego de volta para a FIBRA\""
