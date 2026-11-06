# SennaGuard: atualizar o painel e validar a rede (para a sessão do Claude no servidor)

Você é uma sessão do Claude com terminal no servidor do NOC (Debian 12, `192.168.10.50`), direto ou por SSH a partir de um notebook da Matriz.

**Situação:** o SennaGuard já foi instalado, mas a rede ainda não estava montada nesse dia: MikroTik R-MATRIZ e R-FILIAL, fibra, rádio e antenas. Tudo o que depende da rede ficou sem fazer ou sem conferir. Agora a rede está montada.

**Sua tarefa, em ordem:**

- **A.** Confirmar que a rede está de pé.
- **B.** Atualizar o SennaGuard para a última versão do GitHub.
- **C.** Refazer as etapas de rede do roteiro.
- **D.** Testar de ponta a ponta com o usuário.
- **E.** Entregar o relatório.

## Antes de começar

1. Leia o roteiro principal inteiro. Ele tem os comandos detalhados das etapas citadas aqui:
   `curl -s https://raw.githubusercontent.com/MathZiraA/sennaguard/main/docs/IMPLANTACAO-SERVIDOR.md`
2. Siga as **Regras de segurança** do roteiro à risca:
   - nunca altere os MikroTik: comandos RouterOS vão prontos para o usuário colar no WinBox;
   - nunca derrube a fibra nem rode ou aprove teste de failover;
   - nunca mostre segredos: tokens, chaves privadas, community SNMP, `.env`;
   - não edite `/opt/sennaguard` e não faça `git push`;
   - no Zabbix, só acrescente.
3. Rodando no notebook, siga a seção do roteiro "Se a sessão roda no notebook da Matriz": todo comando roda no servidor, via `ssh root@192.168.10.50`.
4. Quando um passo for do usuário, pare, diga exatamente o que ele deve fazer e espere a confirmação.

## Fase A: a rede está de pé? (só leitura)

Leia os endereços do `/etc/noc/noc.conf`, sem exibir `SNMP_COMMUNITY`, e monte uma tabela **alvo | esperado | resultado**.

```bash
C=/etc/noc/noc.conf; v() { grep -E "^$1=" $C | cut -d= -f2- | tr -d "\"' "; }
for alvo in "$(v LOOPBACK_MATRIZ)" "$(v LOOPBACK_FILIAL)" "$(v FIBRA_FILIAL)" "$(v RADIO_FILIAL)" 10.0.2.3 10.0.2.4 192.168.20.1; do
  [ -n "$alvo" ] && printf '%-16s ' "$alvo" && (ping -c3 -W1 -q "$alvo" | tail -1 || echo SEM RESPOSTA); done
systemctl is-active zabbix-server apache2 noc-analista sennaguard
```

Confira também:

1. **Zabbix pela API**, com o token de `/root/.zabbix_token` e sem exibi-lo:
   - disponibilidade (`host.get` com `active_available`/interfaces) de R-FILIAL, R-MATRIZ (se existir), RADIO-P2P-MATRIZ e RADIO-P2P-FILIAL;
   - último valor e horário de `icmpping` da fibra e do rádio e de `noc.caminho_ativo`.
2. **Leitura nos MikroTik** como o serviço, com o mesmo `$O` da Etapa 3 do roteiro:
   - `runuser -u sennaguard -- ssh -i /etc/sennaguard/mikrotik_key $O zabbix-ia@<LOOPBACK_FILIAL> '/interface print; /routing ospf neighbor print'`
   - O OSPF precisa estar em `Full` pelas duas portas: fibra sfp1 e rádio ether1.
3. **SNMP das antenas**, sem mostrar a community:
   `snmpget -v2c -c "$(v SNMP_COMMUNITY)" 10.0.2.3 1.3.6.1.2.1.1.5.0`, e o mesmo para `10.0.2.4`.

**Se algo básico falhar, pare.** Algo básico é: loopback, gateway da Filial, OSPF ou Zabbix sem dados recentes. Entregue a tabela e o diagnóstico provável (cabo, IP, firewall `REDES_AUTORIZADAS`, rota) e espere o usuário. Não siga para a Fase C com a rede quebrada.

## Fase B: atualizar o SennaGuard

```bash
git -C /opt/sennaguard log --oneline -1                       # versão atual (anote)
grep -c '^TELEGRAM_TOKEN=' /etc/sennaguard/sennaguard.env      # 0 = o instalador vai perguntar o token
```

**Se a contagem der 0:** o `atualizar.sh` vai pedir o token do Telegram, então é o usuário quem roda, numa janela própria: `bash /opt/sennaguard/deploy/atualizar.sh`.

**Se der 1:** rode você mesmo:

```bash
bash /opt/sennaguard/deploy/atualizar.sh
```

Confira depois:

```bash
git -C /opt/sennaguard log --oneline -1                       # 7cdfb80 ou mais novo
systemctl is-active sennaguard; journalctl -u sennaguard -n 60 --no-pager | grep -iE 'traceback|error' || echo "sem erros"
B=http://127.0.0.1:8010
curl -s $B/api/publico                                         # "simulacao": false
# Rotas novas: 401 (sem login) = existe; 404 = versão antiga
for r in "PUT /api/eu/painel" "PUT /api/eu/notificacoes" "POST /api/anexos" "PUT /api/eu/foto"; do
  set -- $r; printf '%-26s %s\n' "$r" "$(curl -s -o /dev/null -w '%{http_code}' -X $1 $B$2)"; done
curl -s -o /dev/null -w 'serie com período: %{http_code}\n' "$B/api/serie/latencia?de=$(( $(date +%s)-3600 ))&ate=$(date +%s)"   # 401
runuser -u sennaguard -- sh -c 'mkdir -p /var/lib/sennaguard/arquivos && test -w /var/lib/sennaguard/arquivos' && echo "arquivos: ok"
curl -sk -o /dev/null -w 'HTTPS pelo Apache: %{http_code}\n' https://localhost/sennaguard/       # 200
```

## Fase C: refazer as etapas de rede do roteiro

Faça **todas**, mesmo que parte pareça feita, e confira o estado real antes de mudar qualquer coisa:

| Etapa do roteiro | O que fazer agora |
| --- | --- |
| **3.1** | testar a leitura nos dois roteadores |
| **3.2** | montar o bloco do R-MATRIZ (`zabbix-ia`, `sennaguard-teste`, `REDES_AUTORIZADAS`) para o usuário colar. Se o usuário não tiver o bloco do `sennaguard-teste`, monte-o a partir de `/etc/sennaguard/mikrotik_teste_key.pub` |
| **3.3** | testar os 3 acessos SSH. O teste só **lista** a `sfp1-WAN-FIBRA`, sem desligar nada |
| **4** | template e trigger de sinal das antenas no Zabbix pela API. Antes de criar, veja se já existem, para não duplicar |
| **5** | validação completa com dados reais (o script Python do roteiro), comparando com o Zabbix |
| **6** | `/var/lib/sennaguard` no `backup_noc.sh`. Se já estiver lá, só confirme, sem duplicar a linha |

Na Etapa 5, confira também o que veio nesta versão:

```bash
cd /opt/sennaguard/backend
runuser -u sennaguard -- env $(grep -v '^#' /etc/sennaguard/sennaguard.env | xargs) /opt/sennaguard/.venv/bin/python - <<'PY'
import time, fonte
for h in (1, 24, 168, 720):
    s = fonte.serie("latencia", h); print(f"latência {h}h:", len(s), "pontos")
agora = int(time.time()); s = fonte.serie("latencia", 2, agora - 86400)
print("janela de ontem (2 h):", len(s), "pontos, de", s[0]["t"] if s else None, "a", s[-1]["t"] if s else None)
PY
```

A janela de ontem tem que trazer pontos entre `agora-93600` e `agora-86400`. Lista vazia na janela de 720 h com dados existentes é divergência: registre no relatório.

## Fase D: teste de ponta a ponta (com o usuário)

Peça ao usuário cada item e marque **ok** ou **falhou**, com o que ele viu:

1. **Acesso pela Filial.** Num PC da LAN da Filial (`192.168.20.x`), abrir `https://192.168.10.50/sennaguard/` e entrar como **Cliente**. O tour aparece no primeiro login.
2. **Visão.** Gráfico de latência com dados reais; os períodos de 1 h a 30 dias funcionam; arrastar no gráfico dá zoom.
3. **Chamado com anexo.** O cliente abre um chamado e cola um print (Ctrl+V). A equipe, noutro PC ou celular, responde e escreve uma nota interna. O cliente **não** vê a nota, e aparece "Visto às".
4. **Perfil.** Enviar uma foto, conectar o Telegram e ajustar os avisos.
5. **Telegram.** Com o Telegram de alguém conectado, mande um teste. Não mostre o token.
   ```bash
   cd /opt/sennaguard/backend && runuser -u sennaguard -- env $(grep -v '^#' /etc/sennaguard/sennaguard.env | xargs) \
     /opt/sennaguard/.venv/bin/python -c "import telegram,time; telegram.para_usuarios([ID], '✅ Teste do SennaGuard'); time.sleep(5)"
   ```
6. **Celular.** Abrir o painel no celular, numa rede da Matriz ou da Filial: barra inferior, cartões e chat.
7. **Backup.** Em **Backups → Fazer backup agora**, aparecem versões do R-MATRIZ e do R-FILIAL.
8. **Opcional, e só pelo usuário, acompanhado:** o primeiro teste de failover pelo painel (**Testes → Pedir → Aprovar**). Você só observa os logs.

## Fase E: relatório

Entregue ao usuário, nesta ordem:

1. **Tabela geral:** item | resultado (ok / falhou / pendente do usuário) | evidência curta. Cubra as fases A a D.
2. **Versão instalada:** `git log --oneline -1`.
3. **Divergências do código com o ambiente real:** comando, saída exata e o arquivo do backend que parece responsável. O usuário vai colar isso para o desenvolvedor corrigir no GitHub.
4. **O que ficou para o usuário fazer**, em passos curtos.
