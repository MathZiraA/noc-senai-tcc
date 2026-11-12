# ====================================================================
# NOC SENAI — Hardening de gerência do roteador (fechar a WAN)
# Correção dos achados do pentest externo: Winbox (8291) e bandwidth-test (2000)
# estavam alcançáveis da rede do SENAI. Este bloco restringe toda a gerência
# às redes do projeto e dropa o resto na WAN.
#
# Aplicar no R-MATRIZ e no R-FILIAL (cole no terminal, Winbox > New Terminal).
# Reversível — os comandos de desfazer estão no fim do arquivo.
# ====================================================================

# --- PARTE 1: fecha a exposição (não depende de listas de interface) ---

# 1.1 Desliga o servidor de bandwidth-test (porta 2000)
/tool bandwidth-server set enabled=no

# 1.2 Restringe os serviços de gerência SÓ às redes do projeto.
#     Conexões de fora dessas faixas (ex.: rede SENAI 172.16.x) passam a ser recusadas.
/ip service set winbox  address=192.168.10.0/24,192.168.20.0/24
/ip service set ssh     address=192.168.10.0/24,192.168.20.0/24
/ip service set www     address=192.168.10.0/24,192.168.20.0/24
/ip service set www-ssl address=192.168.10.0/24,192.168.20.0/24
/ip service set api     address=192.168.10.0/24,192.168.20.0/24
/ip service set api-ssl address=192.168.10.0/24,192.168.20.0/24

# 1.3 Desliga serviços legados que não são usados
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes

# --- PARTE 2: reforço (defesa em profundidade) ---
# Requer as listas de interface WAN e LAN. Confira antes: /interface list print
# Se não existirem, crie (ajuste os nomes das interfaces ao seu roteador):
#   /interface list add name=WAN
#   /interface list add name=LAN
#   /interface list member add list=WAN interface=ether2-INTERNET
#   /interface list member add list=WAN interface=ether4-TIN
#   /interface list member add list=LAN interface=bridge-LAN

# 2.1 Winbox/Telnet por MAC e descoberta de vizinhos só na LAN (não vazam na WAN/L2 externa)
/tool mac-server set allowed-interface-list=LAN
/tool mac-server mac-winbox set allowed-interface-list=LAN
/tool mac-server ping set enabled=no
/ip neighbor discovery-settings set discover-interface-list=LAN

# 2.2 Dropa explicitamente a gerência vinda da WAN, no topo do input
/ip firewall filter add chain=input in-interface-list=WAN protocol=tcp \
    dst-port=22,23,80,443,2000,8291,8728,8729 action=drop \
    comment="NOC: bloqueia gerencia pela WAN" place-before=0

# 2.3 (opcional) Dropa SNMP e DNS vindos da WAN
/ip firewall filter add chain=input in-interface-list=WAN protocol=udp \
    dst-port=161,53 action=drop comment="NOC: bloqueia SNMP/DNS pela WAN"

# ====================================================================
# CONFERIR (depois de aplicar):
#   /ip service print              -> winbox/ssh com a coluna Address preenchida
#   /tool bandwidth-server print   -> enabled: no
#   /ip firewall filter print      -> a regra "NOC: bloqueia gerencia pela WAN"
# Da rede SENAI, as portas 8291 e 2000 devem passar a aparecer FILTRADAS.
#
# DESFAZER (se precisar):
#   /tool bandwidth-server set enabled=yes
#   /ip service set winbox,ssh,www,www-ssl,api,api-ssl address=""
#   /ip firewall filter remove [find comment~"NOC: bloqueia"]
# ====================================================================
