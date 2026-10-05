<#
Envia a configuração gerada para um MikroTik e manda ele se reconfigurar sozinho.

Uso (no notebook, com o cabo na porta ether1 do MikroTik que vai ser configurado):
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

$enviar = @($arquivo)
if ($Equipamento -eq 'R-FILIAL') { $enviar += (Join-Path $saida 'noc-analista.pub') }

# Os dois roteadores de fábrica respondem no mesmo IP: não guardar a "impressão digital" de nenhum
$opcoes = @('-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL', '-o', 'ConnectTimeout=8')

Write-Host "Testando $IP..."
if (-not (Test-Connection $IP -Count 2 -Quiet)) {
    Write-Host "O MikroTik não responde em $IP. Confira o cabo na ether1 e se o notebook pegou IP 192.168.88.x." -ForegroundColor Red
    Write-Host 'Equipamento já configurado antes? Use -IP com o IP atual dele (ex.: -IP 192.168.10.1 -Usuario admin_senai).'
    exit 1
}

Write-Host "`n1/2 Copiando $($enviar | ForEach-Object { Split-Path $_ -Leaf }) (digite a senha atual do MikroTik)"
& scp -O @opcoes @enviar "${Usuario}@${IP}:/"
if ($LASTEXITCODE -ne 0) { Write-Host 'Falha ao copiar. Senha certa? SSH habilitado?' -ForegroundColor Red; exit 1 }

Write-Host "`n2/2 Mandando o $Equipamento se reconfigurar (digite a senha de novo)"
Write-Host '    A conexão vai cair: é o MikroTik reiniciando. Isso é esperado.' -ForegroundColor Yellow
# Dentro de um script o RouterOS não pede confirmação do reset
$nome = Split-Path $arquivo -Leaf
$comando = "/system script add name=noc-aplicar source=`"/system reset-configuration no-defaults=yes skip-backup=yes run-after-reset=$nome`"; /system script run noc-aplicar"
& ssh @opcoes "${Usuario}@${IP}" $comando

Write-Host "`nPronto. Aguarde ~1 minuto e entre de novo pelo Winbox com admin_senai e a senha que você definiu." -ForegroundColor Green
switch ($Equipamento) {
    'R-MATRIZ'  { Write-Host 'O R-MATRIZ agora responde em 192.168.10.1 (ligue o notebook no SW-MATRIZ ou na ether1).' }
    'R-FILIAL'  { Write-Host 'O R-FILIAL agora responde em 192.168.20.1 (gerência só pela LAN da Filial).' }
    'SW-MATRIZ' { Write-Host 'O SW-MATRIZ agora responde em 192.168.10.2.' }
    'SW-FILIAL' { Write-Host 'O SW-FILIAL agora responde em 192.168.20.2.' }
}
Write-Host 'No terminal dele, "/log print where message~\"NOC SENAI\"" mostra se o arquivo foi aplicado até o fim.'
