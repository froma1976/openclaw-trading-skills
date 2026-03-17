param([switch]$HiddenChild)

if (-not $HiddenChild) {
  Start-Process -FilePath 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath, '-HiddenChild') -WindowStyle Hidden
  exit 0
}

$ErrorActionPreference = 'Continue'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'system_audit.log'

"[$(Get-Date -Format s)] START system_audit" | Add-Content $log
& "C:\Windows\py.exe" -3 "$base\scripts\generate_system_audit_report.py" 2>&1 | Add-Content $log
$exit1 = $LASTEXITCODE
"[$(Get-Date -Format s)] GENERATE_EXITCODE=$exit1" | Add-Content $log
& "C:\Windows\py.exe" -3 "$base\scripts\send_system_audit_report.py" 2>&1 | Add-Content $log
$exit2 = $LASTEXITCODE
"[$(Get-Date -Format s)] SEND_EXITCODE=$exit2" | Add-Content $log
$exitCode = 0
if ($exit1 -ne 0 -or $exit2 -ne 0) { $exitCode = 1 }
"[$(Get-Date -Format s)] END exit=$exitCode" | Add-Content $log
exit $exitCode
