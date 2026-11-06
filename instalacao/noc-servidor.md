# Servidor do NOC: Debian 12 direto no PC

> **Atualização 19/10/2026:** o NOC vai rodar numa **VM no VMware ESXi** do servidor de rack (Dell PowerEdge T440,
> ESXi em 192.168.10.40). Dentro da VM, o roteiro é o mesmo deste documento, com dois atalhos:
>
> - **Versão:** Debian **12.15.0** amd64, imagem `debian-12.15.0-amd64-netinst.iso` (a 13 não serve).
> - **VM:** 2 vCPU, 8 GB de RAM, 60 GB de disco, **uma** placa de rede no port group da rede da Matriz
>   (a internet vem pelo R-MATRIZ, porta ether2). Na instalação do Debian, deixe a rede em DHCP.
> - **Depois do Debian instalado**, copie a pasta do projeto para `/opt/noc-senai-tcc` (cópia pela rede, `rsync`/`scp`
>   ou pendrive — **não** é por git). Exemplo a partir do seu PC:
>
>   ```
>   rsync -a --exclude .git --exclude .venv --exclude node_modules ./noc-senai-tcc/ root@192.168.10.50:/opt/noc-senai-tcc/
>   ```
>
> - Depois, no console da VM, como root, um script faz o resto (rede fixa 192.168.10.50, pacotes, `noc.conf`,
>   chave SSH do Analista IA e o `instalacao/instalar-noc.sh`):
>
>   ```
>   bash /opt/noc-senai-tcc/instalacao/preparar-servidor.sh
>   ```
>
>   Ele pede, sem mostrar na tela, o token da API do Zabbix, a senha de app do Gmail e a chave do Gemini.

O servidor de produção é um PC de torre com o Debian 12 instalado direto no disco (sem máquina virtual). Depois da
instalação básica, o `instalacao/instalar-noc.sh` monta o NOC inteiro: Zabbix 7.0, banco, Apache com HTTPS, Grafana, Analista IA,
e-mail, dashboards, mapa, página de status, backup diário e tarefas agendadas.

## Requisitos

| Item | Mínimo | Recomendado |
| --- | --- | --- |
| Memória | 4 GB | 8 GB |
| Disco | 40 GB | 120 GB ou mais (SSD) |
| Rede | 1 placa ligada na rede da Matriz | 2 placas: Matriz + rede da escola (internet para e-mail e IA) |
| Instalação | pendrive de 2 GB ou mais, monitor e teclado (só no início) | |

A internet é necessária durante a instalação (pacotes do Debian, do Zabbix e do Grafana) e depois para enviar e-mails e
usar a IA. A rede da Matriz não tem internet: por isso a segunda placa, ligada na rede da escola.

## 1. Pendrive de instalação

1. Imagem oficial: `debian-12.15.0-amd64-netinst.iso`, de
   https://cdimage.debian.org/cdimage/archive/12.15.0/amd64/iso-cd/ (conferir o SHA256SUMS da mesma pasta).
2. Gravar com o Rufus (https://rufus.ie): selecionar o pendrive e a ISO, esquema de partição GPT (PC com UEFI) ou MBR
   (BIOS antiga), Iniciar, "Gravar em modo imagem ISO". Apaga tudo o que estiver no pendrive.

Usar o Debian **12** (bookworm): o instalador do NOC e os pacotes do Zabbix 7.0 usados aqui são para essa versão.

## 2. BIOS do PC

Na tecla de setup (geralmente Del, F2 ou F10):
- Ligar sozinho quando a energia voltar: "Restore on AC Power Loss" / "AC Back" = **Power On**.
- Desligar o modo de economia que suspende o PC, se existir.
- Boot pelo pendrive: menu de boot (F12, F11, F8 ou Esc) ou ordem de boot com o USB primeiro.

## 3. Instalação do Debian (tela por tela)

| Tela | Escolha |
| --- | --- |
| Menu inicial | **Install** (o modo texto, mais simples) |
| Idioma / país / teclado | Português (Brasil) / Brasil / Português Brasileiro (ABNT2) |
| Placa de rede principal | a que está ligada na **rede da escola** (internet) durante a instalação |
| Nome da máquina | `noc-senai` |
| Domínio | deixar em branco |
| Senha do root | uma senha forte, **anotar** |
| Usuário comum | nome `aluno` e uma senha, **anotar** |
| Fuso horário | São Paulo (ou o da escola) |
| Particionamento | Assistido: usar o disco inteiro → todos os arquivos em uma partição → confirmar |
| Espelho do repositório | Brasil → deb.debian.org |
| Pesquisa de popularidade | Não |
| Seleção de software | **desmarcar** "Ambiente de trabalho Debian" e "GNOME"; **marcar só** "servidor SSH" e "utilitários de sistema padrão" |
| GRUB | Sim, no disco principal |

Ao final, retirar o pendrive e reiniciar. O PC sobe só com a tela de login em texto.

## 4. Rede fixa na Matriz

Entrar como `root` no próprio PC e descobrir os nomes das placas:

```
ip -br link
```

Editar `/etc/network/interfaces` (ex.: `nano /etc/network/interfaces`), mantendo a placa da escola em DHCP e colocando a
da Matriz com IP fixo (troque `enp2s0`/`enp3s0` pelos nomes reais):

```
auto enp2s0
iface enp2s0 inet dhcp            # rede da escola (internet)

auto enp3s0
iface enp3s0 inet static          # rede da Matriz (porta 3, 4 ou 5 do R-MATRIZ)
    address 192.168.10.50/24
    up ip route add 192.168.20.0/24 via 192.168.10.1
    up ip route add 10.0.0.0/8 via 192.168.10.1
```

`systemctl restart networking` e testar: `ping -c3 192.168.10.1` e `ping -c3 deb.debian.org`.
Sem gateway na placa da Matriz de propósito: a internet sai pela escola, e só as redes do projeto vão para o R-MATRIZ.

## 5. Acesso remoto

Do notebook ligado na Matriz: `ssh aluno@192.168.10.50` e depois `su -`. A partir daqui o monitor não é mais
necessário. Para o Claude acessar, instalar a chave pública dele em `/root/.ssh/authorized_keys` (como no protótipo).

## 6. NOC

Copie a pasta do projeto para `/opt/noc-senai-tcc` (cópia pela rede, `rsync`/`scp` ou pendrive — **não** é por git). Depois:

```
cd /opt/noc-senai-tcc
bash instalacao/instalar-noc.sh        # 1ª vez: cria /etc/noc/noc.conf e para
nano /etc/noc/noc.conf      # SERVIDOR_IP=192.168.10.50 e os IPs da rede (já são os padrões)
bash instalacao/instalar-noc.sh        # instala tudo; pede o token do Zabbix, a senha de app do Gmail e a chave do Gemini
```

Na VM do ESXi, o `instalacao/preparar-servidor.sh` faz a rede fixa e os pacotes antes deste passo.

## 7. Conferir

```
cd /root/noc && /opt/noc-analista/bin/python validar_bancada.py
```

16 verificações (rede, enlaces, antenas, SNMP, SSH de leitura, OSPF, Zabbix). Depois, uma simulação de queda para
conferir o e-mail: `python simular_queda.py --cenario queda`.
