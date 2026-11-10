<#
Testa o arquivo gerado num MikroTik de fábrica SEM aplicar (dry-run do RouterOS 7): acha erro de sintaxe antes do reset.

Uso: powershell -ExecutionPolicy Bypass -File bancada\testar.ps1 -Equipamento R-MATRIZ
Resultado em bancada\saida\teste-resultado.txt, com as senhas mascaradas. A última linha tem de ser
"No syntax errors found in the import file".
#>
param([Parameter(Mandatory)][ValidateSet('R-MATRIZ', 'R-FILIAL')][string]$Equipamento)
$saida = Join-Path $PSScriptRoot 'saida'
$op = @('-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL', '-o', 'LogLevel=ERROR')
scp -O @op "$saida\$Equipamento.rsc" admin@192.168.88.1:/
$r = ssh @op admin@192.168.88.1 "/import file-name=$Equipamento.rsc dry-run verbose=yes"
$r | ForEach-Object { $_ -replace 'password=\S+', 'password=***' } | Set-Content -Encoding utf8 "$saida\teste-resultado.txt"
$fim = ($r | Select-Object -Last 1)
Write-Host "`n$fim" -ForegroundColor $(if ($fim -match 'No syntax errors') { 'Green' } else { 'Red' })
if ($fim -notmatch 'No syntax errors') { Write-Host 'Veja os erros em bancada\saida\teste-resultado.txt (procure "expected" ou "error").' }
