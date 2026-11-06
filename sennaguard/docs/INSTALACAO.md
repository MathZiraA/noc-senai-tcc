# SennaGuard: instalação passo a passo (Linux e Windows)

Há três jeitos de rodar o SennaGuard:

| Onde | Para quê | Seção |
| --- | --- | --- |
| Servidor do NOC (Debian 12, junto do Zabbix) | uso real, com HTTPS pelo Apache e serviço que sobe sozinho | [Linux: servidor do NOC](#1-linux-servidor-do-noc-producao) |
| Qualquer Linux (Debian, Ubuntu, Mint...) | testar, apresentar ou desenvolver | [Linux: teste local](#2-linux-teste-local) |
| Windows 10/11 | testar, apresentar ou desenvolver | [Windows](#3-windows-1011) |

Sem `ZABBIX_URL`/`ZABBIX_TOKEN` o SennaGuard roda em **simulação**: valores da bancada real, o rádio fora e um chamado aberto. Os usuários de demonstração usam a senha `senai2026`:

- `matheus.ziravello@gmail.com` (administrador)
- `cliente@filial.local` (cliente)

## Requisitos

| Programa | Versão | Para quê |
| --- | --- | --- |
| Git | qualquer | baixar o repositório |
| Python | 3.11 ou mais novo | a API (FastAPI) |
| Node.js | 20 ou mais novo (o Tailwind 4 não roda no 18) | compilar a interface (React + Vite) |

---

## 1. Linux: servidor do NOC (produção)

O instalador faz tudo sozinho: pacotes, usuário do serviço, compilação, systemd e Apache. Pode rodar de novo a qualquer momento: cada etapa pula o que já está pronto.

### Antes de começar

O servidor precisa ter, montado pelo [noc-senai-tcc](https://github.com/MathZiraA/noc-senai-tcc):

- Debian 12 com Zabbix 7.0 e Apache servindo o Zabbix em HTTPS (CA do NOC);
- `/etc/noc/noc.conf` com os IPs da rede;
- `/root/.zabbix_token` com o token da API do Zabbix (se não existir, o instalador pergunta);
- opcional: `/root/.gemini_key` e `/root/.anthropic_key` (IA) e `/root/.ssh/id_ed25519_mikrotik` (backup dos roteadores).

### Passo a passo (como root)

1. Instale o Git:

   ```bash
   apt-get update && apt-get install -y git
   ```

2. Baixe o repositório **exatamente** em `/opt/sennaguard` (o instalador confere o caminho):

   ```bash
   git clone https://github.com/MathZiraA/sennaguard.git /opt/sennaguard
   ```

3. Rode o instalador:

   ```bash
   bash /opt/sennaguard/deploy/instalar.sh
   ```

   Ele vai perguntar:
   - o token do bot do Telegram (crie no `@BotFather`; Enter para pular);
   - o e-mail, o nome e a senha do primeiro administrador (só na primeira vez).

4. No fim aparece `SennaGuard no ar: https://<IP>/sennaguard/`. Abra no navegador e entre com o administrador que acabou de criar.

5. Se aparecer o bloco de comandos RouterOS, cole no terminal do R-MATRIZ (WinBox → New Terminal). Ele cria o usuário `sennaguard-teste`, usado só pelo teste de failover.

6. Nos PCs da Filial, instale a CA do NOC (`http://<IP>/NOC-SENAI-CA.crt`), como já é feito para o Zabbix, e acesse `https://<IP>/sennaguard/`.

### Conferir

```bash
systemctl status sennaguard                    # deve estar "active (running)"
curl -s http://127.0.0.1:8010/api/publico      # deve responder {"simulacao":false,...}
journalctl -u sennaguard -f                    # log ao vivo
```

### Atualizar para a última versão

```bash
bash /opt/sennaguard/deploy/atualizar.sh
```

Mantém o banco, os usuários e a configuração (`/etc/sennaguard/sennaguard.env`).

---

## 2. Linux: teste local

Funciona em Debian, Ubuntu, Mint e derivados. Não precisa de root depois da instalação dos pacotes.

1. Instale Git, Python e Node.js 20:

   ```bash
   sudo apt-get update
   sudo apt-get install -y git python3 python3-venv curl
   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
   sudo apt-get install -y nodejs
   ```

   Confira: `python3 --version` (3.11+) e `node -v` (v20+).

2. Baixe o repositório:

   ```bash
   git clone https://github.com/MathZiraA/sennaguard.git ~/sennaguard
   cd ~/sennaguard
   ```

3. Instale a API num ambiente virtual:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r backend/requirements.txt
   ```

4. Instale e compile a interface:

   ```bash
   cd frontend
   npm ci
   npm run build
   cd ..
   ```

5. Suba a API (terminal 1, deixe aberto):

   ```bash
   cd ~/sennaguard/backend
   ../.venv/bin/python -m uvicorn main:app --port 8000
   ```

6. Suba a interface (terminal 2, deixe aberto):

   ```bash
   cd ~/sennaguard/frontend
   npx vite preview
   ```

7. Abra **http://localhost:4173/sennaguard/** e entre com um usuário de demonstração.

Para desenvolver (a tela recarrega sozinha a cada alteração), troque os passos 5 e 6 por `uvicorn main:app --reload --port 8000` e `npm run dev`, e abra `http://localhost:5173/sennaguard/`.

---

## 3. Windows 10/11

Os comandos abaixo são para o **PowerShell**. Não precisa ser administrador, exceto para o `winget`, se ele pedir.

1. Instale Git, Python e Node.js (ou baixe de git-scm.com, python.org e nodejs.org):

   ```powershell
   winget install -e --id Git.Git
   winget install -e --id Python.Python.3.12
   winget install -e --id OpenJS.NodeJS.LTS
   ```

   **Feche e abra o PowerShell de novo** e confira: `git --version`, `python --version` (3.11+) e `node -v` (v20+).

   > Se `python` abrir a Microsoft Store, desligue o atalho em Configurações → Aplicativos → Configurações avançadas de aplicativos → Aliases de execução de aplicativos (`python.exe` e `python3.exe`).

2. Baixe o repositório:

   ```powershell
   cd $HOME\Documents
   git clone https://github.com/MathZiraA/sennaguard.git
   cd sennaguard
   ```

3. Instale a API num ambiente virtual:

   ```powershell
   python -m venv .venv
   .venv\Scripts\python -m pip install -r backend\requirements.txt
   ```

   Chamar `.venv\Scripts\python` direto dispensa o `Activate.ps1`, que costuma ser bloqueado pela política de execução do PowerShell. Pelo mesmo motivo, os passos usam `npm.cmd` e `npx.cmd` em vez de `npm` e `npx`.

   > No **Prompt de Comando** (cmd) também funciona: troque `cd` por `cd /d` e pode usar `npm`/`npx` normalmente.

4. Instale e compile a interface:

   ```powershell
   cd frontend
   npm.cmd ci
   npm.cmd run build
   cd ..
   ```

5. Suba a API (janela 1 do PowerShell, deixe aberta):

   ```powershell
   cd $HOME\Documents\sennaguard\backend
   ..\.venv\Scripts\python -m uvicorn main:app --port 8000
   ```

6. Suba a interface (janela 2 do PowerShell, deixe aberta):

   ```powershell
   cd $HOME\Documents\sennaguard\frontend
   npx.cmd vite preview
   ```

7. Abra **http://localhost:4173/sennaguard/** e entre com um usuário de demonstração. Use `localhost`, não `127.0.0.1`: no Windows o Vite escuta só no endereço IPv6 (`::1`).

Para desenvolver, troque os passos 5 e 6 por `..\.venv\Scripts\python -m uvicorn main:app --reload --port 8000` e `npm.cmd run dev`, e abra `http://localhost:5173/sennaguard/`.

Para parar, aperte `Ctrl+C` nas duas janelas.

### Abrir em outro PC da rede (opcional)

1. Suba a interface com `npx.cmd vite preview --host`.
2. Libere a porta no firewall (PowerShell como administrador):

   ```powershell
   New-NetFirewallRule -DisplayName "SennaGuard" -Direction Inbound -Protocol TCP -LocalPort 4173 -Action Allow
   ```

3. No outro PC, abra `http://<IP deste PC>:4173/sennaguard/`.

A API continua só em `127.0.0.1:8000`; o Vite repassa as chamadas para ela.

---

## Ligar ao Zabbix real (fora do servidor do NOC)

No Linux e no Windows de teste, o SennaGuard lê a configuração de variáveis de ambiente. Defina-as **na janela da API, antes do passo 5**.

| Variável | Exemplo | Para quê |
| --- | --- | --- |
| `ZABBIX_URL` | `https://192.168.10.50/zabbix/api_jsonrpc.php` | API do Zabbix (sem ela, simulação) |
| `ZABBIX_TOKEN` | token gerado no Zabbix (Usuários → Tokens de API) | autenticação no Zabbix |
| `NOC_HOST` | `R-FILIAL` | host do Zabbix com as interfaces dos enlaces |
| `NOC_FIBRA_FILIAL` / `NOC_RADIO_FILIAL` | `10.0.1.2` / `10.0.2.2` | IP da Filial em cada enlace |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | chave da IA | Analista IA e "Pergunte ao NOC" |
| `TELEGRAM_TOKEN` | token do `@BotFather` | avisos pelo Telegram |

Linux:

```bash
export ZABBIX_URL=https://192.168.10.50/zabbix/api_jsonrpc.php
export ZABBIX_TOKEN=cole-o-token-aqui
```

Windows (PowerShell):

```powershell
$env:ZABBIX_URL = "https://192.168.10.50/zabbix/api_jsonrpc.php"
$env:ZABBIX_TOKEN = "cole-o-token-aqui"
```

O Zabbix do NOC usa HTTPS com a CA própria: esta máquina precisa confiar nela (`http://192.168.10.50/NOC-SENAI-CA.crt`). No Windows, instale o `.crt` em "Autoridades de Certificação Raiz Confiáveis"; no Linux, copie para `/usr/local/share/ca-certificates/` e rode `sudo update-ca-certificates`.

Fora da simulação não há usuários de demonstração (se você já rodou em simulação antes, apague a pasta `backend/dados` para começar do zero). Crie o primeiro administrador, na mesma janela e com as mesmas variáveis:

```bash
cd backend
../.venv/bin/python gerenciar.py criar-admin --email voce@exemplo.com --nome "Seu Nome"      # Linux
..\.venv\Scripts\python gerenciar.py criar-admin --email voce@exemplo.com --nome "Seu Nome"  # Windows
```

O banco fica em `backend/dados/sennaguard.db` (para trocar de lugar, use `SENNAGUARD_BANCO`).

O **backup dos roteadores** e o **teste de failover** usam chaves SSH dos MikroTik e só funcionam de dentro da rede do NOC. Fora do servidor, aponte as chaves com `SENNAGUARD_MIKROTIK_KEY` e `SENNAGUARD_TESTE_KEY`. O uso real fica no servidor do NOC (seção 1).

---

## Problemas comuns

| Sintoma | Causa e solução |
| --- | --- |
| `npm run build` falha falando do Tailwind ou de `node:` | Node antigo: instale o 20 ou mais novo |
| A página abre, mas o login dá erro de conexão | a API (passo 5) não está rodando, ou não está na porta 8000 |
| `http://127.0.0.1:4173` não abre no Windows | use `http://localhost:4173/sennaguard/` |
| Abrir `http://localhost:4173/` dá tela em branco | falta o `/sennaguard/` no fim do endereço |
| `Activate.ps1 não pode ser carregado` | não precisa ativar: use `.venv\Scripts\python ...` como nos passos |
| `npm.ps1 não pode ser carregado` (PowerShell) | use `npm.cmd` e `npx.cmd`, ou rode no Prompt de Comando |
| `cd /d` dá erro de "parâmetro posicional" | `/d` é do Prompt de Comando; no PowerShell use só `cd` |
| No servidor: `Clone o repositório em /opt/sennaguard` | o instalador só roda a partir de `/opt/sennaguard` |
| No servidor: `O serviço não respondeu` | veja `journalctl -u sennaguard -n 50` |
| Esqueceu a senha do administrador (servidor) | `cd /opt/sennaguard/backend && sudo -u sennaguard env $(cat /etc/sennaguard/sennaguard.env \| xargs) ../.venv/bin/python gerenciar.py redefinir-senha --email x@y` |
