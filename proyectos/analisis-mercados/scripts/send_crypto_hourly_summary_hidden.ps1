$ErrorActionPreference = 'Stop'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'crypto_hourly_summary.log'
"[$(Get-Date -Format s)] START crypto_hourly_summary" | Add-Content $log
& "C:\Windows\py.exe" -3 "$base\scripts\send_crypto_hourly_summary.py" 2>&1 | Add-Content $log
"[$(Get-Date -Format s)] EXITCODE=$LASTEXITCODE" | Add-Content $log
exit $LASTEXITCODE
