# Cópia da VM do protótipo para VMware ESXi

A VM do protótipo (Debian 12 + Zabbix 7.0 + Grafana + Analista IA, como estava em 14/10/2026) está na área de
**Releases** deste repositório, exportada em OVA e dividida em partes de até 1,9 GB (limite de 2 GB por arquivo
do GitHub).

> **Atenção:** a VM contém as credenciais do protótipo funcionando (tokens do Zabbix, chave do Gemini, senha de app
> do Gmail dentro do Zabbix, chave privada da CA do NOC, chaves SSH, senhas do banco e do Grafana). Mantenha o
> repositório **privado** e só dê acesso a quem pode ter essas credenciais. Para entregar a terceiros, prefira o
> instalador (`instalacao/instalar-noc.sh`) num Debian limpo.

## 1. Baixar e juntar as partes

Baixe todos os arquivos `NOC-SENAI-Zabbix.ova.parte*` e o `SHA256SUMS.txt` da release e junte, na mesma pasta:

Windows (PowerShell):
```powershell
cmd /c copy /b NOC-SENAI-Zabbix.ova.parte01+NOC-SENAI-Zabbix.ova.parte02+NOC-SENAI-Zabbix.ova.parte03 NOC-SENAI-Zabbix.ova
Get-FileHash NOC-SENAI-Zabbix.ova -Algorithm SHA256
```
(liste todas as partes que existirem, em ordem)

Linux:
```bash
cat NOC-SENAI-Zabbix.ova.parte* > NOC-SENAI-Zabbix.ova
sha256sum -c SHA256SUMS.txt
```

O hash do `.ova` montado tem de ser igual ao do `SHA256SUMS.txt`.

## 2. Importar no ESXi

No vSphere Client / ESXi Host Client: **Create / Register VM → Deploy a virtual machine from an OVF or OVA file**
→ selecione o `.ova` → escolha o datastore → mapeie as duas placas de rede:

| Placa da VM | Uso no protótipo | No ESXi |
| --- | --- | --- |
| Network adapter 1 (`ens33`) | LAN da Matriz, 192.168.10.50 | Port group ligado à rede da Matriz |
| Network adapter 2 (`ens35`) | NAT do VMware, 192.168.137.50 (internet) | Port group com saída para a internet (e-mail e IA) |

Notas:
- A VM foi criada no VMware Workstation com hardware virtual versão 21 (ESXi 8.0 U2 ou superior). Em ESXi mais antigo,
  importe com o OVF Tool: `ovftool --maxVirtualHardwareVersion=19 NOC-SENAI-Zabbix.ova vi://usuario@esxi/`.
- Tipo do sistema: Debian 12 64 bits. Placas Intel e1000.

## 3. Ajustar a rede para o ambiente real

O IP `192.168.137.50` era do NAT do notebook e não existe no ESXi. Entre pelo console da VM (usuário `aluno`, depois
`su -`) e ajuste:

```bash
# placa de internet: DHCP ou IP fixo da rede de gerência/saída do servidor
nmcli con mod NAT-Internet ipv4.method auto ipv4.addresses "" ipv4.gateway "" ipv4.dns ""
nmcli con up NAT-Internet
# se o IP da LAN da Matriz mudar, ajuste também NOC-Matriz-Estatico e o /etc/noc/noc.conf (SERVIDOR_IP)
nano /etc/noc/noc.conf
cd /root/noc-senai-tcc && bash instalacao/instalar-noc.sh   # reaplica certificado, Zabbix e bloco RouterOS com os IPs novos
```

Depois, para o servidor real, troque `CLIENTE_EMAIL` no `/etc/noc/noc.conf` pelo e-mail do cliente e rode o instalador
de novo.
