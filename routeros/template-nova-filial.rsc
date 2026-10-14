# ====================================================================
# TEMPLATE PADRONIZADO PARA FUTURAS UNIDADES (NOVA FILIAL)
# Mesmo padrão da R-FILIAL (revisão 14/10/2026): porta 1 = rádio, sfp1 = fibra, 3-5 = LAN em bridge,
# loopback /32 como router-id. Senha substituída por placeholder.
# Este arquivo usa variáveis :local: aplique como script (/import arquivo.rsc), nunca colando linha a
# linha no terminal (cada linha colada perde as variáveis da anterior).
# ====================================================================

:local NOMEUNIDADE "R-FILIAL-02"
:local IPLAN "192.168.30.1/24"
:local IPWANFIBRA "10.0.1.6/30"
:local IPWANRADIO "10.0.2.6/29"
:local LOOPBACK "10.255.255.3"
:local SENHAADMIN "<SENHA_ADMIN_UNIDADE>"

/system identity set name=$NOMEUNIDADE

# hEX S (RB760iGS): o MTU nao pode passar do L2MTU (1596 de fabrica). 2026 e o maximo do chip.
/interface ethernet set [find where default-name~"ether"] l2mtu=2026
/interface set [find default-name=ether1] name="ether1-WAN-RADIO" comment="PAP Radio" mtu=2000
/interface set [find default-name=ether2] name="ether2-reserva" comment="Reserva" mtu=2000
/interface ethernet set [find default-name=sfp1] name="sfp1-WAN-FIBRA" comment="PAP Fibra (SFP)" l2mtu=2026 mtu=2000
/interface set [find default-name=ether3] name="ether3-LAN" mtu=2000
/interface set [find default-name=ether4] name="ether4-LAN" mtu=2000
/interface set [find default-name=ether5] name="ether5-LAN" mtu=2000
/interface bridge add name="bridge-LAN" mtu=2000 comment="LAN Interna - portas 3, 4 e 5"
/interface bridge port add bridge=bridge-LAN interface=ether3-LAN
/interface bridge port add bridge=bridge-LAN interface=ether4-LAN
/interface bridge port add bridge=bridge-LAN interface=ether5-LAN
/interface bridge add name="loopback" comment="Loopback /32"

/ip address add address=$IPLAN interface=bridge-LAN
/ip address add address=$IPWANFIBRA interface=sfp1-WAN-FIBRA
/ip address add address=$IPWANRADIO interface=ether1-WAN-RADIO
/ip address add address=($LOOPBACK . "/32") interface=loopback

/user add name="admin_senai" group=full password=$SENHAADMIN
/user disable admin

/ip service set telnet,ftp,www,api,api-ssl,www-ssl disabled=yes
/ip service set ssh,winbox address=192.168.0.0/16 disabled=no

/interface list add name="LAN_MGMT"
/interface list member add interface=bridge-LAN list=LAN_MGMT
/ip neighbor discovery-settings set discover-interface-list=LAN_MGMT
/tool mac-server set allowed-interface-list=LAN_MGMT
/tool mac-server mac-winbox set allowed-interface-list=LAN_MGMT

/routing ospf instance add name="ospf-inst" router-id=$LOOPBACK
/routing ospf area add name="area-0" instance=ospf-inst area-id=0.0.0.0
/routing ospf interface-template add area=area-0 interfaces=sfp1-WAN-FIBRA cost=10 type=ptp comment="PAP Fibra"
/routing ospf interface-template add area=area-0 interfaces=ether1-WAN-RADIO cost=100 type=ptp comment="PAP Radio"
/routing ospf interface-template add area=area-0 interfaces=bridge-LAN passive
/routing ospf interface-template add area=area-0 interfaces=loopback passive

/ip firewall filter
add chain=input action=accept connection-state=established,related
add chain=input action=accept protocol=icmp
add chain=input action=accept protocol=ospf
add chain=input action=accept in-interface-list=LAN_MGMT
add chain=input action=drop
