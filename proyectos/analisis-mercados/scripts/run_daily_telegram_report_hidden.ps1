$ErrorActionPreference = 'Stop'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'daily_telegram_report.log'
"[$(Get-Date -Format s)] START daily_telegram_report" | Add-Content $log

& $ps -NoProfile -ExecutionPolicy Bypass -File "$base\scripts\run_daily_telegram_report.ps1" 2>&1 | Add-Content $log
"[$(Get-Date -Format s)] EXITCODE=$LASTEXITCODE" | Add-Content $log
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
