# Roteiro da demonstração prática — Ataque DoS e defesa ao vivo

Demonstração de que o servidor do NOC **detecta, resiste e alerta** em um ataque de negação de serviço
(DoS) à camada web — o mesmo tipo de ataque que, antes da blindagem, derrubava o site.

- **Atacante:** o notebook da Matriz (`192.168.10.199`), rodando no PowerShell.
- **Alvo:** o site SennaGuard (`https://192.168.10.50/sennaguard/`).
- **Duração:** ~3 minutos (90 s de ataque + reação + recuperação).

---

## 0. Preparação (antes de começar a falar)

### 0.1 Abrir as 4 abas no Chrome (já abertas; confira a ordem)

| Aba | Endereço | Para quê | Login |
| --- | --- | --- | --- |
| 1 | `https://192.168.10.50/sennaguard/` | mostrar o site **no ar** | seu |
| 2 | `https://192.168.10.50:3000/d/noc-redundancia` | painel Fibra x Rádio (Parte 1) | não |
| 3 | `https://192.168.10.50:3000/d/noc-servidor` | **painel do ataque** (principal) | não |
| 4 | `https://192.168.10.50/zabbix/zabbix.php?action=problem.view` | **onde os alertas aparecem** | seu |

### 0.2 Fazer login no **Zabbix** (aba 4) e no **SennaGuard** (aba 1). As do Grafana abrem direto.

### 0.3 Na aba 3 (Grafana Servidor): canto superior direito, trocar **"Atualizar 30s" → 5s**.

### 0.4 Liberar o IP do atacante no fail2ban (senão ele bane em 2 s e corta o efeito). No PowerShell:

```powershell
ssh -i ~/.ssh/id_ed25519_zabbix root@192.168.10.50 "fail2ban-client set noc-http-flood addignoreip 192.168.10.199"
```
Resposta esperada: `These IP addresses/networks are ignored: 192.168.10.199`

### 0.5 Gerar a lista de URLs do ataque (uma vez). No PowerShell:

```powershell
Set-Content "$env:TEMP\urls.txt" (,'url = "https://192.168.10.50/sennaguard/"' * 5000)
```

---

## 1. Ato 1 — "O servidor está saudável" (~20 s)

**Mostre a aba 3 (Grafana Servidor).** Aponte para:
- Os **6 cartões do topo** — todos **verdes**: `SYN_RECV 0`, `Conexões no site 0`, `Apache ocupados` baixo, `IP mais frequente 1`, `fail2ban banidos 0`, `SSH falhas 0`.
- Os gráficos embaixo, calmos.

**Fale:** "O servidor se auto-monitora no Zabbix. Cada métrica aqui é um sinal de ataque. Agora está tudo em paz."

**Mostre a aba 4 (Zabbix Incidentes):** a lista de problemas está **vazia**.

---

## 2. Ato 2 — "Vou simular um ataque DoS" (dispara e volta pro Grafana)

**No PowerShell, rode o ataque** (4 processos paralelos, 90 s, para sozinho):

```powershell
$u = "$env:TEMP\urls.txt"; $fim = (Get-Date).AddSeconds(90); 1..4 | % { Start-Job { param($u,$f) while((Get-Date) -lt $f){ curl.exe -s -k -Z --parallel-max 80 -K $u -o NUL } } -ArgumentList $u,$fim | Out-Null }; "Ataque rodando 90s..."; Get-Job | Wait-Job | Out-Null; Get-Job | Remove-Job; "Ataque encerrado."
```

**Fale enquanto digita:** "Estou disparando centenas de conexões por segundo contra o site, de um único computador — um flood, como um ataque de negação de serviço."

**Troque imediatamente para a aba 3 (Grafana Servidor).**

---

## 3. Ato 3 — "As defesas reagem" (ao vivo, ~90 s) — **aba 3, Grafana**

Com o refresh em 5 s, em poucos segundos (ONDE CADA COISA APARECE):

| O que observar | Onde, na aba 3 | O que acontece |
| --- | --- | --- |
| **Conexões no site** | cartão do topo (2º) + gráfico "Conexões no site (80/443)" | sobe para ~**100** e fica **vermelho** |
| **IP mais frequente** | cartão do topo (4º) | pula para ~**100** e fica **vermelho** (um único IP concentrando tudo) |
| **Apache ocupados** | cartão do topo (3º) + gráfico "Apache: workers ocupados x livres" | sobe (workers trabalhando), mas **não estoura** |
| **Firewall: descartados/s** | gráfico de baixo à direita | **sobe** — o firewall está cortando o excesso |
| **Estados de conexão TCP** | gráfico de baixo à esquerda | a linha de conexões sobe |

**Fale:** "Vejam: o firewall limita as conexões por IP, o mod_evasive responde com erro 403, e o Apache não satura. As três camadas estão segurando o ataque."

### 3.1 O golpe de cena — **aba 1 (SennaGuard)**
**Troque para a aba 1 e aperte F5.** O site **carrega normalmente**.

**Fale:** "Durante o ataque, o site continua no ar. Antes da blindagem, esse mesmo flood derrubava o SennaGuard."

---

## 4. Ato 4 — "O NOC percebe e avisa" (~1 min de ataque) — **aba 4, Zabbix**

Depois de ~1 minuto de ataque sustentado, **troque para a aba 4 (Zabbix Incidentes)** e **atualize (F5)**. Aparecem **linhas coloridas** na lista de problemas:

| Alerta (texto na lista) | Cor / Severidade | Quando |
| --- | --- | --- |
| **Firewall descartando muito tráfego (varredura ou flood)** | 🟡 amarelo (Aviso) | ~15 s |
| **Flood de origem única: um IP concentra muitas conexões** | 🔴 vermelho (Alta) | ~1 min |

**Fale:** "O Zabbix dispara os alertas automaticamente, classificados por severidade."

### 4.1 A investigação por IA — **aba 4, clicando no alerta**
**Clique no alerta vermelho** "Flood de origem única" → abre o detalhe do evento. **Role até os comentários**: o **Analista IA (Gemini)** deixou um laudo com `RESUMO`, `CAUSA PROVÁVEL` e `AÇÃO RECOMENDADA`.

**Fale:** "Além de alertar, o sistema aciona um analista de IA que investiga sozinho e sugere a causa e a ação."

### 4.2 (Opcional) O e-mail — **5ª aba, seu webmail @aluno.senai.br**
Mostre o e-mail **🚨 [ALERTA NOC SENAI]** que chegou na abertura do incidente.

---

## 5. Ato 5 — "Fim do ataque e recuperação" (~2 min)

O ataque para sozinho aos 90 s (o PowerShell mostra `Ataque encerrado.`).

- **Aba 3 (Grafana):** os cartões voltam ao **verde**, os gráficos descem.
- **Aba 4 (Zabbix):** atualize (F5) → os problemas **somem** (resolvidos) em ~1–2 min.
- **(Opcional) E-mail:** chega o **✅ [NORMALIZADO NOC SENAI]**.

**Fale:** "Assim que o ataque cessa, o sistema se normaliza sozinho e registra o fim do incidente."

---

## 6. Limpeza (depois da apresentação)

Remover a liberação temporária do atacante no fail2ban:

```powershell
ssh -i ~/.ssh/id_ed25519_zabbix root@192.168.10.50 "fail2ban-client set noc-http-flood delignoreip 192.168.10.199"
```

---

## 7. Se algo der errado (plano B)

| Problema | Solução |
| --- | --- |
| Os alertas não aparecem | O ataque precisa de ~1 min **sustentado**. Confira que o PowerShell mostra "Ataque rodando 90s..." e que o IP foi liberado no fail2ban (passo 0.4). |
| Quero parar o ataque antes | `Get-Job | Stop-Job; Get-Job | Remove-Job` |
| `curl` dá erro no PowerShell | Use `curl.exe` (o `curl` puro é atalho do `Invoke-WebRequest`). O comando do roteiro já usa `curl.exe`. |
| O site não abre (aviso de certificado) | Instale a CA do NOC no PC: baixe `http://192.168.10.50/NOC-SENAI-CA.crt` e `certutil -user -addstore Root <arquivo>`. |
| Grafana sem dados ao vivo | Confirme o refresh em 5 s (canto superior direito) e o período "Últimas 3 horas". |

---

## Resumo visual do fluxo

```
PowerShell (ataque)  ─→  Grafana aba 3 (métricas sobem)  ─→  site aba 1 (continua no ar)
                                      │
                                      ▼
                         Zabbix aba 4 (alertas 🟡🔴 + laudo da IA)  ─→  e-mail [ALERTA]
                                      │  (ataque para)
                                      ▼
                         tudo volta ao verde  ─→  e-mail [NORMALIZADO]
```
