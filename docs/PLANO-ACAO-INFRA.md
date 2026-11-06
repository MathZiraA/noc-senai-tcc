# Plano de Ação — Melhoria da Infraestrutura do NOC

05/nov/2026 · @Matheus

> Plano para endurecer a infraestrutura **que já existe hoje**: um servidor Dell (gerenciado por iDRAC) rodando o ESXi, com uma VM Debian que concentra todo o NOC (Zabbix, Grafana, SennaGuard e o Analista IA). Não pressupõe compra de hardware novo.

## 1. Diagnóstico

### 1.1 Falha principal — Ponto Único de Falha (SPOF)

Todo o NOC vive em **uma única VM**, dentro de **um único servidor físico**. Os backups de configuração dos roteadores ficam **dentro da própria VM** que deveriam proteger. Se a VM for apagada/corrompida ou o servidor falhar, perde-se o monitoramento **e** os backups de uma só vez.

A redundância Fibra/Rádio/WAN construída no projeto protege o **tráfego dos clientes** — ela **não** protege o próprio NOC.

> **Verdade de engenharia a assumir na banca:** com **um único servidor físico**, o SPOF de host **não pode ser eliminado** por software (nem com mais VMs, nem com Kubernetes). Reconhecer isso e mitigar com backup externo, reconstrução rápida e detecção precoce é o caminho tecnicamente honesto.

### 1.2 Vulnerabilidades secundárias

| # | Vulnerabilidade | Impacto |
|---|---|---|
| V1 | Cópia da VM contém todos os segredos (senhas, tokens, chaves) | Vazamento = comprometimento total |
| V2 | Gerência (switch, VM, roteadores) na mesma faixa dos usuários (sem VLAN) | Exposição do plano de gerência |
| V3 | SNMP v2c com community em texto claro (`public_senai`) | Leitura da gerência por quem esnifar o segmento |
| V4 | SSH do switch oferece KEX legado (group1/14-sha1) | Algoritmos criptográficos fracos |
| V5 | Chave `mikrotik_key` read-only na VM | Se a VM cair, dá leitura dos roteadores |

### 1.3 Risco aceito (fora do escopo)

- **`root` compartilhado no ESXi** entre os grupos da turma — **aceito** por ser ambiente de testes/laboratório. Decisão do responsável pelo projeto.

## 2. Princípio norteador

Com um servidor único, a resiliência não vem de "software redundante", vem de três pilares:

1. **Backup para fora do servidor** (sobreviver à perda total).
2. **Reconstrução rápida e testada** (baixar o tempo de recuperação — RTO).
3. **Detecção precoce da falha de hardware** (ganhar aviso antes de cair).

**Metas:** RPO ≤ 24 h (perda máxima de 1 dia) · RTO ≤ 2 h (NOC de volta em até 2 horas).

## 3. Plano de ação por fases

### Fase 1 — Começar hoje (sem hardware novo)

| Ação | O que faz | Risco tratado | Esforço | Status |
|---|---|---|---|---|
| **1.1 Backup puxado de fora** | Uma máquina externa (notebook/HD/NAS) busca diariamente o `.rsc` dos roteadores e um dump do SennaGuard da VM — não a VM que empurra | SPOF / V1 | Baixo | ☐ |
| **1.2 Proteger a cópia da VM** | Mover o `.vmdk/.ovf/.nvram` para disco externo **criptografado** (BitLocker/VeraCrypt); nunca em nuvem nem no repositório | V1 | Baixo | ☐ |
| **1.3 Roteiro "do zero ao NOC"** | Documento testado que reconstrói a VM a partir do repositório + dump do banco | SPOF (RTO) | Médio | ☐ |
| **1.4 Conferir RAID na iDRAC** | Ver em *Storage* quantos discos há e se estão em RAID (redundância de disco é a única de hardware já disponível) | SPOF parcial | Baixo | ☐ |

### Fase 2 — Detecção e segmentação

| Ação | O que faz | Risco tratado | Esforço | Status |
|---|---|---|---|---|
| **2.1 iDRAC → Zabbix** | Monitorar o **próprio servidor** (temperatura, fontes, discos, RAID, memória) via Redfish/SNMP da iDRAC — aviso antes da falha do ponto único | SPOF (detecção) | Médio | ☐ |
| **2.2 VLAN de gerência** | Isolar gerência (switch/VM/roteadores) numa VLAN separada da faixa dos usuários | V2, resolve metade de V3 | Médio | ☐ |
| **2.3 SNMP v2c → v3** | Trocar community em claro por SNMPv3 (auth SHA + priv AES); senha definida e digitada pelo usuário | V3 | Médio | ☐ |

### Fase 3 — Endurecimento final

| Ação | O que faz | Risco tratado | Esforço | Status |
|---|---|---|---|---|
| **3.1 SSH forte no switch** | Atualizar firmware; restringir gerência a um único host; remover KEX legado | V4 | Médio | ☐ |
| **3.2 Rotação da `mikrotik_key`** | Gerar novo par, trocar as públicas nos equipamentos; garantir `chmod 600` e dono correto na VM | V5 | Baixo | ☐ |
| **3.3 Separar Zabbix/Grafana em VM própria** | Tirar monitoramento e aplicação do mesmo destino (reduz raio de dano de software) | Resiliência | Médio | ☐ |

## 4. Matriz de risco (antes do plano)

| Risco | Probabilidade | Impacto | Severidade |
|---|---|---|---|
| Perda total da VM/servidor (SPOF) | Média | Crítico | 🔴 Alta |
| Vazamento da cópia com segredos (V1) | Baixa | Crítico | 🟠 Média-alta |
| Falha de disco sem RAID | Média | Alto | 🟠 Média-alta |
| Interceptação da gerência (V2/V3) | Baixa | Médio | 🟡 Média |
| SSH/chave comprometidos (V4/V5) | Baixa | Médio | 🟡 Média |

## 5. Decisão sobre Kubernetes

Com **um único host físico**, Kubernetes **não entra como solução de redundância** — a redundância de K8s é entre nós, e todos os nós (VMs) compartilhariam o mesmo servidor. Usá-lo e chamá-lo de "redundante" seria incorreto.

**Veredito:** K8s só se justifica aqui como **estudo/demonstração acadêmica**. Se adotado, usar **k3s** (nó único, leve), **apenas no SennaGuard** (stateless-friendly), mantendo Zabbix + banco fora dele, e **declarar na documentação** que oferece self-healing e rolling updates **a nível de pod, sem HA de host**.

## 6. O que destrava o início

Pendências de informação (não de hardware) para detalhar Fase 1 e 2:

- **Modelo do Dell** (ex.: R740/R640) — para acertar Redfish/SNMP da iDRAC (ação 2.1).
- **RAID na iDRAC** — quantos discos e em que configuração (ação 1.4).
- **Switch real da Matriz** — MikroTik ou o Cisco que apareceu no SNMP (`Gi1/0/x`) — define o script de VLAN e SSH (ações 2.2 e 3.1).

As ações **1.1** (backup externo) e **1.3** (roteiro de reconstrução) podem começar **sem nenhuma dessas respostas**.
