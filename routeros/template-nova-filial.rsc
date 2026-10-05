# ====================================================================
# TEMPLATE PADRONIZADO PARA FUTURAS UNIDADES (NOVA FILIAL)
# Transcrito do documento da topologia. Senha substituída por placeholder.
# Este arquivo usa variáveis :local: aplique como script (/import arquivo.rsc), nunca colando linha a
# linha no terminal (cada linha colada perde as variáveis da anterior).
# ====================================================================

:local NOMEUNIDADE "R-FILIAL-02"
:local IPLAN "192.168.30.1/24"
:local IPWANFIBRA "10.0.1.6/30"
:local IPWANRADIO "10.0.2.6/29"
:local ROUTERID "3.3.3.3"
:local SENHAADMIN "<SENHA_ADMIN_UNIDADE>"

/system identity set name=$NOMEUNIDADE

/interface set [find default-name=ether1] name="ether1-LAN" comment="LAN Interna" mtu=2000
/interface set [find default-name=ether2] name="ether2-WAN-FIBRA" comment="PAP Fibra" mtu=2000
/interface set [find default-name=ether3] name="ether3-WAN-RADIO" comment="PAP Radio" mtu=2000

/ip address add address=$IPLAN interface=ether1-LAN
/ip address add address=$IPWANFIBRA interface=ether2-WAN-FIBRA
/ip address add address=$IPWANRADIO interface=ether3-WAN-RADIO

/user add name="admin_senai" group=full password=$SENHAADMIN
/user disable admin

/ip service set telnet,ftp,www,api,api-ssl,www-ssl disabled=yes
/ip service set ssh,winbox address=192.168.0.0/16 disabled=no

/interface list add name="LAN_MGMT"
/interface list member add interface=ether1-LAN list=LAN_MGMT
/ip neighbor discovery-settings set discover-interface-list=LAN_MGMT
/tool mac-server set allowed-interface-list=LAN_MGMT
/tool mac-server mac-winbox set allowed-interface-list=LAN_MGMT

/routing ospf instance add name="ospf-inst" router-id=$ROUTERID
/routing ospf area add name="area-0" instance=ospf-inst area-id=0.0.0.0
/routing ospf interface-template add area=area-0 interfaces=ether2-WAN-FIBRA cost=10 type=ptp
/routing ospf interface-template add area=area-0 interfaces=ether3-WAN-RADIO cost=100 type=ptp
/routing ospf interface-template add area=area-0 interfaces=ether1-LAN passive=yes

/ip firewall filter
add chain=input action=accept connection-state=established,related
add chain=input action=accept protocol=icmp
add chain=input action=accept protocol=ospf
add chain=input action=accept in-interface-list=LAN_MGMT
add chain=input action=drop
