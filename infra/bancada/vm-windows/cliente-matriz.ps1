# Configura a VM Windows como cliente da Matriz (NOC SENAI TCC)
# Rodar no PowerShell COMO ADMINISTRADOR, dentro da VM (placa em Bridged na rede da Matriz)
$ErrorActionPreference = "Stop"
$IP = "192.168.10.11"; $GW = "192.168.10.1"; $DNS = "192.168.10.1"

$placa = Get-NetAdapter | Where-Object Status -eq "Up" | Select-Object -First 1
if (-not $placa) { throw "Nenhuma placa de rede conectada. Confira o cabo e o modo Bridged da VM." }
Write-Host "Placa: $($placa.Name)"

# IP fixo, gateway e DNS do R-MATRIZ
Set-NetIPInterface -InterfaceIndex $placa.ifIndex -Dhcp Disabled
Get-NetIPAddress -InterfaceIndex $placa.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false
Get-NetRoute -InterfaceIndex $placa.ifIndex -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue | Remove-NetRoute -Confirm:$false
New-NetIPAddress -InterfaceIndex $placa.ifIndex -IPAddress $IP -PrefixLength 24 -DefaultGateway $GW | Out-Null
Set-DnsClientServerAddress -InterfaceIndex $placa.ifIndex -ServerAddresses $DNS

# Rede privada e ping liberado (o NOC e a Filial testam por ping)
Start-Sleep 3
Set-NetConnectionProfile -InterfaceIndex $placa.ifIndex -NetworkCategory Private
if (-not (Get-NetFirewallRule -DisplayName "Ping NOC" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Ping NOC" -Protocol ICMPv4 -IcmpType 8 -Direction Inbound -Action Allow | Out-Null
}

# Nome do computador (vale depois de reiniciar)
if ($env:COMPUTERNAME -ne "PC-MATRIZ") { Rename-Computer -NewName "PC-MATRIZ" -Force }

Write-Host "`nTestes:"
foreach ($alvo in "192.168.10.1", "192.168.10.50", "192.168.20.1", "8.8.8.8") {
    "{0,-15} {1}" -f $alvo, $(if (Test-Connection $alvo -Count 2 -Quiet) { "OK" } else { "sem resposta" })
}
"{0,-15} {1}" -f "google.com", $(try { Resolve-DnsName google.com -ErrorAction Stop | Out-Null; "DNS OK" } catch { "DNS falhou" })
Write-Host "`nPronto. Reinicie a VM para aplicar o nome PC-MATRIZ."
