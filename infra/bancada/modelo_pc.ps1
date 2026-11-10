# Configura o IP fixo deste PC na bancada NOC SENAI. Rode no PowerShell COMO ADMINISTRADOR:
#   powershell -ExecutionPolicy Bypass -File .\__ARQUIVO__
# IP __IP__/24, gateway __GW__, MTU 2000 (teste de jumbo frame) e resposta a ping liberada.
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Abra o PowerShell como administrador e rode de novo.' -ForegroundColor Red; exit 1
}

# Placa de rede cabeada que está conectada (ignora Wi-Fi e placas virtuais)
$placa = Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' -and $_.MediaType -eq '802.3' } |
    Select-Object -First 1
if (-not $placa) { Write-Host 'Nenhuma placa de rede com cabo conectado.' -ForegroundColor Red; exit 1 }
Write-Host "Placa: $($placa.Name) ($($placa.InterfaceDescription))"

Set-NetIPInterface -InterfaceIndex $placa.ifIndex -Dhcp Disabled
Get-NetIPAddress -InterfaceIndex $placa.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Remove-NetIPAddress -Confirm:$false
Get-NetRoute -InterfaceIndex $placa.ifIndex -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
    Remove-NetRoute -Confirm:$false
New-NetIPAddress -InterfaceIndex $placa.ifIndex -IPAddress '__IP__' -PrefixLength 24 -DefaultGateway '__GW__' | Out-Null

# MTU 2000: só funciona se a placa aceitar jumbo frames (senão fica em 1500 e o teste de 1972 bytes falha)
try { Set-NetIPInterface -InterfaceIndex $placa.ifIndex -NlMtuBytes 2000 } catch {
    Write-Host 'Aviso: a placa não aceitou MTU 2000; o ping de 1972 bytes não vai passar neste PC.' -ForegroundColor Yellow
}

# Responder a ping (o Windows bloqueia por padrão)
Get-NetFirewallRule -Name 'FPS-ICMP4-ERQ-In*', 'CoreNet-Diag-ICMP4-EchoRequest-In*' -ErrorAction SilentlyContinue |
    Enable-NetFirewallRule

Write-Host "`nPronto: $($placa.Name) = __IP__/24, gateway __GW__" -ForegroundColor Green
Write-Host 'Teste: ping __GW__'
