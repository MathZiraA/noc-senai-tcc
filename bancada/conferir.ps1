<#
Lê a configuração de um roteador já configurado (somente leitura) e testa, de dentro dele, o caminho até o outro lado.

Uso (notebook na LAN do roteador, ether3):
  powershell -ExecutionPolicy Bypass -File bancada\conferir.ps1 -IP 192.168.20.1   (R-FILIAL)
  powershell -ExecutionPolicy Bypass -File bancada\conferir.ps1 -IP 192.168.10.1   (R-MATRIZ)
Senha: a do admin_senai daquele roteador. Resultado em bancada\saida\conferir-<IP>.txt (sem senhas).
#>
param([string]$IP = '192.168.20.1')
if ($IP -eq '192.168.10.1') { $lado = 'FILIAL'; $fibra = '10.0.1.2'; $radio = '10.0.2.2'; $lo = '10.255.255.2'; $lan = '192.168.20.1'; $src = '192.168.10.1' }
else                        { $lado = 'MATRIZ'; $fibra = '10.0.1.1'; $radio = '10.0.2.1'; $lo = '10.255.255.1'; $lan = '192.168.10.1'; $src = '192.168.20.1' }
# Sem aspas dentro do comando: o PowerShell 5.1 as remove ao passar para o ssh
$cmd = '/system identity print; /system resource print; /interface print; /interface bridge port print; ' +
       '/ip address print; /ip dhcp-server print; /routing ospf instance print; /routing ospf area print; ' +
       '/routing ospf interface-template print; /routing ospf neighbor print; /ip route print; ' +
       '/tool netwatch print; /ip firewall filter print; /ip service print; /user print; /system scheduler print; ' +
       ":put PING-FIBRA-$lado; /ping $fibra count=3; :put PING-RADIO-$lado; /ping $radio count=3; " +
       ":put PING-LOOPBACK-$lado; /ping $lo count=3; :put PING-LAN-$lado; /ping $lan src-address=$src count=3; " +
       ":put TRACEROUTE; /tool traceroute $lan src-address=$src count=1"
$r = ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o LogLevel=ERROR "admin_senai@$IP" $cmd
$saida = Join-Path $PSScriptRoot 'saida'
New-Item -ItemType Directory -Force $saida | Out-Null
$r | Set-Content -Encoding utf8 "$saida\conferir-$IP.txt"
Write-Host "`nLeitura concluída: $($r.Count) linhas em bancada\saida\conferir-$IP.txt" -ForegroundColor Green
# Resumo rápido dos pings
$r | Select-String -Pattern '^PING-|sent=' | ForEach-Object { Write-Host "  $($_.Line.Trim())" }
