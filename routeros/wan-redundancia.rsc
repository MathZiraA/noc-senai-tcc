# ====================================================================
# R-MATRIZ — Redundância WAN: LINK VIVO (principal, ether2) + LINK TIN (backup, ether4)
#   - Os dois links pegam IP por DHCP. A rota padrão vai pela VIVO (distância 1) e pelo TIN (distância 2).
#   - A cada 5 s o roteador pinga um IP de teste por link, preso àquele link (rota /32 + blackhole):
#       VIVO -> 1.0.0.1 (Cloudflare; a rede da escola bloqueia ping ao OpenDNS)   TIN -> 9.9.9.9 (Quad9)
#     Se a VIVO perde 60% dos pings, a rota dela é desligada e tudo sai pelo TIN (~5-10 s).
#     Quando a VIVO volta a responder, a rota é religada e a internet volta para ela sozinha.
#   - Matriz e Filial (pela fibra ou rádio) herdam o failover: o NAT sai pelos dois links.
#   - SNMP só leitura para o servidor do NOC (igual ao R-FILIAL).
# Cole no terminal do WinBox do R-MATRIZ. O cabo do TIN vai na ether4.
# ====================================================================

# 1. ether4 sai da LAN e vira o LINK TIN
/interface bridge port remove [find interface="ether4-LAN"]
/interface list member remove [find interface="ether4-LAN"]
/interface set [find default-name=ether4] name="ether4-TIN" comment="LINK TIN (backup, DHCP)"
/interface set [find default-name=ether2] comment="LINK VIVO (principal, DHCP)"
/interface bridge set [find name="bridge-LAN"] comment="Rede Interna Matriz (192.168.10.0/24) - portas 3 e 5"
/interface list member add interface=ether4-TIN list=WAN_PUBLIC

# 2. Rotas: padrão por link + IP de teste preso ao link (o blackhole impede testar pelo outro link)
#    Os dois links vêm da MESMA rede da escola (172.16.31.0/24): por isso o gateway leva a porta (IP%porta)
/ip route
add dst-address=0.0.0.0/0 gateway=172.16.31.254%ether2-INTERNET distance=1 comment="DEF-VIVO"
add dst-address=0.0.0.0/0 gateway=172.16.31.254%ether4-TIN distance=2 comment="DEF-TIN"
add dst-address=1.0.0.1/32 gateway=172.16.31.254%ether2-INTERNET distance=1 comment="MON-VIVO"
add dst-address=9.9.9.9/32 gateway=172.16.31.254%ether4-TIN distance=1 comment="MON-TIN"
add dst-address=1.0.0.1/32 blackhole distance=250 comment="MON-VIVO trava"
add dst-address=9.9.9.9/32 blackhole distance=250 comment="MON-TIN trava"

# 3. DHCP: o cliente não cria rota sozinho; o script atualiza o gateway das rotas acima
/ip dhcp-client set [find interface=ether2-INTERNET] add-default-route=no comment="LINK VIVO" \
    script=":if (\$bound=1) do={/ip route set [find comment=\"DEF-VIVO\"] gateway=(\$\"gateway-address\" . \"%ether2-INTERNET\"); /ip route set [find comment=\"MON-VIVO\"] gateway=(\$\"gateway-address\" . \"%ether2-INTERNET\")}"
/ip dhcp-client add interface=ether4-TIN add-default-route=no use-peer-dns=no comment="LINK TIN" \
    script=":if (\$bound=1) do={/ip route set [find comment=\"DEF-TIN\"] gateway=(\$\"gateway-address\" . \"%ether4-TIN\"); /ip route set [find comment=\"MON-TIN\"] gateway=(\$\"gateway-address\" . \"%ether4-TIN\")}"

# 4. NAT e liberação da Filial também pelo TIN
/ip firewall nat add chain=srcnat out-interface=ether4-TIN action=masquerade comment="NAT: Matriz e Filial pelo LINK TIN"
/ip firewall filter add chain=forward action=accept src-address=192.168.20.0/24 out-interface=ether4-TIN \
    comment="Filial -> internet (TIN)" place-before=[find comment="Filial -> internet"]

# 5. Detecção a cada 5 s e troca automática
/tool netwatch
add host=1.0.0.1 type=icmp interval=5s packet-count=5 packet-interval=200ms thr-loss-percent=60% \
    comment="NOC: LINK VIVO" \
    down-script="/ip route set [find comment=\"DEF-VIVO\"] disabled=yes; /ip firewall connection remove [find]; :log warning \"[NOC] LINK VIVO CAIU: internet pelo LINK TIN\"" \
    up-script="/ip route set [find comment=\"DEF-VIVO\"] disabled=no; /ip firewall connection remove [find]; :log warning \"[NOC] LINK VIVO OK: internet de volta para a VIVO\""
add host=9.9.9.9 type=icmp interval=5s packet-count=5 packet-interval=200ms thr-loss-percent=60% \
    comment="NOC: LINK TIN" \
    down-script="/ip route set [find comment=\"DEF-TIN\"] disabled=yes; :log warning \"[NOC] LINK TIN CAIU\"" \
    up-script="/ip route set [find comment=\"DEF-TIN\"] disabled=no; :log warning \"[NOC] LINK TIN OK\""

# 6. SNMP só leitura para o servidor do NOC
:if ([:len [/snmp community find name=public_senai]] = 0) do={/snmp community add name=public_senai addresses=192.168.10.50/32 security=none read-access=yes write-access=no}
/snmp community set [find default=yes] disabled=yes
/snmp set enabled=yes contact="NOC SENAI TCC" location="Rack Matriz"

# 7. Pega o gateway atual dos dois links
/ip dhcp-client renew [find]
