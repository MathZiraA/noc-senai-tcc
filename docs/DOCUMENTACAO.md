# NOC SENAI — Zabbix + Analista IA: Documentação Técnica

Oct 3, 2026 · @Matheus

## 1. Visão geral

O NOC do TCC monitora a redundância Fibra/Rádio entre Matriz e Filial e avisa por e-mail, em menos de 2 minutos, quando um enlace cai, com um relatório de causa provável escrito por IA. Tudo roda em uma VM Debian com Zabbix 7.0 dentro do notebook, ligada ao switch da Matriz.

O que foi construído:

- **Monitoramento:** o roteador R-FILIAL é coletado por SNMP e cada enlace (fibra e rádio) é testado por ping a cada 10 segundos.
- **Detecção de failover:** 9 triggers distinguem fibra caída com rádio assumindo, rádio caído, Filial isolada, failover lento e fibra instável, e avisam antes da queda quando o rádio começa a degradar. O tempo de cada failover é medido em segundos.
- **Dashboard NOC:** estado dos enlaces em tempo real, latência, problemas ativos e histórico de notificações, no Zabbix e no Grafana (tela escura para a TV do NOC, com o caminho ativo Fibra/Rádio em destaque).
- **E-mail:** alerta na abertura e na normalização de cada problema, via Gmail.
- **Analista NOC com IA:** ao abrir um problema, uma IA (Google Gemini, gratuito) investiga o Zabbix e o MikroTik com ferramentas somente leitura e envia um relatório com linha do tempo, causa provável, impacto e ações recomendadas.

![Arquitetura do NOC: do enlace ao e-mail](arquitetura.png)

O Zabbix detecta a queda e manda o alerta direto ao Gmail; em paralelo, chama o Analista IA, que investiga (Zabbix, Gemini e SSH no roteador) e devolve um comentário ao evento, que vira o segundo e-mail.

Status em 03/10/2026: servidor, dashboard, e-mail e IA testados de ponta a ponta. Falta apenas a montagem física da bancada (MikroTiks e enlaces).

## 2. Topologia monitorada

A Matriz e a Filial se ligam por dois enlaces com OSPF: a fibra (custo 10) carrega o tráfego e o rádio (custo 100) só assume quando a fibra cai. A rede não tem saída para a internet.

| Equipamento | Função | Endereços |
| --- | --- | --- |
| R-MATRIZ (MikroTik RouterOS v7) | Gateway da Matriz, OSPF router-id 1.1.1.1 | LAN 192.168.10.1/24 · Fibra 10.0.1.1/30 · Rádio 10.0.2.1/29 |
| R-FILIAL (MikroTik RouterOS v7) | Gateway da Filial, OSPF router-id 2.2.2.2 — **host monitorado** | LAN 192.168.20.1/24 · Fibra 10.0.1.2/30 · Rádio 10.0.2.2/29 |
| SW-MATRIZ / SW-FILIAL | Switches L2 de acesso | 192.168.10.2 / 192.168.20.2 (se gerenciáveis) |
| RADIO-P2P-MATRIZ / FILIAL | Ponte L2 transparente do enlace de backup | 10.0.2.3 / 10.0.2.4 |
| Servidor Zabbix (VM) | Monitoramento + Analista IA, ligado ao SW-MATRIZ | 192.168.10.50/24 |

Portas nos roteadores: `ether1-LAN`, `ether2-WAN-FIBRA`, `ether3-WAN-RADIO`, todas com MTU 2000.

Por que o Zabbix fica na Matriz: ele mede cada enlace pingando o IP da Filial **daquele** enlace (10.0.1.2 pela fibra, 10.0.2.2 pelo rádio). Assim, ele enxerga exatamente qual caminho caiu, enquanto a coleta SNMP usa a LAN da Filial (192.168.20.1), alcançável por qualquer um dos dois.

## 3. Servidor Zabbix

O Zabbix 7.0.31 roda em uma VM Debian 12 no VMware do notebook, com duas placas de rede: uma na rede da Matriz para monitorar e outra em NAT para ter internet (e-mail e IA). As duas redes nunca se misturam.

| Item | Valor |
| --- | --- |
| Sistema | Debian 12 (bookworm), Python 3.11 |
| Pacotes | Zabbix Server 7.0 LTS + frontend PHP + Apache + MariaDB + zabbix-agent2 |
| Interface web | `http://192.168.137.50/zabbix` (do notebook, sempre) · `http://192.168.10.50/zabbix` (da rede da Matriz) |
| SSH | `root@192.168.137.50` por chave (`id_ed25519_zabbix` no notebook) |
| Banco | MariaDB, base `zabbix`, utf8mb4 |

Recursos da VM após a ampliação de 03/10/2026: 4 GB de RAM, 1 vCPU, disco de 20 GB (cerca de 48% em uso) e swap de 2 GB em arquivo (`/swapfile`). A tabela de partições anterior está salva em `/root/sda-particoes-antes.sfdisk`. Na mesma VM roda o Grafana 13.2 em `http://192.168.137.50:3000` (seção 5).

### Rede da VM

| Placa | Modo VMware | Perfil NetworkManager | Endereço | Uso |
| --- | --- | --- | --- | --- |
| ens33 | Bridge na placa Killer E2600 (cabo) | `NOC-Matriz-Estatico` | 192.168.10.50/24, sem gateway | Rotas 192.168.20.0/24 e 10.0.0.0/8 via 192.168.10.1 |
| ens35 | NAT (VMnet8) | `NAT-Internet` | 192.168.137.50/24, gateway e DNS 192.168.137.2 | Internet pelo Wi-Fi do notebook |

Cuidado: no **Virtual Network Editor** do VMware, o VMnet0 deve estar preso à placa Killer (cabo), não em "Automatic". Em automático, o bridge pode cair no Wi-Fi e a VM perde a rede da Matriz.

### Instalação (resumo)

1. Repositório oficial `zabbix-release_latest_7.0+debian12_all.deb` e pacotes `zabbix-server-mysql zabbix-frontend-php zabbix-apache-conf zabbix-sql-scripts zabbix-agent2`.
2. Banco `zabbix` (utf8mb4\_bin) com usuário próprio e importação de `server.sql.gz`.
3. `DBPassword` em `/etc/zabbix/zabbix_server.conf` e assistente web concluído.
4. Toda a configuração seguinte foi feita pela API (scripts Python em `/root/noc`), sem cliques no navegador.

## 4. Monitoramento do R-FILIAL

O host R-FILIAL está no grupo **Rede SENAI - Equipamentos**, é coletado por SNMP v2c na LAN `192.168.20.1:161` (comunidade na macro `{$SNMP_COMMUNITY}` = `public_senai`) e usa o template oficial **Mikrotik by SNMP**, que descobre sozinho interfaces, CPU, memória, temperatura e inclui ping ICMP.

### Itens de enlace (criados no host)

Esses itens não dependem do SNMP: funcionam assim que os enlaces tiverem IP, coletando a cada 10 s e guardando 90 dias de histórico.

| Item | Chave | Significado |
| --- | --- | --- |
| Caminho ativo Matriz-Filial | `noc.caminho_ativo` (calculado: fibra × 2 + rádio) | 3 ou 2 = FIBRA, 1 = RÁDIO (failover), 0 = FILIAL ISOLADA |
| Enlace FIBRA - estado (R-FILIAL ether2) | `icmpping[10.0.1.2,3,,,500]` | 1 = UP, 0 = DOWN (mapa "Estado do Enlace") |
| Enlace RÁDIO - estado (R-FILIAL ether3) | `icmpping[10.0.2.2,3,,,500]` | 1 = UP, 0 = DOWN |
| Enlace FIBRA - latência | `icmppingsec[10.0.1.2,3,,,500]` | Tempo de resposta em segundos (0 = sem resposta) |
| Enlace RÁDIO - latência | `icmppingsec[10.0.2.2,3,,,500]` | Tempo de resposta em segundos |
| Enlace FIBRA / RÁDIO - perda de pacotes | `icmppingloss[10.0.1.2,...]` / `icmppingloss[10.0.2.2,...]` | % de pacotes perdidos, base da previsão de degradação |
| Alcance LAN Filial (1s) | `icmpping[192.168.20.1,1,,,300]`, a cada **1 s** | Mede o tempo real sem comunicação durante uma troca de enlace |
| Tempo de failover medido | `noc.failover.segundos` (trapper) | Segundos de interrupção em cada queda da fibra, gravado por `failover_registro.py` |

### Triggers de redundância

Um enlace só é considerado DOWN após 2 medições seguidas sem resposta (cerca de 20 s), o que evita alarme por um pacote perdido.

| Severidade | Trigger | Condição |
| --- | --- | --- |
| Desastre | FILIAL ISOLADA: Fibra e Rádio indisponíveis | Os dois enlaces DOWN |
| Alta | Link FIBRA caiu: failover para RÁDIO ativo | Fibra DOWN e rádio UP |
| Média | Link RÁDIO (backup) caiu: rede sem redundância | Rádio DOWN e fibra UP |
| Média | Filial sem comunicação há mais de 10s (failover lento ou queda) | LAN da Filial sem resposta por 10 s seguidos |
| Média | RÁDIO com perda de pacotes (>5% por 5min) | Rádio UP, mas perdendo pacotes |
| Aviso | Link FIBRA instável: 3+ quedas na última hora | 6 ou mais mudanças de estado da fibra em 1 h |
| Aviso | Latência alta no RÁDIO (>50ms por 5min) | Latência mínima do rádio acima de 50 ms por 5 min |
| Aviso | PREVISÃO: latência do RÁDIO deve passar de 50ms em 30min | `forecast()` da última hora prevê mais de 50 ms em 30 min, ainda abaixo disso agora |
| Aviso | RÁDIO acima do normal: latência 2x maior que a média de 24h | Média de 15 min acima do dobro da média de 24 h |

Os três últimos avisam **antes** da queda do rádio: ele ainda funciona, mas está piorando. Isso dá tempo de verificar alinhamento e interferência enquanto a fibra ainda está de pé.

### Manutenção automática da bancada

Enquanto a rede não está montada, o host fica na manutenção **Montagem da bancada - TCC**: o Zabbix continua coletando, mas não envia e-mails. Um cron (`/etc/cron.d/noc-fim-manutencao`) verifica a cada minuto e encerra a manutenção sozinho assim que a fibra ou o rádio responderem.

## 5. Dashboard NOC

O dashboard **NOC - Monitoramento de Redundância (OFICIAL)** tem 3 páginas (redundância, saúde do R-FILIAL e mapa da topologia) que se alternam sozinhas a cada 30 s, pensado para ficar aberto numa TV durante a apresentação. Ele é montado pelo script `dash_noc.py`.

### Página 1 — Redundância Fibra x Rádio

| Linha | Widgets | Para que serve |
| --- | --- | --- |
| 1 | CAMINHO ATIVO, FIBRA (principal), RÁDIO (backup), Latência FIBRA, Latência RÁDIO, Problemas por severidade | Estado em 2 segundos: verde = UP, vermelho = DOWN; latência verde até 20 ms, amarela até 50 ms, vermelha acima |
| 2 | Linha do tempo dos enlaces (degraus 1/0) e Latência FIBRA x RÁDIO | Mostra quando cada enlace caiu e voltou e quanto tempo durou o failover |
| 3 | Tráfego FIBRA (ether2) x RÁDIO (ether3) | No failover o tráfego some da linha azul e aparece na laranja: a prova visual de que a redundância funcionou |
| 4 | Problemas ativos (com linha do tempo) e Análises da IA enviadas por e-mail | O que está acontecendo agora e o que a IA concluiu |

### Página 2 — Saúde do R-FILIAL

Disponibilidade SNMP/ICMP, relógio, todas as notificações enviadas, CPU, memória, temperatura e tráfego de todas as interfaces.

Os gráficos de tráfego, CPU, memória e temperatura usam padrões de nome (ex.: `*ether2*Bits*`). Eles ficam vazios até o SNMP responder e se preenchem sozinhos depois que o template descobrir as interfaces, sem nenhuma edição.

Dica para a apresentação: o botão de tela cheia (modo quiosque) no canto superior direito do dashboard esconde os menus do Zabbix.

### Grafana — a tela da TV do NOC

O Grafana 13.2 com o plugin oficial do Zabbix (6.8.0) mostra o painel **NOC - Redundância Fibra x Rádio** em `http://192.168.137.50:3000`, com tema escuro e atualização a cada 10 s. Ele só lê dados: coleta, alertas, e-mail e IA continuam no Zabbix.

| Painel | O que mostra |
| --- | --- |
| Caminho ativo Matriz ↔ Filial | FIBRA (verde), RÁDIO (failover, laranja) ou FILIAL ISOLADA (vermelho), lido do item calculado do Zabbix |
| FIBRA / RÁDIO | UP ou DOWN com fundo verde ou vermelho |
| Latência FIBRA / RÁDIO | Tempo de resposta, ou "sem resposta" quando o enlace está fora |
| Linha do tempo dos enlaces | Faixas UP/DOWN ao longo do tempo: cada troca de cor é uma queda ou um retorno |
| Latência Fibra x Rádio e Tráfego ether2 x ether3 | Gráficos; no failover o tráfego sai da linha da fibra e aparece na do rádio |
| Problemas | Lista de problemas do grupo, com os comentários da IA |

Como usar:

- **TV do NOC:** abrir `http://192.168.137.50:3000/d/noc-redundancia?kiosk`. O acesso de visitante é somente leitura e não pede login.
- **Administração:** usuário `admin`; a senha aleatória está na VM, em `/root/.grafana_admin`.
- **Conexão com o Zabbix:** fonte de dados "Zabbix NOC" com o usuário `grafana-leitura` (somente leitura, token próprio).
- **Configuração:** tudo por provisionamento (`setup_grafana.py`); para mudar o painel, edite o script e rode-o de novo. Para conferir, rode `testar_grafana.py`.

Verificado em 03/10/2026: todos os painéis de dados respondem e o painel mostra corretamente FILIAL ISOLADA com a bancada desmontada. O gráfico de tráfego só terá dados depois que o SNMP do MikroTik responder.

### Mapa da topologia (página 3 do dashboard do Zabbix)

O mapa **Topologia NOC SENAI - Fibra x Rádio** desenha Matriz e Filial com a fibra em linha direta e o rádio passando pelas duas antenas. Cada enlace muda de cor sozinho: verde = normal, vermelho = caído, laranja = perda de pacotes ou instável, amarelo = previsão de degradação. O R-FILIAL e as antenas acendem com os problemas, e os rótulos dos enlaces mostram a latência ao vivo. Criado por `mapa_topologia.py`.

### Página de status para os usuários da Filial

Uma página simples, sem termos técnicos, em `http://192.168.10.50/status` (rede da empresa) e `http://192.168.137.50/status` (notebook), atualizada a cada minuto por `status_page.py` (cron) e servida pelo Apache.

- **Situação agora:** "Funcionando normalmente", "Funcionando pelo link reserva" ou "Sem conexão com a Matriz".
- **Disponibilidade:** percentual das últimas 24 h e 7 dias, com uma barra colorida por dia.
- **Ocorrências dos últimos 7 dias** em linguagem simples, com duração.
- **Último failover:** quantos segundos os usuários ficaram sem conexão na última troca automática.
- Enquanto o host estiver em manutenção, uma faixa avisa que o ambiente está em implantação.

## 6. Notificações por e-mail

Cada problema do grupo gera até três e-mails para `matheus.ziravello@aluno.senai.br`: o alerta na abertura, a análise da IA cerca de 1 minuto depois e a normalização quando resolve. Os três foram recebidos no teste de 03/10/2026; aparecem com remetente "eu" porque saem da própria conta.

### Tipo de mídia "Gmail Alertas SENAI"

| Campo | Valor |
| --- | --- |
| Servidor SMTP | `smtp.gmail.com`, porta 587, STARTTLS |
| Conta e remetente | `matheus.ziravello@aluno.senai.br` |
| Autenticação | Senha de app do Google (a conta tem verificação em duas etapas; a senha normal é recusada com erro 534) |
| Formato | HTML |
| Destinatário | Mídia do usuário Admin, todas as severidades, 24x7 |

### Ações

| Ação | Estado | O que faz |
| --- | --- | --- |
| Notificação NOC - Redundância e Enlaces | Ativa | Alerta "\[ALERTA NOC SENAI\]" na abertura e "\[NORMALIZADO NOC SENAI\]" na recuperação, para o grupo Rede SENAI - Equipamentos |
| Analista IA - Investigação de incidentes | Ativa | Chama o Analista IA na abertura; quando a IA comenta o evento, envia o comentário por e-mail como "\[ANÁLISE IA\]" |
| Notificação de Redundância - Link Fibra/Rádio | Desativada | Duplicada e sem filtro: mandava cada alerta duas vezes e incluía alertas do próprio Zabbix server |

Problemas suprimidos por manutenção não geram e-mail (opção "pausar operações para problemas suprimidos").

Dica: no Gmail, um filtro com assunto `NOC SENAI` que aplica o marcador "NOC" e marca como importante deixa os alertas fáceis de achar na apresentação.

## 7. Analista NOC com IA

O Analista IA é um serviço Python na VM (`noc-analista`) que recebe cada problema novo do Zabbix, investiga sozinho com ferramentas somente leitura e publica um relatório em cerca de 20 s. Ele usa o Google Gemini na camada gratuita, sem custo.

### Fluxo de um incidente

1. O Zabbix abre o problema e a ação "Analista IA" chama o webhook `Analista IA`, que faz `POST http://127.0.0.1:8765/evento`.
2. O serviço espera **60 s** juntando os eventos do mesmo host (ex.: "fibra caiu" + "ether2 link down" viram um incidente só).
3. A IA recebe a lista de eventos, a topologia e as regras de interpretação, e chama as ferramentas que achar necessárias.
4. O relatório vira um comentário no evento, assinado pelo usuário `noc-analista`, e fica salvo em `/var/lib/noc-analista/`.
5. O comentário dispara a operação de atualização da ação, que envia o e-mail "\[ANÁLISE IA\]".

O comentário usa um usuário próprio porque o Zabbix não notifica o autor de uma atualização sobre ela mesma: comentando como Admin, o e-mail para o Admin nunca sairia.

### Ferramentas da IA (somente leitura)

| Ferramenta | O que devolve |
| --- | --- |
| `estado_atual` | Disponibilidade SNMP, caminho ativo, estado e latência de cada enlace, problemas ativos |
| `historico_item` | Mudanças UP/DOWN com horário, ou mínimo/média/máximo de uma métrica |
| `eventos_recentes` | Problemas das últimas horas com duração (detecta link instável) |
| `listar_itens` | O que o Zabbix coleta do host (tráfego, CPU, interfaces) |
| `medir_failover` | Para cada queda e retorno da fibra, quantos segundos a LAN da Filial ficou sem resposta (ping a cada 1 s) |
| `consultar_mikrotik` | SSH no R-FILIAL com usuário `zabbix-ia` (grupo read): interfaces, erros Ethernet, vizinhos OSPF, rotas, log, recursos. Lista fixa de comandos |

O cálculo do `medir_failover` foi validado com dados simulados: uma queda com 6 s de interrupção foi medida como 6 s, e um retorno sem perda como "troca transparente".

### Provedor de IA

| Provedor | Quando é usado | Custo |
| --- | --- | --- |
| Google Gemini (`gemini-3.5-flash`, depois `gemini-flash-latest`, depois `gemini-flash-lite-latest`) | Padrão, chave em `/root/.gemini_key` | Gratuito (o Google pode usar os dados enviados para melhorar modelos) |
| Anthropic Claude (`claude-opus-5-5`) | Só se existir `/root/.anthropic_key`; tem prioridade | Pago por uso |

A camada gratuita do Gemini responde "503 alta demanda" com frequência. O serviço tenta cada modelo duas vezes e passa para o próximo; no teste real isso aconteceu e a análise saiu normalmente.

### Proteções

- **Custo e ruído:** o mesmo problema não é reanalisado antes de 15 min, e há no máximo 12 análises por hora.
- **Somente leitura:** nenhuma ferramenta altera o Zabbix ou o roteador.
- **Sem loop:** atualizações e recuperações são ignoradas, então o próprio comentário da IA não dispara nova análise.
- **Honestidade:** a IA é instruída a afirmar só o que os dados mostram, a dizer qual dado faltou e a dar confiança alta apenas quando a evidência aponta para uma única causa.

### Exemplo real (03/10/2026, bancada desmontada)

Gerado pelo `gemini-3.5-flash` em 17 s, após 8 consultas às ferramentas. Trecho:

```text
RESUMO: O roteador R-FILIAL está completamente isolado, com ambos os enlaces
(Fibra e Rádio) indisponíveis. O host está marcado como em manutenção no Zabbix.

LINHA DO TEMPO:
- 10:20:41  Ambos os enlaces já estavam DOWN desde o início da medição.
- 10:21:32  Alerta de indisponibilidade por ICMP ping é ativado.

CAUSA PROVÁVEL: Manutenção programada ou intervenção física no local
(confiança média). [...] o Zabbix perdeu toda a visibilidade da Filial,
impossibilitando distinguir remotamente se o equipamento está sem energia,
se foi desligado ou se houve falha física simultânea.

AÇÕES RECOMENDADAS:
1. Confirmar se há manutenção ativa ou se o R-FILIAL está em bancada.
2. Verificar presencialmente se o roteador está ligado e recebendo energia.
3. Checar os LEDs das portas ether2 (Fibra) e ether3 (Rádio).
```

A causa apontada (equipamento em bancada) era a verdadeira. Duas falhas da primeira versão foram corrigidas antes deste resultado: a IA afirmava que a fibra "caiu" no horário em que a medição apenas começou, e dava confiança alta para três causas alternativas. Os relatórios de failover real (fibra cai, rádio assume) só poderão ser avaliados com a bancada montada.

## 8. Segurança

Cada componente tem só a permissão de que precisa, e nenhuma senha ou chave fica escrita nos scripts: todas ficam em arquivos `chmod 600` lidos só pelo root.

| Credencial | Onde fica | Quem usa |
| --- | --- | --- |
| Token da API do Zabbix (Admin) | `/root/.zabbix_token` | Scripts de configuração e ferramentas da IA |
| Token do usuário `noc-analista` | `/root/.zabbix_token_analista` | Só para comentar eventos |
| Chave do Gemini | `/root/.gemini_key` | Analista IA |
| Chave SSH do analista | `/root/.ssh/id_ed25519_mikrotik` | Consultas de leitura no R-FILIAL |
| Senha de app do Gmail | Dentro da mídia do Zabbix (banco) | Envio de e-mail |
| Acesso SSH à VM | Chave `id_ed25519_zabbix` no notebook | Administração |

Medidas aplicadas:

- **Usuário `noc-analista` no Zabbix:** papel "User", grupo "NOC Automação" sem acesso ao frontend, leitura só no grupo Rede SENAI - Equipamentos.
- **Usuário `zabbix-ia` no MikroTik:** grupo `read`, login só por chave, e a IA executa apenas uma lista fixa de 6 comandos de consulta.
- **SNMP:** v2c somente leitura, aceito apenas do IP do Zabbix (192.168.10.50); a comunidade padrão `public` é desativada.
- **Firewall do R-FILIAL:** SNMP (UDP 161) e SSH (TCP 22) liberados só para o Zabbix, antes do drop final.
- **Serviço do analista:** ouve apenas em `127.0.0.1:8765`, inacessível pela rede.
- **Scripts antigos:** movidos para `/root/scripts-antigos/` com as senhas removidas.

Pendências recomendadas:

- [ ] Revogar a senha de app do Gmail que foi exposta em chat e gerar uma nova
- [ ] Trocar a senha pessoal do Gmail que também foi exposta
- [ ] Trocar a senha padrão do usuário Admin do Zabbix
- [ ] Trocar `TROQUE_POR_UMA_SENHA_FORTE` no script do R-FILIAL antes de colar

## 9. Dia da montagem

No Zabbix nada precisa ser mexido: com a rede montada e o script abaixo colado no R-FILIAL, os enlaces ficam verdes em até 1 minuto e a manutenção se encerra sozinha.

### Checklist

- [ ] Colar os scripts principais do R-MATRIZ e do R-FILIAL (documento da topologia)
- [ ] Colar no R-FILIAL o bloco de integração com o NOC (abaixo), com a senha trocada
- [ ] Ligar o cabo do notebook no SW-MATRIZ, com o Wi-Fi conectado à internet
- [ ] Conferir no VMware que o VMnet0 está preso à placa Killer (cabo)
- [ ] No Debian: `ping 192.168.10.1`, `ping 10.0.1.2` e `ping 10.0.2.2` respondem
- [ ] No Debian: `snmpget -v2c -c public_senai 192.168.20.1 1.3.6.1.2.1.1.5.0` devolve `R-FILIAL`
- [ ] Dashboard: FIBRA e RÁDIO verdes, disponibilidade SNMP verde
- [ ] Rodar o roteiro de testes de failover

### Bloco de integração para o R-FILIAL

Arquivo `routeros-r-filial-noc.rsc`. O `security=none` é obrigatório no SNMP v2c: o `security=private` dos scripts antigos exigia SNMPv3 e o Zabbix nunca conseguiria ler o roteador.

```text
:local ZABBIX "192.168.10.50"
/snmp community set [find default=yes] disabled=yes
/snmp community add name=public_senai addresses=$ZABBIX security=none read-access=yes write-access=no
/snmp set enabled=yes contact="NOC SENAI TCC" location="Rack Filial"
/ip firewall filter add chain=input action=accept protocol=udp dst-port=161 src-address=$ZABBIX comment="NOC: Zabbix SNMP"
/ip firewall filter add chain=input action=accept protocol=tcp dst-port=22 src-address=$ZABBIX comment="NOC: Analista IA SSH (leitura)"
/ip firewall filter move [find comment="NOC: Zabbix SNMP"] destination=0
/ip firewall filter move [find comment="NOC: Analista IA SSH (leitura)"] destination=1
/user add name=zabbix-ia group=read password="TROQUE_POR_UMA_SENHA_FORTE" comment="Analista IA - somente leitura"
/user ssh-keys add user=zabbix-ia key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ6p8g/oAtn3KK0x8Tze43LoZ5JZ6vePhG3ihVcCquum noc-analista@zabbix"
```

A sintaxe `ssh-keys add ... key=` não foi confirmada na versão do RouterOS da bancada. Se der erro, a alternativa é enviar o arquivo `.pub` ao roteador e usar `/user ssh-keys import`.

### Roteiro de testes de failover

| Teste | Comando no R-FILIAL | Resultado esperado |
| --- | --- | --- |
| 1. Queda da fibra | `/interface disable ether2-WAN-FIBRA` | Em \~20 s: FIBRA vermelho, trigger "Link FIBRA caiu: failover para RÁDIO ativo", e-mail de alerta; em \~1 min: e-mail "\[ANÁLISE IA\]" confirmando o failover e o tempo medido em segundos |
| 2. Volta da fibra | `/interface enable ether2-WAN-FIBRA` | FIBRA verde, e-mail "\[NORMALIZADO NOC SENAI\]" |
| 3. Queda do rádio | `/interface disable ether3-WAN-RADIO` | Trigger "rede sem redundância" (Média), alerta e análise |
| 4. Fibra instável | Desligar e religar a ether2 3 vezes em poucos minutos | Trigger "Link FIBRA instável"; a IA deve apontar problema físico |
| 5. Filial isolada | Desligar ether2 e ether3 | Trigger de Desastre; a IA deve dizer que perdeu a visibilidade e listar verificações físicas |

O mesmo problema só é reanalisado pela IA após 15 min. Para repetir um teste antes disso, rode `systemctl restart noc-analista` na VM.

## 10. Operação e solução de problemas

Quase todo problema se diagnostica com três comandos na VM: o estado dos serviços, o log do analista e o log do Zabbix.

### Comandos úteis (na VM, como root)

| Para | Comando |
| --- | --- |
| Ver se tudo está rodando | `systemctl status zabbix-server apache2 mariadb noc-analista` |
| Saúde e provedor do analista | `curl -s localhost:8765/saude` |
| Log do analista em tempo real | `journalctl -u noc-analista -f` |
| Log do Zabbix server | `tail -f /var/log/zabbix/zabbix_server.log` |
| Relatórios da IA já gerados | `ls -lt /var/lib/noc-analista/` |
| Analisar o problema ativo agora, sem enviar | `cd /root/noc && /opt/noc-analista/bin/python analista.py --simular` |
| O mesmo, comentando e enviando e-mail | `... analista.py --simular --publicar` |
| Testar o fluxo inteiro até o e-mail (sem IA) | `touch /root/noc/MODO_TESTE && systemctl restart noc-analista && /opt/noc-analista/bin/python teste_integracao.py; rm /root/noc/MODO_TESTE && systemctl restart noc-analista` |
| Testar as ferramentas da IA | `/opt/noc-analista/bin/python testar_ferramentas.py` |
| Ver rede da VM | `ip -4 -br a` e `nmcli con show` |

### Erros comuns

| Sintoma | Causa provável | Correção |
| --- | --- | --- |
| SNMP vermelho, mas os enlaces respondem ping | Comunidade, `security=private` ou firewall do R-FILIAL | Conferir o bloco de integração (seção 9) e testar com `snmpget` |
| Enlaces DOWN com tudo ligado | VM sem rota ou bridge no Wi-Fi | `ip route` deve mostrar 10.0.0.0/8 e 192.168.20.0/24 via 192.168.10.1; conferir VMnet0 |
| Nenhum e-mail chega | Host em manutenção ou senha de app revogada | Em Reports > Action log, ver o status do alerta; erro 534 = gerar nova senha de app |
| Alerta chega, análise IA não | Gemini indisponível, chave ausente ou cooldown de 15 min | `journalctl -u noc-analista -n 50`; "todos os modelos indisponíveis" = tentar mais tarde |
| Análise IA chega cortada | Comentário do Zabbix limitado a 2048 caracteres | Relatório completo em `/var/lib/noc-analista/` |
| Após um `apt upgrade` a sessão SSH caiu | Serviços de rede reiniciados | Rodar upgrades dentro de `tmux` ou `screen` |

### Quando o modelo do Gemini sair do ar

O Google retira versões antigas (o `gemini-2.5-flash` já não existe para contas novas). Se todos os modelos da lista falharem com erro 404, edite `MODELOS` em `/root/noc/provedor_gemini.py` com um nome atual e rode `systemctl restart noc-analista`.

## 11. Arquivos e scripts

O código-fonte fica na pasta `Documents\Claude\noc-analista` do notebook, com cópia em execução na VM em `/root/noc`. Todos os scripts de configuração podem ser rodados de novo sem duplicar nada.

| Arquivo | Função |
| --- | --- |
| `zbx.py` | Cliente da API do Zabbix (token Admin e token do analista) |
| `fix_redundancia.py` | Host na LAN, template MikroTik, itens de enlace, caminho ativo, alcance 1 s, perdas, triggers de queda e de previsão, manutenção |
| `dash_enlaces.py` / `dash_noc.py` | Dashboard NOC do Zabbix (3 páginas) |
| `mapa_topologia.py` | Mapa da topologia com enlaces coloridos por trigger |
| `setup_grafana.py` / `testar_grafana.py` | Configuração completa do Grafana e teste dos painéis |
| `status_page.py` | Página de status para os usuários (cron a cada minuto) |
| `failover_registro.py` | Grava o tempo de cada failover no item `noc.failover.segundos` (cron a cada minuto) |
| `auto_fim_manutencao.py` | Encerra a manutenção quando um enlace responde (cron a cada minuto) |
| `setup_zabbix_analista.py` | Webhook, ação "Analista IA", usuário `noc-analista` e seu token |
| `analista.py` | Serviço do Analista IA: recebe, agrupa, investiga, publica |
| `ferramentas.py` | As 6 ferramentas somente leitura da IA |
| `provedor_gemini.py` / `provedor_teste.py` | Provedor Gemini gratuito e provedor de teste sem IA |
| `testar_ferramentas.py` / `teste_integracao.py` | Testes das ferramentas e do fluxo completo até o e-mail |
| `noc-analista.service` | Unidade systemd (`/etc/systemd/system/`) |
| `routeros-r-filial-noc.rsc` | Bloco de integração para colar no R-FILIAL |

Na VM também ficam: o ambiente Python em `/opt/noc-analista` (SDKs `google-genai` e `anthropic`), os relatórios em `/var/lib/noc-analista/` e os scripts antigos, sem senhas, em `/root/scripts-antigos/`.

## 12. Próximos passos: usos da IA e ideias de inovação

O Analista IA hoje cobre a análise de cada incidente; as listas abaixo são candidatas para expandir o projeto, não itens já implementados (exceto onde indicado).

### 20 usos da IA neste projeto

1. Análise de causa de cada incidente (implementado)
2. Medir o tempo de failover: quantos segundos o OSPF levou para passar o tráfego ao rádio (implementado)
3. Relatório semanal de disponibilidade: quanto cada enlace ficou no ar e quanto tempo a rede rodou pelo rádio
4. Detectar fibra instável e recomendar manutenção antes da queda definitiva
5. Prever falha do rádio percebendo a latência subindo aos poucos (implementado)
6. Auditoria diária da configuração: comparar o `/export` do MikroTik com a versão aprovada
7. Revisão de segurança do roteador: admin reativado, serviços abertos, regras de firewall fracas
8. Chat NOC: perguntas em português, como "quanto tempo ficamos no rádio hoje?"
9. Resumo de troca de plantão com o que aconteceu nas últimas 8 horas
10. Pós-incidente automático quando o problema resolve: duração, impacto e lições
11. Correlação de eventos num incidente só (implementado em parte, com a janela de 60 s)
12. Prioridade inteligente: tratar diferente o mesmo alerta em manutenção e em produção
13. Sugerir limites melhores para os triggers com base no histórico real
14. Documentação viva: inventário e plano de IPs gerados a partir dos dados coletados
15. Validação do MTU 2000 de ponta a ponta com teste guiado e laudo
16. Roteiro guiado de teste de failover para a banca, com laudo automático
17. Capacidade: avaliar se o rádio aguenta o tráfego que a fibra carrega
18. Explicar cada alerta em linguagem simples para técnicos iniciantes
19. Gerar o script de uma nova filial a partir do modelo, para revisão humana
20. Analisar os logs do MikroTik em busca de força bruta e comportamento estranho

### Ideias para inovar

- **Integração com o assistente de voz JARVIS:** "Jarvis, como está a rede?" e aviso falado quando a fibra cai.
- **Bot no Telegram ou WhatsApp** com botões "ver análise" e "reconhecer alerta".
- **Mapa da topologia no Zabbix ou no Grafana**, com os enlaces mudando de cor ao vivo (implementado no Zabbix).
- **Monitorar o R-MATRIZ e as duas antenas** para a IA distinguir defeito de antena de defeito de roteador.
- **Detecção instantânea:** o MikroTik avisa o Zabbix na hora da queda (SNMP trap ou netwatch), em vez de esperar o próximo ping.
- **Correção com aprovação humana:** a IA sugere um comando e um botão no e-mail autoriza a execução.
- **Página de status** para os usuários da Filial, como as empresas fazem (implementado).
- **Relatório mensal em PDF** gerado automaticamente para a gerência.
- **Backup das configurações em Git**, com a IA explicando o que mudou de um dia para o outro.
- **Experimento para o TCC:** comparar IA na nuvem (Gemini) e IA local (Ollama) em qualidade, tempo e custo.
- **Avaliação da IA:** botão "útil / não útil" em cada análise, gerando métricas de precisão para a monografia.
- **Testes de falha agendados:** derrubar a fibra de propósito toda semana, com aprovação, e medir se a redundância continua funcionando.
