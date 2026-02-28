$ErrorActionPreference = 'SilentlyContinue'

# 1) Gateway
try {
  & openclaw gateway start | Out-Null
} catch {}

# 2) Dashboard (si no está corriendo)
$dashCmd = 'uvicorn app:app --host 127.0.0.1 --port 8080'
$existing = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match [regex]::Escape($dashCmd) }
if (-not $existing) {
  Start-Process -FilePath "py" -ArgumentList "-3 -m $dashCmd" -WorkingDirectory "C:\Users\Fernando\.openclaw\workspace\agent-ops-dashboard" -WindowStyle Hidden
}

# 3) Workspace visible (opcional, ayuda a continuidad)
Start-Process explorer.exe "C:\Users\Fernando\.openclaw\workspace"

Write-Output "OK startup stack"
