$ErrorActionPreference = 'SilentlyContinue'
$log = 'C:\Users\Fernando\.openclaw\workspace\startup-stack.log'
"[$(Get-Date -Format s)] inicio startup" | Add-Content $log

# 1) Gateway
try {
  & openclaw gateway start | Out-Null
  "[$(Get-Date -Format s)] gateway start ok" | Add-Content $log
} catch {
  "[$(Get-Date -Format s)] gateway start error" | Add-Content $log
}

Start-Sleep -Seconds 5

# 2) Dashboard (si no está corriendo)
$dashCmd = 'uvicorn app:app --host 127.0.0.1 --port 8080'
$existing = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match [regex]::Escape($dashCmd) }
if (-not $existing) {
  Start-Process -FilePath "C:\Windows\py.exe" -ArgumentList "-3 -m $dashCmd" -WorkingDirectory "C:\Users\Fernando\.openclaw\workspace\agent-ops-dashboard" -WindowStyle Hidden
  "[$(Get-Date -Format s)] dashboard start launched" | Add-Content $log
} else {
  "[$(Get-Date -Format s)] dashboard already running" | Add-Content $log
}

# 3) Reintento de salud rápido
$ok = $false
for($i=0;$i -lt 4;$i++){
  Start-Sleep -Seconds 3
  try {
    $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health -TimeoutSec 4
    if($r.StatusCode -eq 200){ $ok = $true; break }
  } catch {}
}
$healthText = 'fail'
if($ok){ $healthText = 'ok' }
"[$(Get-Date -Format s)] dashboard health=$healthText" | Add-Content $log

# 4) Workspace visible
Start-Process explorer.exe "C:\Users\Fernando\.openclaw\workspace"
"[$(Get-Date -Format s)] fin startup" | Add-Content $log
