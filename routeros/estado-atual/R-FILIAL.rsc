# software id = C789-MW9G
#
# model = RB760iGS
# serial number = A36A0BA85CEF
/interface bridge add comment="Rede Interna Filial (192.168.20.0/24) - portas 3, 4 e 5" mtu=2000 name=bridge-LAN
/interface bridge add comment="Loopback /32 - identificacao e monitoramento" name=loopback
/interface ethernet set [ find default-name=ether1 ] comment="PAP Backup Radio (/29)" l2mtu=2026 mtu=2000 name=ether1-WAN-RADIO
/interface ethernet set [ find default-name=ether2 ] comment="Reserva (fibra no SFP)" l2mtu=2026 mtu=2000 name=ether2-reserva
/interface ethernet set [ find default-name=ether3 ] comment="Rede Interna Filial" l2mtu=2026 mtu=2000 name=ether3-LAN
/interface ethernet set [ find default-name=ether4 ] comment="Rede Interna Filial" l2mtu=2026 mtu=2000 name=ether4-LAN
/interface ethernet set [ find default-name=ether5 ] comment="Rede Interna Filial" l2mtu=2026 mtu=2000 name=ether5-LAN
/interface ethernet set [ find default-name=sfp1 ] comment="PAP Principal Fibra Optica (/30) - SFP" l2mtu=2026 mtu=2000 name=sfp1-WAN-FIBRA
/interface list add name=LAN_MGMT
/interface list add name=WAN_PUBLIC
/ip pool add name=pool-LAN ranges=192.168.20.100-192.168.20.199
/routing ospf instance add name=ospf-filial router-id=10.255.255.2
/routing ospf area add instance=ospf-filial name=area-0
/snmp community set [ find default=yes ] disabled=yes
/snmp community add addresses=192.168.10.50/32 name=public_senai
/system script add dont-require-permissions=no name=script_backup_automatico owner=*sys policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="/system backup save name=(\"backup_filial_\" . [/system clock get date])"
/interface bridge port add bridge=bridge-LAN interface=ether3-LAN
/interface bridge port add bridge=bridge-LAN interface=ether4-LAN
/interface bridge port add bridge=bridge-LAN interface=ether5-LAN
/ip neighbor discovery-settings set discover-interface-list=LAN_MGMT
/interface list member add interface=bridge-LAN list=LAN_MGMT
/interface list member add interface=sfp1-WAN-FIBRA list=WAN_PUBLIC
/interface list member add interface=ether1-WAN-RADIO list=WAN_PUBLIC
/ip address add address=10.255.255.2 comment="Loopback R-FILIAL" interface=loopback network=10.255.255.2
/ip address add address=192.168.20.1/24 comment="Gateway LAN Filial" interface=bridge-LAN network=192.168.20.0
/ip address add address=10.0.1.2/30 comment="PAP Fibra Filial" interface=sfp1-WAN-FIBRA network=10.0.1.0
/ip address add address=10.0.2.2/29 comment="PAP Radio Filial" interface=ether1-WAN-RADIO network=10.0.2.0
/ip dhcp-server add address-pool=pool-LAN interface=bridge-LAN lease-time=1h name=dhcp-LAN
/ip dhcp-server network add address=192.168.20.0/24 comment="LAN Filial" dns-server=192.168.10.1 gateway=192.168.20.1
/ip firewall address-list add address=192.168.10.0/24 list=REDES_AUTORIZADAS
/ip firewall address-list add address=192.168.20.0/24 list=REDES_AUTORIZADAS
/ip firewall filter add action=accept chain=input comment="NOC: Zabbix SNMP" dst-port=161 protocol=udp src-address=192.168.10.50
/ip firewall filter add action=accept chain=input comment="1. Aceitar conexoes estabelecidas e relacionadas" connection-state=established,related
/ip firewall filter add action=accept chain=input comment="NOC: Analista IA SSH (leitura)" dst-port=22 protocol=tcp src-address=192.168.10.50
/ip firewall filter add action=drop chain=input comment="2. Bloquear conexoes invalidas" connection-state=invalid
/ip firewall filter add action=accept chain=input comment="3. Permitir ICMP (Ping)" protocol=icmp
/ip firewall filter add action=accept chain=input comment="4. Permitir OSPF (Protocolo 89)" protocol=ospf
/ip firewall filter add action=accept chain=input comment="5. Acesso Gerencia (SSH e WinBox)" dst-port=22,8291 in-interface-list=LAN_MGMT protocol=tcp src-address-list=REDES_AUTORIZADAS
/ip firewall filter add action=accept chain=input comment="5b. Gerencia vinda da Matriz (SSH e WinBox)" dst-port=22,8291 protocol=tcp src-address=192.168.10.0/24
/ip firewall filter add action=drop chain=input comment="6. Bloquear restante"
/ip firewall filter add action=accept chain=forward connection-state=established,related
/ip firewall filter add action=drop chain=forward connection-state=invalid
/ip firewall filter add action=drop chain=forward comment="Filial nao gerencia as antenas" dst-address=10.0.2.0/29 protocol=!icmp src-address=192.168.20.0/24
/ip firewall filter add action=accept chain=forward comment="Filial -> Matriz" dst-address=192.168.10.0/24 src-address=192.168.20.0/24
/ip firewall filter add action=accept chain=forward comment="Matriz -> Filial" dst-address=192.168.20.0/24 src-address=192.168.10.0/24
/ip firewall filter add action=drop chain=forward in-interface-list=WAN_PUBLIC
/ip service set ftp disabled=yes
/ip service set ssh available-from=192.168.10.0/24,192.168.20.0/24
/ip service set telnet disabled=yes
/ip service set www disabled=yes
/ip service set reverse-proxy disabled=yes
/ip service set winbox available-from=192.168.10.0/24,192.168.20.0/24
/ip service set api disabled=yes
/ip service set api-ssl disabled=yes
/routing ospf interface-template add area=area-0 comment="PAP Fibra - Custo 10 (Prioritario)" cost=10 dead-interval=4s hello-interval=1s interfaces=sfp1-WAN-FIBRA type=ptp
/routing ospf interface-template add area=area-0 comment="PAP Radio - Custo 100 (Backup)" cost=100 dead-interval=4s hello-interval=1s interfaces=ether1-WAN-RADIO type=ptp
/routing ospf interface-template add area=area-0 comment="Anunciar LAN Filial sem enviar pacotes OSPF" interfaces=bridge-LAN passive
/routing ospf interface-template add area=area-0 comment="Anunciar loopback /32" interfaces=loopback passive
/snmp set contact="NOC SENAI TCC" enabled=yes location="Rack Filial"
/system clock set time-zone-name=America/Sao_Paulo
/system identity set name=R-FILIAL
/system ntp client set enabled=yes
/system ntp client servers add address=10.255.255.1
/system scheduler add !days interval=1d name=agendador_backup on-event=script_backup_automatico policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon start-date=2026-09-28 start-time=00:00:00
/tool bandwidth-server set enabled=no
/tool mac-server set allowed-interface-list=LAN_MGMT
/tool mac-server mac-winbox set allowed-interface-list=LAN_MGMT
/tool netwatch add comment="NOC: qualidade da fibra (troca para o radio se degradar)" down-script="/routing ospf interface-template set [find comment~\"PAP Fibra\"] cost=200; :log warning \"[NOC] FIBRA DEGRADADA ou CAIDA: trafego desviado para o RADIO\"" host=10.0.1.1 interval=10s packet-count=20 packet-interval=100ms thr-avg=30ms thr-loss-percent=10% type=icmp up-script="/routing ospf interface-template set [find comment~\"PAP Fibra\"] cost=10; :log warning \"[NOC] FIBRA OK: trafego de volta para a FIBRA\""
