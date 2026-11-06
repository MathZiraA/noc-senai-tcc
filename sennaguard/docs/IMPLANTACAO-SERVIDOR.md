# SennaGuard: roteiro de implantação para a sessão do Claude no servidor do NOC

22/10/2026 · Matheus · [versão editável](https://claude.ai/artifact/RSFyKTiRhaMG7yZ7bMyexj)

## Contexto e objetivo

Você é uma sessão do Claude com terminal no servidor do NOC (Debian 12, como root). Sua tarefa é deixar o **SennaGuard** funcionando com dados reais: verificar o servidor, conferir a instalação feita pelo usuário, ligar o sinal das antenas no Zabbix pela API, preparar os acessos SSH aos roteadores e validar tudo. Tokens, senhas e comandos que mudam os roteadores ficam com o usuário (Matheus): você prepara e pede, ele executa.

O SennaGuard é um painel web do NOC do TCC (repositório público `MathZiraA/sennaguard`: o clone não pede login nem token). Ele lê o Zabbix 7.0 que já roda neste servidor e foi montado pelo projeto `MathZiraA/noc-senai-tcc`.

| Item | Valor |
| --- | --- |
| Servidor | `192.168.10.50` (LAN da Matriz), Debian 12, Zabbix 7.0, Apache com HTTPS e CA própria do NOC |
| Endereço público do painel | `https://192.168.10.50/sennaguard/` (Apache → `127.0.0.1:8010`) |
| Código | `/opt/sennaguard` (backend em `backend/`, interface compilada em `frontend/dist`) |
| Serviço | `sennaguard.service`, usuário de sistema `sennaguard`, logs em `journalctl -u sennaguard` |
| Configuração | `/etc/sennaguard/sennaguard.env` (640, root:sennaguard) |
| Segredos | `/etc/sennaguard/{gemini_key,anthropic_key,mikrotik_key,mikrotik_teste_key}` (600, dono sennaguard) |
| Dados | `/var/lib/sennaguard/` (banco SQLite e `backups/` das configurações dos roteadores) |
| Configuração do NOC | `/etc/noc/noc.conf`; token do Zabbix em `/root/.zabbix_token`; scripts do NOC em `/root/noc` |
| Livro de chamados do Analista IA | `/var/lib/noc-analista/chamados.jsonl` |
| Roteadores | R-MATRIZ loopback `10.255.255.1`, R-FILIAL loopback `10.255.255.2` (MikroTik hEX S, RouterOS 7) |
| Antenas | hosts `RADIO-P2P-MATRIZ` (`10.0.2.3`) e `RADIO-P2P-FILIAL` (`10.0.2.4`), Ubiquiti PowerBeam M5, SNMP já habilitado |
| LAN da Filial | `192.168.20.0/24`, gateway `192.168.20.1` |

O código está pronto e testado em simulação: login por perfil, chamados com SLA, Telegram, relatório PDF, manutenção, backups, chat com IA, teste de failover e base de conhecimento. O instalador (`deploy/instalar.sh`) troca a simulação pelos dados reais sozinho. O que nunca rodou é o modo real contra este Zabbix e estes roteadores: é isso que você vai validar.

### Se a sessão roda no notebook da Matriz (acesso remoto por SSH)

Quando o Claude roda num notebook da LAN da Matriz, e não no próprio servidor, todo o roteiro vale igual, com estas adaptações:

- **Todo comando deste roteiro roda no servidor**, via `ssh root@192.168.10.50`. Nada é instalado nem gravado no notebook.
- O acesso precisa ser por **chave, sem senha** (`ssh -o BatchMode=yes root@192.168.10.50 true` tem que funcionar). Se pedir senha, pare e peça ao usuário para configurar a chave.
- Blocos de várias linhas: mande pela entrada padrão, sem colocar o script dentro de aspas:
  - shell: `ssh root@192.168.10.50 'bash -s' <<'EOF' … EOF`
  - Python: `ssh root@192.168.10.50 'python3 -' <<'PY' … PY`
  - Python com o ambiente do serviço (Etapa 5): `ssh root@192.168.10.50 "cd /opt/sennaguard/backend && runuser -u sennaguard -- env \$(grep -v '^#' /etc/sennaguard/sennaguard.env | xargs) /opt/sennaguard/.venv/bin/python -" <<'PY' … PY`
- Para gravar um script no servidor (ex.: `/root/sennaguard_antenas.py`): `ssh root@192.168.10.50 'cat > /root/sennaguard_antenas.py' <<'PY' … PY`.
- **Nenhum segredo vem para o notebook:** não copie tokens, chaves nem o `.env` para a máquina local, nem por `scp`.
- Para ler este roteiro antes do clone, baixe direto do GitHub (público): `curl -s https://raw.githubusercontent.com/MathZiraA/sennaguard/main/docs/IMPLANTACAO-SERVIDOR.md`. Depois do clone ele também fica em `/opt/sennaguard/docs/`.
- O `git clone` a sessão mesma faz (o repositório é público). O passo interativo (`instalar.sh`) o usuário faz numa janela SSH separada. O WinBox e o navegador do painel ficam no próprio notebook.

## Regras de segurança

Este servidor monitora uma rede em produção. Na dúvida, pare e pergunte ao usuário.

- **Nunca altere os roteadores MikroTik.** Você só tem acesso de leitura (usuário `zabbix-ia`). Comandos que criam usuários ou mudam a configuração vão prontos para o usuário colar no WinBox. Use um acesso de administrador só se o usuário entregar um, explicitamente, nesta conversa.
- **Nunca derrube a fibra.** Não rode o teste de failover, não aprove testes no painel e nunca execute `/interface disable` em nenhum roteador. O primeiro teste é feito pelo usuário, acompanhado.
- **Nunca mostre nem copie segredos.** Não imprima o conteúdo de `/root/.zabbix_token`, `/root/.gemini_key`, `/root/.anthropic_key`, das chaves SSH privadas nem de `TELEGRAM_TOKEN`/`ZABBIX_TOKEN` do `.env`. Para conferir se existem, use `test -s arquivo`, `stat` ou `grep -c '^CHAVE=' arquivo`.
- **Não digite segredos no lugar do usuário.** O instalador pergunta o token do Telegram e a senha do administrador: quem responde é o usuário.
- **Não crie, apague nem edite usuários do SennaGuard**, e não redefina senhas. Contas são do usuário.
- **No Zabbix, só acrescente.** Pode vincular template e criar trigger nos hosts das antenas (Etapa 4). Não apague nem desative hosts, itens, triggers, ações ou mídias que já existem.
- **Mudanças em arquivos do sistema:** antes de editar `/root/noc/backup_noc.sh` ou qualquer arquivo de `/etc`, faça uma cópia `.bak-AAAAMMDD` e mostre o diff ao usuário depois.
- **Não faça `git push`** em nenhum repositório. Alterações no servidor ficam no servidor; o usuário decide o que vai para o GitHub.
- **Não reinicie** o Zabbix, o MySQL nem o `noc-analista`. Pode reiniciar o `sennaguard` e recarregar o Apache (`systemctl reload apache2`), sempre depois de `apache2ctl configtest`.

## Divisão de tarefas

Siga as etapas nesta ordem. Quando uma linha for do usuário, pare, diga exatamente o que ele precisa fazer e espere a confirmação antes de seguir.

| # | Etapa | Quem faz | O que entrega |
| --- | --- | --- | --- |
| 1 | Verificar o servidor antes da instalação | **Sessão** | lista de pendências (ou "tudo certo") |
| 2a | Criar o bot do Telegram | Usuário | token do bot |
| 2b | `git clone` do repositório público em `/opt/sennaguard` | **Sessão** | código no servidor |
| 2c | `bash deploy/instalar.sh` (responde token do Telegram e senha do admin) | Usuário | painel no ar e bloco RouterOS impresso no fim |
| 2d | Conferir serviço, Apache, `.env` e permissões | **Sessão** | instalação conferida |
| 3a | Preparar os comandos RouterOS (`zabbix-ia` no R-MATRIZ, `sennaguard-teste`, lista de redes autorizadas) | **Sessão** | bloco pronto para colar |
| 3b | Colar os comandos no WinBox do R-MATRIZ | Usuário | usuários criados |
| 3c | Testar o SSH de leitura e o de teste (sem desligar nada) | **Sessão** | 3 conexões OK |
| 4 | Template e trigger de sinal das antenas no Zabbix, pela API | **Sessão** | sinal em dBm sendo coletado |
| 5 | Validar os dados reais e o backup das configurações | **Sessão** | checklist preenchido |
| 6 | Incluir `/var/lib/sennaguard` no backup diário do NOC | **Sessão** | `backup_noc.sh` atualizado (com cópia) |
| 7 | Conectar o Telegram, cadastrar pessoas, certificado nos PCs, TV, primeiro teste de failover | Usuário | uso no dia a dia |
| 8 | Relatório final | **Sessão** | resumo no formato da última seção |

## Etapa 1: verificações antes da instalação

Somente leitura. Rode cada bloco e anote o que falhar; no fim, entregue ao usuário a lista do que precisa ser resolvido antes da Etapa 2.

```bash
# Sistema e serviços do NOC
cat /etc/debian_version; id -u                    # Debian 12; precisa ser 0 (root)
systemctl is-active zabbix-server apache2 noc-analista mariadb 2>/dev/null || systemctl is-active zabbix-server apache2 noc-analista mysql
curl -s -o /dev/null -w '%{http_code}\n' http://localhost/zabbix/   # 200

# Arquivos que o instalador usa (só confere se existem, sem mostrar o conteúdo)
for f in /root/.zabbix_token /root/.gemini_key /root/.anthropic_key /root/.ssh/id_ed25519_mikrotik /etc/noc/noc.conf /etc/ssl/noc/noc.key; do
  test -s "$f" && echo "ok  $f" || echo "FALTA $f"; done
grep -E '^(SERVIDOR_IP|HOST_FILIAL|FIBRA_FILIAL|RADIO_FILIAL|LAN_FILIAL|LOOPBACK_MATRIZ|LOOPBACK_FILIAL|SNMP_COMMUNITY|RADIO_SINAL_MIN_DBM)=' /etc/noc/noc.conf | sed 's/^SNMP_COMMUNITY=.*/SNMP_COMMUNITY=(definida)/'

# Porta do SennaGuard livre e internet para baixar pacotes (Node.js 20, pip, npm)
ss -ltnp | grep -c ':8010 ' || true          # 0 = livre
curl -sI https://deb.nodesource.com | head -1; curl -sI https://pypi.org | head -1

# Repositório público acessível (deve imprimir um hash e refs/heads/main) e destino livre
git ls-remote https://github.com/MathZiraA/sennaguard.git main
test -e /opt/sennaguard && echo "JÁ EXISTE /opt/sennaguard" || echo "ok  /opt/sennaguard livre"
```

Teste o token do Zabbix sem exibi-lo:

```bash
curl -s -X POST http://localhost/zabbix/api_jsonrpc.php -H 'Content-Type: application/json-rpc' \
  -H "Authorization: Bearer $(cat /root/.zabbix_token)" \
  -d '{"jsonrpc":"2.0","method":"host.get","params":{"output":["host"]},"id":1}' | python3 -m json.tool | grep '"host"'
```

O resultado deve listar pelo menos `R-FILIAL`, `RADIO-P2P-MATRIZ` e `RADIO-P2P-FILIAL`. Anote se existe também um host `R-MATRIZ`.

Como interpretar:

- `/root/.anthropic_key` faltando é normal: o Claude é opcional e o chat usa o Gemini.
- `/root/.ssh/id_ed25519_mikrotik` faltando: o backup das configurações não vai funcionar. Avise o usuário; essa chave é a do Analista IA.
- Qualquer outro `FALTA`, serviço inativo ou token do Zabbix sem resposta: **pare** e explique ao usuário antes de seguir.
- `git ls-remote` falhando: sem internet ou o repositório voltou a ser privado. Pare e avise o usuário.
- `/opt/sennaguard` já existe: é uma instalação anterior. Não apague; pergunte ao usuário se é para atualizar (`bash /opt/sennaguard/deploy/atualizar.sh`) em vez de instalar.
- Porta 8010 ocupada: descubra o processo com `ss -ltnp | grep 8010` e pergunte ao usuário o que fazer.

Terminando sem bloqueios, diga ao usuário: "Pode instalar", com o passo a passo da Etapa 2.

## Etapa 2: instalação (usuário) e conferência (sessão)

**Passe ao usuário, exatamente assim:**

**Você (sessão) clona o código.** O repositório é público, então não há login nem token:

```bash
git clone https://github.com/MathZiraA/sennaguard.git /opt/sennaguard
git -C /opt/sennaguard log --oneline -1          # anote o commit no relatório
```

**Depois passe ao usuário, exatamente assim:**

1. No Telegram: `@BotFather` → `/newbot` → nome `SennaGuard NOC` → guarde o token do bot.
2. No terminal do servidor, como root:

```bash
bash /opt/sennaguard/deploy/instalar.sh
```

O instalador pergunta o token do bot (Enter vazio desliga o Telegram) e o e-mail, o nome e a senha do primeiro administrador. No fim, ele imprime `SennaGuard no ar: https://…/sennaguard/` e um bloco de 4 linhas RouterOS para o usuário `sennaguard-teste`. **Peça ao usuário para colar esse bloco aqui na conversa**: você vai usá-lo na Etapa 3. Ele só aparece na primeira instalação.

**Depois que o usuário confirmar, confira:**

```bash
systemctl is-active sennaguard; systemctl is-enabled sennaguard
journalctl -u sennaguard -n 40 --no-pager                      # sem Traceback
curl -s http://127.0.0.1:8010/api/publico                       # {"simulacao":false,"senha_demo":null}
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/sennaguard/   # 200
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/sennaguard/api/eventos  # 401 (precisa de login: o roteamento está certo)
apache2ctl -M 2>/dev/null | grep -E 'proxy_module|proxy_http|headers'; a2query -c sennaguard

# Configuração: nomes das variáveis, sem os valores
cut -d= -f1 /etc/sennaguard/sennaguard.env
stat -c '%a %U:%G %n' /etc/sennaguard /etc/sennaguard/* /var/lib/sennaguard
ls -ld /var/lib/noc-analista; ls -l /var/lib/noc-analista/chamados.jsonl 2>/dev/null
```

O que esperar:

- No `.env`: `ZABBIX_URL`, `ZABBIX_TOKEN`, `NOC_HOST`, `NOC_FIBRA_FILIAL`, `NOC_RADIO_FILIAL`, `NOC_LIVRO`, `SENNAGUARD_BANCO`, `COOKIE_SEGURO`, `NOC_LAN_FILIAL`, `NOC_LOOPBACK_MATRIZ`, `NOC_LOOPBACK_FILIAL` e, se o usuário informou, `TELEGRAM_TOKEN`.
- `.env` com `640 root:sennaguard`. Chaves em `/etc/sennaguard` com `600 sennaguard:sennaguard`; `mikrotik_teste_key.pub` pode ser `644`.
- `/var/lib/noc-analista` no grupo `sennaguard` com setgid (`drwxr-s---` ou parecido). Se `chamados.jsonl` existir, `640` e grupo `sennaguard`.
- Se `simulacao` vier `true`: o `ZABBIX_URL` ou o `ZABBIX_TOKEN` não entrou no `.env`. Mostre ao usuário quais nomes faltam; não grave o token você mesmo.
- Se o `.env` não tiver `NOC_LAN_FILIAL` ou os loopbacks, é porque essas chaves não estão no `noc.conf`. Acrescente com os valores conhecidos (`NOC_LAN_FILIAL=192.168.20.1`, `NOC_LOOPBACK_MATRIZ=10.255.255.1`, `NOC_LOOPBACK_FILIAL=10.255.255.2`) e rode `systemctl restart sennaguard`. Valores de rede não são segredo.

## Etapa 3: acesso SSH aos roteadores

O SennaGuard usa dois acessos. Você testa os dois, mas quem cria os usuários nos roteadores é o usuário, colando os comandos que você preparar. Use sempre `runuser -u sennaguard --`, para testar exatamente como o serviço roda.

| Acesso | Usuário no RouterOS | Chave no servidor | Para quê | Onde |
| --- | --- | --- | --- | --- |
| Leitura | `zabbix-ia` (grupo `read`) | `/etc/sennaguard/mikrotik_key` (cópia da chave do Analista IA) | backup diário (`/export terse`) | R-MATRIZ e R-FILIAL |
| Teste | `sennaguard-teste` (grupo próprio, com escrita) | `/etc/sennaguard/mikrotik_teste_key` (gerada pelo instalador) | desligar e religar a sfp1 no teste de failover | só R-MATRIZ |

### 3.1 Testar o que já existe

```bash
K=/etc/sennaguard/mikrotik_key
O='-o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new'
runuser -u sennaguard -- ssh -i $K $O zabbix-ia@10.255.255.2 '/system identity print'   # R-FILIAL: deve funcionar (Analista IA)
runuser -u sennaguard -- ssh -i $K $O zabbix-ia@10.255.255.1 '/system identity print'   # R-MATRIZ: provavelmente falha
```

Se o R-FILIAL falhar, pare: o Analista IA usa o mesmo acesso. Mostre o erro ao usuário.

### 3.2 Preparar o bloco para o usuário colar no R-MATRIZ

A chave **pública** pode ser exibida. Monte o bloco assim:

```bash
PUB=$(cat /root/.ssh/id_ed25519_mikrotik.pub)
IP=$(grep -E '^SERVIDOR_IP=' /etc/noc/noc.conf | cut -d= -f2 | tr -d "\"' "); IP=${IP:-192.168.10.50}
cat <<EOF
# --- R-MATRIZ: usuário de leitura para o backup do SennaGuard ---
/file add name=zabbix-ia.pub contents="$PUB"
/user add name=zabbix-ia group=read address=$IP/32 password=$(openssl rand -hex 16)
/user ssh-keys import public-key-file=zabbix-ia.pub user=zabbix-ia
# --- confira se o servidor pode fazer SSH (o firewall só libera REDES_AUTORIZADAS) ---
/ip firewall address-list print where list=REDES_AUTORIZADAS
# se $IP (ou 192.168.10.0/24) não aparecer, rode também:
/ip firewall address-list add list=REDES_AUTORIZADAS address=$IP comment="servidor NOC"
EOF
```

Entregue ao usuário:

1. esse bloco, só as linhas do R-MATRIZ;
2. o bloco de 4 linhas do `sennaguard-teste` que o instalador imprimiu na Etapa 2.

Se o usuário não tiver o bloco do `sennaguard-teste`, monte-o a partir de `/etc/sennaguard/mikrotik_teste_key.pub`, com as mesmas linhas que o fim de `deploy/instalar.sh` imprime: grupo com `policy=ssh,read,write,test,policy,!winbox,!web,!api,!ftp`, usuário com `address=$IP/32` e importação da chave. Diga para colar tudo em **WinBox → R-MATRIZ → New Terminal** e avisar quando terminar. Se `zabbix-ia` já existir no R-MATRIZ, o `/user add` dá erro: tudo bem, então basta o `/user ssh-keys import`.

### 3.3 Testar depois que o usuário colar

```bash
runuser -u sennaguard -- ssh -i /etc/sennaguard/mikrotik_key $O zabbix-ia@10.255.255.1 '/system identity print'
runuser -u sennaguard -- ssh -i /etc/sennaguard/mikrotik_teste_key $O sennaguard-teste@10.255.255.1 '/interface print where name=sfp1-WAN-FIBRA'
```

O segundo comando só **lista** a interface, sem desligar nada. A resposta precisa mostrar `sfp1-WAN-FIBRA`, sem a flag `X` (desabilitada). Se mostrar `X`, avise o usuário na hora: a fibra está desligada.

Com `Permission denied`, a chave não foi importada ou o `address=` do usuário não é o IP do servidor. Com `Connection timed out`, falta liberar o servidor em `REDES_AUTORIZADAS`.

## Etapa 4: Zabbix via API, sinal das antenas

O SennaGuard procura nas antenas um item cujo nome contenha "signal" (sem "noise") e mostra o valor em dBm. Para esse item existir, as duas antenas precisam de interface SNMP e do template **Ubiquiti AirOS by SNMP**. O Zabbix também precisa de uma trigger para o sinal abaixo do mínimo do `noc.conf` (`RADIO_SINAL_MIN_DBM`, padrão −60).

Salve o script abaixo em `/root/sennaguard_antenas.py` e rode com `python3 /root/sennaguard_antenas.py`. Ele só acrescenta: não apaga nem altera nada que já exista, e pode ser rodado de novo sem duplicar.

```python
"""Liga o sinal das antenas no Zabbix para o SennaGuard (idempotente, só acrescenta)."""
import json, time, urllib.request
from pathlib import Path

URL = "http://localhost/zabbix/api_jsonrpc.php"
TOKEN = Path("/root/.zabbix_token").read_text().strip()
CONF = {l.split("=", 1)[0].strip(): l.split("=", 1)[1].strip().strip('"\'')
        for l in Path("/etc/noc/noc.conf").read_text().splitlines() if "=" in l and not l.lstrip().startswith("#")}
ANTENAS = {"RADIO-P2P-MATRIZ": CONF.get("ANTENA_MATRIZ", "10.0.2.3"), "RADIO-P2P-FILIAL": CONF.get("ANTENA_FILIAL", "10.0.2.4")}
MINIMO = CONF.get("RADIO_SINAL_MIN_DBM", "-60")

def call(m, p):
    req = urllib.request.Request(URL, json.dumps({"jsonrpc": "2.0", "method": m, "params": p, "id": 1}).encode(),
                                 {"Content-Type": "application/json-rpc", "Authorization": f"Bearer {TOKEN}"})
    r = json.loads(urllib.request.urlopen(req, timeout=20).read())
    if "error" in r: raise SystemExit(f"{m}: {r['error']}")
    return r["result"]

tpl = call("template.get", {"filter": {"name": ["Ubiquiti AirOS by SNMP"]}, "output": ["templateid"]})
if not tpl:
    raise SystemExit("Template 'Ubiquiti AirOS by SNMP' não encontrado. Liste com template.get search name=Ubiquiti e avise o usuário.")
tid = tpl[0]["templateid"]

for host, ip in ANTENAS.items():
    h = call("host.get", {"filter": {"host": [host]}, "output": ["hostid"], "selectInterfaces": ["type", "ip"],
                          "selectParentTemplates": ["templateid"], "selectMacros": ["macro"]})
    if not h:
        print(f"{host}: host não existe no Zabbix, pulando"); continue
    h = h[0]
    if not any(i["type"] == "2" for i in h["interfaces"]):
        if not any(m["macro"] == "{$SNMP_COMMUNITY}" for m in h["macros"]) and CONF.get("SNMP_COMMUNITY"):
            call("usermacro.create", {"hostid": h["hostid"], "macro": "{$SNMP_COMMUNITY}", "value": CONF["SNMP_COMMUNITY"], "type": 1})
        call("hostinterface.create", {"hostid": h["hostid"], "type": 2, "main": 1, "useip": 1, "ip": ip, "dns": "", "port": "161",
                                      "details": {"version": 2, "community": "{$SNMP_COMMUNITY}", "bulk": 1}})
        print(f"{host}: interface SNMP criada ({ip})")
    if tid not in [t["templateid"] for t in h["parentTemplates"]]:
        call("host.massadd", {"hosts": [{"hostid": h["hostid"]}], "templates": [{"templateid": tid}]})
        print(f"{host}: template vinculado")
    else:
        print(f"{host}: template já estava vinculado")
```

Depois de rodar, **espere 5 minutos** para a primeira coleta e liste os itens de sinal (os valores não são segredo):

```bash
python3 - <<'PY'
import json, urllib.request
from pathlib import Path
T = Path("/root/.zabbix_token").read_text().strip()
def call(m, p):
    r = urllib.request.Request("http://localhost/zabbix/api_jsonrpc.php", json.dumps({"jsonrpc":"2.0","method":m,"params":p,"id":1}).encode(),
        {"Content-Type":"application/json-rpc","Authorization":f"Bearer {T}"})
    return json.loads(urllib.request.urlopen(r).read())["result"]
for host in ("RADIO-P2P-MATRIZ", "RADIO-P2P-FILIAL"):
    h = call("host.get", {"filter": {"host": [host]}, "output": ["hostid"]})[0]["hostid"]
    for i in call("item.get", {"hostids": h, "search": {"name": "signal"}, "output": ["name", "key_", "lastvalue", "units", "error"]}):
        print(host, "|", i["name"], "|", i["key_"], "|", i["lastvalue"], i["units"], "|", i["error"][:60])
PY
```

Confira:

- Deve existir um item de **intensidade do sinal** com valor entre −50 e −65 dBm. Na bancada, a medição foi −53/−52.
- Se o primeiro item com "signal" no nome não for o de intensidade, o SennaGuard vai ler o item errado. Nesse caso, avise o usuário com os nomes listados; a correção fica na função `_item_sinal` do `backend/fonte.py`.
- Item com `error` de timeout ou valor vazio: a community SNMP da antena não bate com a do `noc.conf`. Peça ao usuário para conferir no airOS (Services → SNMP Agent). Não mostre a community.

**Trigger de sinal fraco** (uma por antena, só se ainda não existir uma com o mesmo nome). Use a chave (`key_`) do item de intensidade listado acima:

```python
# Dentro do mesmo estilo de script (função call acima), para cada antena:
nome = "Sinal do rádio abaixo de -60 dBm ({HOST.NAME})"
if not call("trigger.get", {"hostids": hostid, "filter": {"description": [nome]}, "output": ["triggerid"]}):
    call("trigger.create", {"description": nome, "priority": 3,   # 3 = Média
         "expression": f"last(/{host}/{chave_do_item})<-60",
         "manual_close": 0, "tags": [{"tag": "component", "value": "enlace"}, {"tag": "enlace", "value": "radio"}]})
```

Substitua `-60` pelo valor de `RADIO_SINAL_MIN_DBM` se o `noc.conf` tiver outro. Por fim, rode `systemctl restart sennaguard` e confira que `fonte.serie("sinal", 1)` (Etapa 5) traz valores.

## Etapa 5: validação com dados reais

O código do modo real foi escrito a partir do `noc-senai-tcc` e testado com respostas simuladas, mas nunca contra este Zabbix. Aqui você chama as mesmas funções do backend, com a mesma configuração do serviço, e compara com o Zabbix. Tudo é leitura, exceto o backup, que só grava em `/var/lib/sennaguard/backups`.

**Não edite o código em `/opt/sennaguard`.** As atualizações vêm do GitHub com `git pull --ff-only`, que falha se houver mudanças locais. Divergências vão para o relatório, com a saída exata; a correção é feita no repositório.

```bash
cd /opt/sennaguard/backend
runuser -u sennaguard -- env $(grep -v '^#' /etc/sennaguard/sennaguard.env | xargs) /opt/sennaguard/.venv/bin/python - <<'PY'
import json, fonte, livro, backup, ia, telegram
print("1 simulação:", fonte.SIMULACAO)
v = fonte.visao()
print("2 caminho:", v["caminho"], "| fibra:", v["enlaces"]["fibra"], "| rádio:", v["enlaces"]["radio"], "| failover:", v["ultimo_failover"])
al = fonte.alertas(24)
print("3 alertas 24h:", len(al), [(a["severidade"], a["nome"][:50], a["ativo"], bool(a["analise"])) for a in al[:6]])
print("4 equipamentos:", [(e["nome"], e["local"], e["up"]) for e in fonte.equipamentos()])
for m in ("latencia", "trafego", "sinal"):
    s = fonte.serie(m, 1); print("5", m, "pontos:", len(s), "último:", s[-1] if s else None)
d = fonte.detalhe_equipamento(fonte.HOST)
print("6 R-FILIAL interfaces:", [(i["nome"], i["up"], i["rx"]) for i in d["interfaces"]][:8], "recursos:", d["recursos"])
print("7 livro de chamados:", livro.verificar(), "chamados NOC:", len(livro.chamados()))
for h in backup.ROTEADORES:
    try: print("8 backup", h, backup.fazer_backup(h))
    except Exception as e: print("8 backup", h, "ERRO:", e)
print("9 IA:", ia.provedor(), "| Telegram ativo:", telegram.ativo())
PY
ls -l /var/lib/sennaguard/backups/*/
```

Compare com o Zabbix (pela interface ou pela API, como na Etapa 1):

| # | Esperado | Onde conferir no Zabbix | Se divergir |
| --- | --- | --- | --- |
| 1 | `False` | — | o `.env` não tem `ZABBIX_URL`/`ZABBIX_TOKEN`: volte à Etapa 2 |
| 2 | caminho igual ao item "Caminho ativo Matriz-Filial" (`noc.caminho_ativo`: 3 ou 2 = fibra, 1 = rádio); latência da fibra em ms (≈ 0,6) | Latest data do R-FILIAL, tag `component=enlace` | anote o valor bruto do item e o que o SennaGuard mostrou |
| 3 | mesma quantidade e nomes de Monitoring → Problems (24 h, host R-FILIAL); `analise` = True nos que têm comentário do `noc-analista` | Problems → histórico do evento | anote o nome do usuário que comenta as análises (o código espera `noc-analista`) |
| 4 | todos os hosts do Zabbix, com Matriz/Filial pelo nome | Data collection → Hosts | anote os hosts que caíram no local errado |
| 5 | `latencia` com pontos; `trafego` com pontos se o SNMP do R-FILIAL tem itens "Bits received" de `sfp1` e `ether1`; `sinal` com pontos depois da Etapa 4 | Latest data | anote os nomes reais dos itens de tráfego da sfp1 e da ether1 |
| 6 | interfaces do R-FILIAL com status e Mbps; CPU, memória e uptime | Latest data do R-FILIAL (template Mikrotik by SNMP) | anote os nomes reais dos itens de CPU, memória e uptime |
| 7 | `ok: True` (ou 0 registros, se ainda não houve chamado NOC) | `/var/lib/noc-analista/chamados.jsonl` | permissão negada → rode o instalador de novo |
| 8 | `(True, n, 0)` para os dois roteadores e arquivos `.rsc` criados | — | o erro do SSH vai para o relatório; volte à Etapa 3 |
| 9 | `gemini` (ou `claude`) e `True` se o usuário informou o token | — | sem IA: confira `/etc/sennaguard/gemini_key` com `test -s` |

Teste também o bot do Telegram, sem mostrar o token. Deve imprimir o @ do bot:

```bash
cd /opt/sennaguard/backend && runuser -u sennaguard -- env $(grep -v '^#' /etc/sennaguard/sennaguard.env | xargs) /opt/sennaguard/.venv/bin/python -c "import telegram; print(telegram._api('getMe')['username'] if telegram.ativo() else 'sem token')"
```

Por fim, peça ao usuário para abrir `https://192.168.10.50/sennaguard/` e confirmar três coisas: o cabeçalho não diz "dados simulados", o login não mostra "Modo demonstração" e o chat "Pergunte ao NOC" responde "como está a rede?".

## Etapa 6: incluir o SennaGuard no backup do NOC

O NOC já tem um backup diário: `/root/noc/backup_noc.sh`, chamado pelo cron `/etc/cron.d/noc-backup` às 02:30. Ele guarda 7 dias em `/var/backups/noc` (pasta só do root) e avisa o Zabbix pelo item `noc.backup.mb`. O SennaGuard tem dados que só existem nele (usuários, chamados SG com o histórico encadeado, artigos, testes de failover e as versões das configurações dos roteadores), e nada disso entra hoje.

1. Faça a cópia: `cp -p /root/noc/backup_noc.sh /root/noc/backup_noc.sh.bak-$(date +%Y%m%d)`.
2. Logo antes da linha `# Configurações e dados pequenos`, acrescente a cópia consistente do banco SQLite (copiar o arquivo com `tar` enquanto o serviço grava pode gerar um arquivo corrompido):

```bash
# SennaGuard: cópia consistente do SQLite (usuários, chamados SG, artigos, testes), sem parar o serviço
if [ -f /var/lib/sennaguard/sennaguard.db ]; then
    python3 -c "import sqlite3,sys; o=sqlite3.connect('/var/lib/sennaguard/sennaguard.db'); d=sqlite3.connect(sys.argv[1]); o.backup(d); d.close()" \
        "$DESTINO/sennaguard-banco-$DATA.db" && gzip "$DESTINO/sennaguard-banco-$DATA.db"
fi
```

3. Na lista do `tar czf "$DESTINO/noc-config-$DATA.tar.gz"`, acrescente numa linha nova, antes de `/root/.zabbix_token`:

```bash
    /etc/sennaguard /var/lib/sennaguard/backups /etc/systemd/system/sennaguard.service /etc/apache2/conf-available/sennaguard.conf \
```

`/etc/sennaguard` tem segredos (token do Telegram, chaves). Isso é aceitável aqui porque o script já usa `umask 077` e a pasta de destino é `700`, a mesma proteção das outras credenciais do NOC.

4. Valide sem esperar o cron:

```bash
bash -n /root/noc/backup_noc.sh && /root/noc/backup_noc.sh
ls -lh /var/backups/noc | tail -4
tar tzf "$(ls -t /var/backups/noc/noc-config-*.tar.gz | head -1)" | grep -c sennaguard    # maior que 0
zcat "$(ls -t /var/backups/noc/sennaguard-banco-*.db.gz | head -1)" > /tmp/sg-teste.db && \
  python3 -c "import sqlite3; c=sqlite3.connect('/tmp/sg-teste.db'); print(c.execute('pragma integrity_check').fetchone(), c.execute('select count(*) from usuarios').fetchone())"; rm -f /tmp/sg-teste.db
```

O esperado é `('ok',)` e a quantidade de usuários cadastrados.

5. Mostre ao usuário o `diff -u` entre a cópia `.bak` e o arquivo novo. Lembre que essa mudança vale só neste servidor: para valer também numa reinstalação, ela precisa entrar no repositório `noc-senai-tcc` (`noc/backup_noc.sh`), e quem decide e faz isso é o usuário.

**Restauração** (para o relatório; não execute): `systemctl stop sennaguard`, descompactar o `sennaguard-banco-*.db.gz` sobre `/var/lib/sennaguard/sennaguard.db` (dono `sennaguard`), extrair `/etc/sennaguard` e `/var/lib/sennaguard/backups` do `tar`, e `systemctl start sennaguard`.

## Relatório final e solução de problemas

### Relatório ao usuário

Ao terminar, entregue ao usuário um relatório neste formato, sem nenhum segredo. Ele será repassado à sessão do Claude que mantém o código, então divergências precisam da saída exata.

```text
SENNAGUARD — IMPLANTAÇÃO <data>
Etapa 1 servidor ............ ok | pendências: …
Etapa 2 instalação .......... ok | simulacao=false | Telegram: sim/não | IA: gemini/claude/nenhuma
Etapa 3 SSH ................. leitura R-FILIAL ok/erro | leitura R-MATRIZ ok/erro | teste R-MATRIZ ok/erro
Etapa 4 Zabbix .............. template nas 2 antenas ok/erro | item de sinal: <nome> = <valor> dBm | triggers criadas: n
Etapa 5 validação ........... itens 1–9: ok/divergência (detalhe abaixo)
Etapa 6 backup do NOC ....... ok | integrity_check ok | diff mostrado ao usuário

DIVERGÊNCIAS PARA CORRIGIR NO CÓDIGO (item, esperado, obtido, saída exata):
…

AINDA COM O USUÁRIO:
[ ] Conectar o próprio Telegram (nome → Conectar Telegram)
[ ] Cadastrar o cliente da Filial e a equipe (Usuários → Novo usuário) e pedir que conectem o Telegram
[ ] Instalar a CA do NOC nos PCs da Filial e na TV (http://192.168.10.50/NOC-SENAI-CA.crt)
[ ] Gerar o link da TV (Usuários → Telas de TV) e abrir em tela cheia
[ ] Primeiro teste de failover acompanhado (Testes de failover → Pedir → Aprovar) e guardar o laudo em PDF
[ ] Levar a mudança do backup_noc.sh para o repositório noc-senai-tcc, se quiser
```

### Solução de problemas

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| `systemctl status sennaguard` falhou | dependência Python ou `.env` com linha inválida | `journalctl -u sennaguard -n 80 --no-pager`; o erro vai no relatório |
| Painel em 404 ou 503 | configuração do Apache ausente, ou serviço parado | `a2enconf sennaguard && apache2ctl configtest && systemctl reload apache2`; confira `curl -s 127.0.0.1:8010/api/publico` |
| Painel não atualiza sozinho | buffer do Apache no `/api/eventos` | confira se `/etc/apache2/conf-available/sennaguard.conf` tem o bloco `/sennaguard/api/eventos` com `flushpackets=on` depois do bloco geral |
| `simulacao: true` depois de instalar | faltou `ZABBIX_URL`/`ZABBIX_TOKEN` no `.env` | volte à Etapa 2; quem grava o token é o usuário |
| Tráfego vazio no painel | itens SNMP do R-FILIAL com outro nome | liste `item.get` com `search name="Bits"` no R-FILIAL e anote os nomes |
| Chamados NOC não aparecem | sem leitura em `/var/lib/noc-analista` | rode o instalador de novo; ele refaz grupo e setgid |
| Backup: `Permission denied (publickey)` | chave não importada ou `address=` errado | Etapa 3.2 |
| Backup: `Host key verification failed` | equipamento trocado ou reinstalado | apague a linha do IP em `/var/lib/sennaguard/backups/known_hosts` e teste de novo |
| Sinal sem valor | community SNMP diferente na antena | usuário confere no airOS; você não mostra a community |
| Chat responde "IA não configurada" | sem `/etc/sennaguard/gemini_key` | `test -s /root/.gemini_key` e rode o instalador de novo (ele copia) |

Se algo não estiver nesta tabela e exigir mudar código, roteador ou segredo, **pare e pergunte ao usuário**.
