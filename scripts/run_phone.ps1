# Serve Ghostlab over HTTPS on your Wi-Fi so an iPhone can use the camera, microphone and export.
# Safari only allows the microphone on HTTPS, so this makes a self-signed certificate (kept in work/, never committed).
# The Meta key is asked for here in the terminal and lives only in this process. Leave it blank to serve the bundled demos.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$certDir = "work/cert"; $key = "$certDir/key.pem"; $crt = "$certDir/cert.pem"
New-Item -ItemType Directory -Force $certDir | Out-Null
$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -match '^(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))\.' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback' } | Select-Object -ExpandProperty IPAddress
if (-not $ips) { throw "No Wi-Fi/LAN address found. Connect the PC to the same Wi-Fi as the phone." }
if (-not (Test-Path $crt)) {
  $san = ($ips | ForEach-Object { "IP:$_" }) -join ","
  $ErrorActionPreference = "Continue"
  & openssl req -x509 -newkey rsa:2048 -nodes -keyout $key -out $crt -days 7 -subj "/CN=ghostlab" -addext "subjectAltName=$san,DNS:localhost" 2>$null
  $ErrorActionPreference = "Stop"
  if (-not (Test-Path $crt)) { throw "openssl failed; run this from Git Bash or install openssl." }
}
$plain = ""
if (-not $env:GHOSTLAB_NO_PROMPT) {
  $secure = Read-Host "Meta MODEL_API_KEY (input hidden; Enter to skip)" -AsSecureString
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}
if ($plain) { $env:MODEL_API_KEY = $plain } else { Remove-Item Env:MODEL_API_KEY -ErrorAction SilentlyContinue; Write-Host "No key: bundled demo clips only." }
$ips | ForEach-Object { Write-Host "On the phone (same Wi-Fi), open:  https://$($_):8791" -ForegroundColor Cyan }
Write-Host "Safari will warn about the certificate: Show Details -> visit this website. Ctrl+C here to stop." -ForegroundColor Yellow
& .venv/Scripts/python.exe -m uvicorn ghostlab.server:app --host 0.0.0.0 --port 8791 --ssl-keyfile $key --ssl-certfile $crt
