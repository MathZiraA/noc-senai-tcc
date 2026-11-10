<#
Atualiza um MikroTik de fábrica (192.168.88.1) do RouterOS 6 para o 7: envia o pacote e reinicia.

Uso (cabo do notebook na ether3 do MikroTik):
  powershell -ExecutionPolicy Bypass -File bancada\atualizar_v7.ps1
O pacote (hEX S = arquitetura mmips) fica em Documents\routeros-download; troque -Pacote para outro modelo.
Senha pedida: a atual do admin (de fábrica, vazia: só Enter). Depois, 2 a 3 minutos sem tirar da tomada.
#>
param([string]$Pacote = "$env:USERPROFILE\Documents\routeros-download\routeros-7.24.5-mmips.npk")
if (-not (Test-Path $Pacote)) {
    Write-Host "Pacote não encontrado: $Pacote" -ForegroundColor Red
    Write-Host 'Baixe em https://mikrotik.com/download (RouterOS 7, arquitetura do modelo; hEX S = MMIPS).'
    exit 1
}
$saida = Join-Path $PSScriptRoot 'saida'
New-Item -ItemType Directory -Force $saida | Out-Null
# RouterOS 6 só fala algoritmos SSH antigos: liberados só para esta conexão
$op = @('-o', 'MACs=+hmac-sha1', '-o', 'HostKeyAlgorithms=+ssh-rsa',
        '-o', 'KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1',
        '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL', '-o', 'LogLevel=ERROR')
# Reboot dentro de um /import não pede confirmação (e evita aspas, que o PowerShell 5.1 tira dos argumentos)
Set-Content -Path "$saida\noc-reboot.rsc" -Encoding ascii -Value '/system reboot'

Write-Host '1/2 Enviando o RouterOS 7 (Enter na senha)'
scp -O @op $Pacote "$saida\noc-reboot.rsc" admin@192.168.88.1:/
if ($LASTEXITCODE -ne 0) { Write-Host 'Falha ao enviar. O MikroTik está em 192.168.88.1?' -ForegroundColor Red; exit 1 }
Write-Host '2/2 Reiniciando para instalar (Enter na senha). A conexão cai: é esperado.'
ssh @op admin@192.168.88.1 '/import file-name=noc-reboot.rsc'
Write-Host "`nAguarde 2 a 3 minutos sem tirar da tomada. Depois o WinBox mostra a versão 7 em Neighbors." -ForegroundColor Green
