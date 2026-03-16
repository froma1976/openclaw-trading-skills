param([switch]$HiddenChild)

if (-not $HiddenChild) {
  Start-Process -FilePath 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath, '-HiddenChild') -WindowStyle Hidden
  exit 0
}

$ErrorActionPreference = 'Continue'
& "C:\Windows\py.exe" -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\audit_crypto_freshness.py" | Out-Null
