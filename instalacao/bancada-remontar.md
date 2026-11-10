# Passo a passo: montar a bancada de novo

Os dois roteadores **guardam a configuração** (ela fica gravada neles, mesmo desligados). Para remontar, é só ligar
os cabos na ordem abaixo e conferir. Não precisa reconfigurar nada, a não ser que um roteador tenha sido resetado
(veja a parte 9).

Estado em 14/10/2026: R-MATRIZ e R-FILIAL (MikroTik hEX S) no RouterOS 7.24.5, fibra funcionando
(OSPF fechado, ~0,7 ms, 0% de perda), rádio ainda sem as antenas.

## 1. Material

- 2 MikroTik hEX S com as fontes (etiquetar: **R-MATRIZ** e **R-FILIAL**)
- Fibra com os 2 módulos SFP (já encaixados nas portas **sfp1**)
- 2 antenas do rádio P2P com as fontes PoE (ou, para teste, 1 cabo de rede direto no lugar delas)
- Notebook com o WinBox (`Documents\winbox\WinBox.exe`) e 1 cabo de rede
- Opcional: 1 PC para cada lado, switches

## 2. Mapa das portas (igual nos dois roteadores)

| Porta | Uso | Liga em |
| --- | --- | --- |
| **ether1** | Rádio (backup) | antena (ou cabo direto até a ether1 do outro roteador) |
| ether2 | Reserva (livre) | nada |
| **ether3, 4, 5** | Rede local (LAN) | notebook, PCs, switch |
| **sfp1** | Fibra (principal) | módulo SFP com a fibra até a sfp1 do outro roteador |

**Nunca** ligue o rádio ou a fibra nas portas 3, 4 ou 5: elas são a rede local, e as duas redes viram uma só
(dois DHCP brigando, OSPF ignorado).

| Roteador | Rede local | IP do roteador | Loopback | Fibra | Rádio |
| --- | --- | --- | --- | --- | --- |
| R-MATRIZ | 192.168.10.0/24 | 192.168.10.1 | 10.255.255.1 | 10.0.1.1 | 10.0.2.1 |
| R-FILIAL | 192.168.20.0/24 | 192.168.20.1 | 10.255.255.2 | 10.0.1.2 | 10.0.2.2 |

Os dois roteadores entregam IP automático (DHCP) na rede local: .100 a .199.

## 3. Montagem física (nesta ordem)

1. Ligue a **fibra**: sfp1 do R-MATRIZ ↔ sfp1 do R-FILIAL.
2. Ligue o **rádio**: ether1 do R-MATRIZ → antena da Matriz; ether1 do R-FILIAL → antena da Filial.
   (Sem as antenas: deixe desligado, ou um cabo direto ether1 ↔ ether1 para simular.)
3. Ligue o **notebook** na **ether3 do R-FILIAL** (é de lá que os testes partem).
4. Ligue as **fontes** dos dois roteadores. Espere **1 minuto**.
5. Confira as luzes: sfp1 acesa nos dois; ether3 acesa no R-FILIAL; ether1 acesa se o rádio estiver ligado.

## 4. Conferir o notebook

No cmd: `ipconfig`. A placa **Ethernet** tem de mostrar um IP **192.168.20.1xx** (veio do DHCP do R-FILIAL).
Se mostrar 169.254.x.x: o cabo não está na ether3/4/5 ou o roteador ainda está ligando. Espere e rode
`ipconfig /renew`.

## 5. Teste rápido da fibra (cmd)

O notebook usa o Wi-Fi para tudo que não é da rede local, então o `-S` obriga o ping a sair pelo cabo:

```
ping -S 192.168.20.1xx 192.168.10.1
```

(troque `192.168.20.1xx` pelo IP do passo 4). Resposta com **TTL=63** = o pacote atravessou o R-FILIAL e a fibra
até o R-MATRIZ. Para ver o caminho: desligue o Wi-Fi um momento e rode `tracert 192.168.10.1`
(192.168.20.1 → 192.168.10.1).

## 6. Conferência completa (PowerShell, na pasta do repositório)

```
powershell -ExecutionPolicy Bypass -File infra\bancada\conferir.ps1 -IP 192.168.20.1
```

Senha: a do **admin_senai do R-FILIAL**. No fim ele mostra um resumo dos pings; o arquivo completo fica em
`infra\bancada\saida\conferir-192.168.20.1.txt`. O que tem de aparecer:

| No arquivo | Esperado |
| --- | --- |
| `/interface print` | `sfp1-WAN-FIBRA` com **R** (running) e MTU 2000; `ether1-WAN-RADIO` com R se o rádio estiver ligado |
| `/routing ospf neighbor` | 1 vizinho pela `sfp1-WAN-FIBRA` (2 vizinhos com o rádio funcionando) |
| `/ip route` | `192.168.10.0/24` e `10.255.255.1/32` com gateway `10.0.1.1%sfp1-WAN-FIBRA` |
| `/tool netwatch` | status **up** (fibra boa) |
| PING-FIBRA, PING-LOOPBACK, PING-LAN | `packet-loss=0%` |

## 7. Rádio (quando as antenas estiverem montadas)

1. Configure as antenas pela página web delas, com a ficha `infra\bancada\saida\RADIOS.txt`
   (Matriz = Access Point PtP, Filial = Station, modo bridge, IPs 10.0.2.3 e 10.0.2.4, MTU 2000).
2. Cabo de cada antena na **ether1** do seu roteador.
3. Rode o `conferir.ps1` de novo: tem de aparecer **2 vizinhos OSPF** (sfp1 e ether1) e o PING-RADIO com 0% de
   perda. As rotas continuam pela fibra (custo 10 contra 100 do rádio): o rádio fica de reserva.

## 8. Teste de failover (a demonstração do TCC; precisa do rádio funcionando)

1. No cmd, deixe um ping contínuo da Filial para a Matriz:
   `ping -t -S 192.168.20.1xx 192.168.10.1`
2. No WinBox, conecte no **R-FILIAL** (192.168.20.1, admin_senai), abra **New Terminal** e derrube a fibra:
   `/interface disable sfp1-WAN-FIBRA`
3. Conte quantos pings falham até voltar a responder (agora pelo rádio). Cada "Esgotado" ≈ 1 segundo.
   Esperado: poucos segundos (o OSPF percebe a queda e troca de caminho).
4. Confirme o desvio: `/ip route print where dst-address=192.168.10.0/24` mostra o gateway `10.0.2.1%ether1-WAN-RADIO`.
5. Volte a fibra: `/interface enable sfp1-WAN-FIBRA`. Em segundos a rota volta para a sfp1.
6. Para ver o que o roteador registrou: `/log print where message~"NOC"`.

Para o teste de **fibra degradada** (troca sem a fibra cair), o netwatch troca para o rádio quando a média do ping
na fibra passa de 30 ms ou a perda passa de 10%. Na bancada isso só acontece de verdade com a fibra ruim (por
exemplo, conector sujo); a lógica pode ser vista em `/tool netwatch print detail`.

## 9. Se algo der errado

| Sintoma | O que fazer |
| --- | --- |
| Notebook sem IP (169.254.x.x) | Cabo na ether3/4/5? Roteador ligado há 1 min? `ipconfig /renew` |
| WinBox não conecta pelo IP | Na aba **Neighbors**, clique no **MAC** do roteador (funciona sem IP) |
| Ping da Matriz falha | Use o `-S` (passo 5). Sem `-S` o Windows manda pelo Wi-Fi |
| sfp1 sem luz | Módulo SFP bem encaixado? Fibra invertida (TX/RX)? Troque as pontas de um lado |
| OSPF sem vizinho | `conferir.ps1`: as duas pontas da fibra têm de estar na sfp1 com R (running) |
| Senha do admin_senai esquecida | Reset do roteador (botão) e refazer a parte 10 |
| Rádio "liga" as duas redes (IPs da rede errada) | O cabo do rádio está numa porta de LAN: mude para a **ether1** |

## 10. Só se um roteador for resetado (configuração do zero)

Os modelos em `routeros/` já têm tudo o que foi corrigido na montagem real (fibra na sfp1, DHCP, MTU, OSPF v7).

1. Notebook na **ether3** do roteador de fábrica (o notebook pega IP 192.168.88.x).
2. Se a versão for 6.x (WinBox, aba Neighbors): `powershell -ExecutionPolicy Bypass -File infra\bancada\atualizar_v7.ps1`
   (Enter nas senhas; 2 a 3 minutos).
3. Gere de novo os arquivos com as senhas (os da pasta `saida` de 14/10 são anteriores às correções):
   `python infra\bancada\gerar_configs.py` (Enter no IP do Zabbix e na comunidade; senhas do admin_senai; `n` nos switches).
4. Teste sem aplicar: `powershell -ExecutionPolicy Bypass -File infra\bancada\testar.ps1 -Equipamento R-MATRIZ`
   → tem de terminar com "No syntax errors found".
5. Aplique: `powershell -ExecutionPolicy Bypass -File infra\bancada\enviar_mikrotik.ps1 -Equipamento R-MATRIZ`
   (Enter nas senhas; o roteador reinicia e se configura sozinho em ~1 minuto).
6. Confira (parte 6).

## 11. Depois: o Zabbix (VM no VMware)

Quando quiser o monitoramento: notebook na **ether3 do R-MATRIZ**, VM ligada (placa `ens33` em bridge com a placa
do cabo, IP fixo 192.168.10.50). Na VM: `cd /root/noc && /opt/noc-analista/bin/python validar_bancada.py`.
E-mail e IA precisam de internet na VM (placa NAT); o monitoramento dos enlaces funciona sem internet.

**Senhas:** os arquivos de `infra\bancada\saida` contêm as senhas que você escolheu. Essa pasta nunca vai para o GitHub;
apague-a quando o TCC terminar.
