# Montagem automática da bancada

> **Bancada já configurada?** Para remontar (os roteadores guardam a configuração), siga
> [PASSO-A-PASSO.md](PASSO-A-PASSO.md). Este arquivo é a configuração do zero.
>
> Ferramentas auxiliares: `atualizar_v7.ps1` (RouterOS 6 → 7), `testar.ps1` (testa o arquivo sem aplicar) e
> `conferir.ps1` (lê a configuração e testa a fibra e o rádio de dentro do roteador).

Tudo roda no notebook, na pasta do repositório. Cabos ligados conforme o mapa de portas da documentação (seção 9).

## 1. Gerar os arquivos (uma vez)

```powershell
python bancada\gerar_configs.py
```

Pergunta o IP do Zabbix, a comunidade SNMP e as senhas do `admin_senai` (sem mostrar na tela). Gera tudo em `bancada\saida\`. **Esses arquivos têm as suas senhas: apague a pasta depois de configurar.**

## 2. Roteadores (um de cada vez)

Ligue o cabo do notebook numa porta de **LAN** do MikroTik (**ether3, 4 ou 5**), com o MikroTik **de fábrica** (o notebook pega IP 192.168.88.x sozinho). Para um equipamento já usado, faça antes o reset pelo botão ou pelo Winbox.

```powershell
powershell -ExecutionPolicy Bypass -File bancada\enviar_mikrotik.ps1 -Equipamento R-MATRIZ
```

A senha pedida é a **atual** do MikroTik: a da etiqueta ou vazia (só Enter). Ele copia o arquivo, apaga a configuração, reinicia e se configura sozinho em cerca de 1 minuto. A conexão cai no meio: é normal.

Repita com `-Equipamento R-FILIAL`. Os switches, se forem MikroTik gerenciáveis, usam `-Equipamento SW-MATRIZ` / `SW-FILIAL`.

Depois de configurado, o roteador **não está mais em 192.168.88.1** e só aceita gerência pela LAN dele:

| Equipamento | Novo IP | Gerenciar a partir de |
| --- | --- | --- |
| R-MATRIZ | 192.168.10.1 | Notebook/PC no SW-MATRIZ |
| R-FILIAL | 192.168.20.1 | PC no SW-FILIAL |

Para conferir se o arquivo foi aplicado até o fim, no terminal do roteador: `/log print where message~"NOC SENAI"` deve mostrar "aplicando" e "aplicado".

## 3. Rádios P2P

Pela página web de cada rádio, com os valores de `bancada\saida\RADIOS.txt`. É o único equipamento manual: depende do fabricante.

## 4. PCs

Copie `pc-matriz.ps1` / `pc-filial.ps1` para o PC correspondente e rode **como administrador**:

```powershell
powershell -ExecutionPolicy Bypass -File .\pc-filial.ps1
```

Configura IP fixo, gateway, MTU 2000 (se a placa aceitar) e libera o ping.

## 5. Notebook com o Zabbix

Cabo numa porta livre do SW-MATRIZ, Wi-Fi na internet e, no VMware, o VMnet0 preso à placa do cabo. A VM já está em 192.168.10.50.

## 6. Conferir tudo

Na VM do Zabbix:

```bash
cd /root/noc && /opt/noc-analista/bin/python validar_bancada.py
```

Testa 16 pontos (rede, enlaces, antenas, Filial, SNMP, SSH de leitura, OSPF, rota pela fibra, MTU 2000 e o que o Zabbix está vendo) e dá uma dica para cada falha. Com tudo OK, faça o teste de failover: no R-FILIAL, `/interface disable sfp1-WAN-FIBRA`.

## 7. Limpeza

Apague `bancada\saida\` (tem as senhas).
