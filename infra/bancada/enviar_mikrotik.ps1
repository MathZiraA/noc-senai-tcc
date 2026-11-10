<#
Envia a configuração gerada para um MikroTik e manda ele se reconfigurar sozinho.

Uso (no notebook, com o cabo na porta ether3, 4 ou 5 do MikroTik que vai ser configurado):
  powershell -ExecutionPolicy Bypass -File bancada\enviar_mikrotik.ps1 -Equipamento R-MATRIZ
  powershell -ExecutionPolicy Bypass -File bancada\enviar_mikrotik.ps1 -Equipamento R-FILIAL

O que acontece:
  1. Copia bancada\saida\<Equipamento>.rsc (e a chave do analista, no R-FILIAL) para o MikroTik.
  2. O MikroTik apaga a configuração atual, reinicia e aplica o arquivo sozinho (~1 minuto).
A senha pedida é a ATUAL do MikroTik: num equipamento de fábrica, a da etiqueta (ou vazia, só Enter).
#>
param(
    [Parameter(Mandatory)][ValidateSet('R-MATRIZ', 'R-FILIAL', 'SW-MATRIZ', 'SW-FILIAL')][string]$Equipamento,
    [string]$IP = '192.168.88.1',   # IP de fábrica do MikroTik
    [string]$Usuario = 'admin'
)
$ErrorActionPreference = 'Stop'
$saida = Join-Path $PSScriptRoot 'saida'
$arquivo = Join-Path $saida "$Equipamento.rsc"
if (-not (Test-Path $arquivo)) { Write-Host "Falta $arquivo. Rode antes: python bancada\gerar_configs.py" -ForegroundColor Red; exit 1 }

$nome = Split-Path $arquivo -Leaf
# O comando de reset vai num arquivo: o PowerShell 5.1 tira as aspas internas de argumentos passados ao ssh.
# Rodado por /import (script), o RouterOS não pede confirmação do reset.
$aplicar = Join-Path $saida 'noc-aplicar.rsc'
Set-Content -Path $aplicar -Encoding ascii -Value "/system reset-configuration no-defaults=yes skip-backup=yes run-after-reset=$nome"

$enviar = @($arquivo, $aplicar)
if ($Equipamento -eq 'R-FILIAL') { $enviar += (Join-Path $saida 'noc-analista.pub') }

# Os dois roteadores de fábrica respondem no mesmo IP: não guardar a "impressão digital" de nenhum
$opcoes = @('-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL', '-o', 'ConnectTimeout=8', '-o', 'LogLevel=ERROR')

Write-Host "Testando $IP..."
if (-not (Test-Connection $IP -Count 2 -Quiet)) {
    Write-Host "O MikroTik não responde em $IP. Confira o cabo numa porta de LAN (ether3-5) e se o notebook pegou IP 192.168.88.x." -ForegroundColor Red
    Write-Host 'Equipamento já configurado antes? Use -IP com o IP atual dele (ex.: -IP 192.168.10.1 -Usuario admin_senai).'
    exit 1
}

Write-Host "`n1/2 Copiando $($enviar | ForEach-Object { Split-Path $_ -Leaf }) (digite a senha atual do MikroTik)"
& scp -O @opcoes @enviar "${Usuario}@${IP}:/"
if ($LASTEXITCODE -ne 0) { Write-Host 'Falha ao copiar. Senha certa? SSH habilitado?' -ForegroundColor Red; exit 1 }

Write-Host "`n2/2 Mandando o $Equipamento se reconfigurar (digite a senha de novo)"
Write-Host '    A conexão vai cair: é o MikroTik reiniciando. Isso é esperado.' -ForegroundColor Yellow
# Sem 2>&1: no PowerShell 5.1 qualquer linha do ssh no stderr vira erro e mata o comando no meio.
# A resposta do RouterOS vem pelo stdout; erros de login o próprio ssh mostra na tela.
$ErrorActionPreference = 'Continue'
$resposta = @(& ssh @opcoes "${Usuario}@${IP}" "/import file-name=noc-aplicar.rsc")
$resposta | ForEach-Object { Write-Host "    $_" }
# (a conexão cair sem resposta é o sucesso: o MikroTik reiniciou para se reconfigurar)
if (($resposta -join ' ') -match 'error|failure') {
    Write-Host "O MikroTik recusou o comando acima: nada foi alterado. Mande o print para análise." -ForegroundColor Red
    exit 1
}

Write-Host "`nPronto. Aguarde ~1 minuto e entre de novo pelo Winbox com admin_senai e a senha que você definiu." -ForegroundColor Green
switch ($Equipamento) {
    'R-MATRIZ'  { Write-Host 'O R-MATRIZ agora responde em 192.168.10.1 (ligue o notebook no SW-MATRIZ ou nas portas 3, 4 ou 5).' }
    'R-FILIAL'  { Write-Host 'O R-FILIAL agora responde em 192.168.20.1 (gerência só pela LAN da Filial).' }
    'SW-MATRIZ' { Write-Host 'O SW-MATRIZ agora responde em 192.168.10.2.' }
    'SW-FILIAL' { Write-Host 'O SW-FILIAL agora responde em 192.168.20.2.' }
}
Write-Host 'No terminal dele, "/log print where message~\"NOC SENAI\"" mostra se o arquivo foi aplicado até o fim.'
