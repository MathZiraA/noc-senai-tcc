# software id = 17PU-3DM5
#
# model = RB760iGS
# serial number = A8150A2D04C1
/interface bridge add comment="Rede Interna Matriz (192.168.10.0/24) - portas 3 e 5" mtu=2000 name=bridge-LAN
/interface bridge add comment="Loopback /32 - identificacao e monitoramento" name=loopback
/interface ethernet set [ find default-name=ether1 ] comment="PAP Backup Radio (/29)" l2mtu=2026 mtu=2000 name=ether1-WAN-RADIO
/interface ethernet set [ find default-name=ether2 ] comment="LINK VIVO (principal, DHCP)" l2mtu=2026 mtu=2000 name=ether2-INTERNET
/interface ethernet set [ find default-name=ether3 ] comment="Rede Interna Matriz" l2mtu=2026 mtu=2000 name=ether3-LAN
/interface ethernet set [ find default-name=ether4 ] comment="LINK TIN (backup, DHCP)" l2mtu=2026 mtu=2000 name=ether4-TIN
/interface ethernet set [ find default-name=ether5 ] comment="Rede Interna Matriz" l2mtu=2026 mtu=2000 name=ether5-LAN
/interface ethernet set [ find default-name=sfp1 ] comment="PAP Principal Fibra Optica (/30) - SFP" l2mtu=2026 mtu=2000 name=sfp1-WAN-FIBRA
/interface list add name=LAN_MGMT
/interface list add name=WAN_PUBLIC
/ip dhcp-server option add code=121 name=rotas-projeto value=0x18c0a814c0a80a01080ac0a80a01
/ip pool add name=pool-LAN ranges=192.168.10.100-192.168.10.199
/ip dhcp-server add address-pool=pool-LAN interface=bridge-LAN lease-time=1h name=dhcp-LAN
/routing ospf instance add name=ospf-matriz originate-default=if-installed router-id=10.255.255.1
/routing ospf area add instance=ospf-matriz name=area-0
/snmp community set [ find default=yes ] disabled=yes
/snmp community add addresses=192.168.10.50/32 name=public_senai
/system script add dont-require-permissions=no name=script_backup_automatico owner=*sys policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="/system backup save name=(\"backup_matriz_\" . [/system clock get date])"
/user group add comment="SennaGuard: teste de failover" name=sennaguard-teste policy=ssh,read,write,policy,test,!local,!telnet,!ftp,!reboot,!winbox,!password,!web,!sniff,!sensitive,!api,!romon,!rest-api
/interface bridge port add bridge=bridge-LAN interface=ether3-LAN
/interface bridge port add bridge=bridge-LAN interface=ether5-LAN
/ip neighbor discovery-settings set discover-interface-list=LAN_MGMT
/interface list member add interface=bridge-LAN list=LAN_MGMT
/interface list member add interface=sfp1-WAN-FIBRA list=WAN_PUBLIC
/interface list member add interface=ether1-WAN-RADIO list=WAN_PUBLIC
/interface list member add interface=ether2-INTERNET list=WAN_PUBLIC
/interface list member add interface=ether4-TIN list=WAN_PUBLIC
/ip address add address=10.255.255.1 comment="Loopback R-MATRIZ" interface=loopback network=10.255.255.1
/ip address add address=192.168.10.1/24 comment="Gateway LAN Matriz" interface=bridge-LAN network=192.168.10.0
/ip address add address=10.0.1.1/30 comment="PAP Fibra Matriz" interface=sfp1-WAN-FIBRA network=10.0.1.0
/ip address add address=10.0.2.1/29 comment="PAP Radio Matriz" interface=ether1-WAN-RADIO network=10.0.2.0
/ip dhcp-client add add-default-route=no comment="LINK VIVO" interface=ether2-INTERNET name=client1 script=":if (\$bound=1) do={/ip route set [find comment=\"DEF-VIVO\"] gateway=(\$\"gateway-address\" . \"%ether2-INTERNET\"); /ip route set [find comment=\"MON-VIVO\"] gateway=(\$\"gateway-address\" . \"%ether2-INTERNET\")}"
/ip dhcp-client add add-default-route=no comment="LINK TIN" interface=ether4-TIN name=client2 script=":if (\$bound=1) do={/ip route set [find comment=\"DEF-TIN\"] gateway=(\$\"gateway-address\" . \"%ether4-TIN\"); /ip route set [find comment=\"MON-TIN\"] gateway=(\$\"gateway-address\" . \"%ether4-TIN\")}" use-peer-dns=no
/ip dhcp-server network add address=192.168.10.0/24 comment="LAN Matriz" dhcp-option=rotas-projeto dns-server=192.168.10.1 gateway=192.168.10.1
/ip dns set allow-remote-requests=yes
/ip firewall address-list add address=192.168.10.0/24 list=REDES_AUTORIZADAS
/ip firewall address-list add address=192.168.20.0/24 list=REDES_AUTORIZADAS
/ip firewall filter add action=accept chain=input comment="NOC: Zabbix SNMP" dst-port=161 protocol=udp src-address=192.168.10.50
/ip firewall filter add action=accept chain=input comment="1. Aceitar conexoes estabelecidas e relacionadas" connection-state=established,related
/ip firewall filter add action=drop chain=input comment="2. Bloquear conexoes invalidas" connection-state=invalid
/ip firewall filter add action=accept chain=input comment="3. Permitir ICMP (Ping)" protocol=icmp
/ip firewall filter add action=accept chain=input comment="4. Permitir OSPF (Protocolo 89)" protocol=ospf
/ip firewall filter add action=accept chain=input comment="5. Acesso Gerencia (SSH e WinBox)" dst-port=22,8291 in-interface-list=LAN_MGMT protocol=tcp src-address-list=REDES_AUTORIZADAS
/ip firewall filter add action=accept chain=input comment="5c. DNS para a rede local" dst-port=53 in-interface-list=LAN_MGMT protocol=udp
/ip firewall filter add action=accept chain=input comment="5c. DNS para a rede local (TCP)" dst-port=53 in-interface-list=LAN_MGMT protocol=tcp
/ip firewall filter add action=accept chain=input comment="5d. DNS para a LAN da Filial" dst-port=53 protocol=udp src-address=192.168.20.0/24
/ip firewall filter add action=accept chain=input comment="5d. DNS para a LAN da Filial (TCP)" dst-port=53 protocol=tcp src-address=192.168.20.0/24
/ip firewall filter add action=accept chain=input comment="5e. NTP para o R-FILIAL (fibra, radio e loopback)" dst-port=123 protocol=udp src-address=10.0.0.0/8
/ip firewall filter add action=drop chain=input comment="6. Bloquear restante"
/ip firewall filter add action=accept chain=forward connection-state=established,related
/ip firewall filter add action=drop chain=forward connection-state=invalid
/ip firewall filter add action=accept chain=forward comment="Matriz -> Filial" dst-address=192.168.20.0/24 src-address=192.168.10.0/24
/ip firewall filter add action=accept chain=forward comment="Filial -> Matriz" dst-address=192.168.10.0/24 src-address=192.168.20.0/24
/ip firewall filter add action=accept chain=forward comment="Filial -> internet (TIN)" out-interface=ether4-TIN src-address=192.168.20.0/24
/ip firewall filter add action=accept chain=forward comment="Filial -> internet" out-interface=ether2-INTERNET src-address=192.168.20.0/24
/ip firewall filter add action=drop chain=forward in-interface-list=WAN_PUBLIC
/ip firewall nat add action=masquerade chain=srcnat comment="NAT: Matriz e Filial para a internet" out-interface=ether2-INTERNET
/ip firewall nat add action=masquerade chain=srcnat comment="NAT: Matriz e Filial pelo LINK TIN" out-interface=ether4-TIN
/ip route add comment=DEF-VIVO disabled=no distance=1 dst-address=0.0.0.0/0 gateway=172.16.31.254%ether2-INTERNET
/ip route add comment=DEF-TIN disabled=no distance=2 dst-address=0.0.0.0/0 gateway=172.16.31.254%ether4-TIN
/ip route add comment=MON-VIVO distance=1 dst-address=1.0.0.1/32 gateway=172.16.31.254%ether2-INTERNET
/ip route add comment=MON-TIN distance=1 dst-address=9.9.9.9/32 gateway=172.16.31.254%ether4-TIN
/ip route add blackhole comment="MON-VIVO trava" distance=250 dst-address=1.0.0.1/32
/ip route add blackhole comment="MON-TIN trava" distance=250 dst-address=9.9.9.9/32
/ip service set ftp disabled=yes
/ip service set ssh available-from=192.168.10.0/24
/ip service set telnet disabled=yes
/ip service set www disabled=yes
/ip service set reverse-proxy disabled=yes
/ip service set winbox available-from=192.168.10.0/24
/ip service set api disabled=yes
/ip service set api-ssl disabled=yes
/routing ospf interface-template add area=area-0 comment="PAP Fibra - Custo 10 (Prioritario)" cost=10 dead-interval=4s hello-interval=1s interfaces=sfp1-WAN-FIBRA type=ptp
/routing ospf interface-template add area=area-0 comment="PAP Radio - Custo 100 (Backup)" cost=100 dead-interval=4s hello-interval=1s interfaces=ether1-WAN-RADIO type=ptp
/routing ospf interface-template add area=area-0 comment="Anunciar LAN Matriz sem enviar pacotes OSPF" interfaces=bridge-LAN passive
/routing ospf interface-template add area=area-0 comment="Anunciar loopback /32" interfaces=loopback passive
/snmp set contact="NOC SENAI TCC" enabled=yes location="Rack Matriz"
/system clock set time-zone-name=America/Sao_Paulo
/system identity set name=R-MATRIZ
/system ntp client set enabled=yes
/system ntp server set enabled=yes
/system ntp client servers add address=a.ntp.br
/system ntp client servers add address=b.ntp.br
/system ntp client servers add address=c.ntp.br
/system scheduler add !days interval=1d name=agendador_backup on-event=script_backup_automatico policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon start-date=2026-09-28 start-time=00:00:00
/tool bandwidth-server set enabled=no
/tool mac-server set allowed-interface-list=LAN_MGMT
/tool mac-server mac-winbox set allowed-interface-list=LAN_MGMT
/tool netwatch add comment="NOC: qualidade da fibra (troca para o radio se degradar)" down-script="/routing ospf interface-template set [find comment~\"PAP Fibra\"] cost=200; :log warning \"[NOC] FIBRA DEGRADADA ou CAIDA: trafego desviado para o RADIO\"" host=10.0.1.2 interval=10s packet-count=20 packet-interval=100ms thr-avg=30ms thr-loss-percent=10% type=icmp up-script="/routing ospf interface-template set [find comment~\"PAP Fibra\"] cost=10; :log warning \"[NOC] FIBRA OK: trafego de volta para a FIBRA\""
/tool netwatch add comment="NOC: LINK VIVO" down-script="/ip route set [find comment=\"DEF-VIVO\"] disabled=yes; /ip firewall connection remove [find]; :log warning \"[NOC] LINK VIVO CAIU: internet pelo LINK TIN\"" host=1.0.0.1 interval=5s packet-count=5 packet-interval=200ms thr-loss-percent=60% type=icmp up-script="/ip route set [find comment=\"DEF-VIVO\"] disabled=no; /ip firewall connection remove [find]; :log warning \"[NOC] LINK VIVO OK: internet de volta para a VIVO\""
/tool netwatch add comment="NOC: LINK TIN" down-script="/ip route set [find comment=\"DEF-TIN\"] disabled=yes; :log warning \"[NOC] LINK TIN CAIU\"" host=9.9.9.9 interval=5s packet-count=5 packet-interval=200ms thr-loss-percent=60% type=icmp up-script="/ip route set [find comment=\"DEF-TIN\"] disabled=no; :log warning \"[NOC] LINK TIN OK\""
