$ErrorActionPreference = 'Continue'
$log = 'C:\Users\Fernando\.openclaw\workspace\startup-stack.log'
"[$(Get-Date -Format s)] inicio startup" | Add-Content $log

function Get-OpenClawProcCount([string]$needle) {
  return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq 'node.exe' -and ($_.CommandLine -like "*$needle*") }).Count
}

function Test-ListeningPort([int]$port) {
  return @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).Count -gt 0
}

$gatewayNeedle = 'openclaw\dist\index.js gateway --port 18789'
$nodeNeedle = 'openclaw\dist\index.js node run --host 127.0.0.1 --port 18789'

# 1) Gateway
try {
  $gatewayBefore = Get-OpenClawProcCount $gatewayNeedle
  & 'C:\Users\Fernando\.openclaw\gateway.cmd' | Out-Null
  $gatewayListening = Test-ListeningPort 18789
  $gatewayAfter = Get-OpenClawProcCount $gatewayNeedle
  "[$(Get-Date -Format s)] gateway start requested before=$gatewayBefore after=$gatewayAfter listening=$gatewayListening" | Add-Content $log
} catch {
  "[$(Get-Date -Format s)] gateway start error" | Add-Content $log
}

Start-Sleep -Seconds 5

# 1b) Node host
try {
  $nodeBefore = Get-OpenClawProcCount $nodeNeedle
  & 'C:\Users\Fernando\.openclaw\node.cmd' | Out-Null
  $nodeAfter = Get-OpenClawProcCount $nodeNeedle
  "[$(Get-Date -Format s)] node host start requested before=$nodeBefore after=$nodeAfter" | Add-Content $log
} catch {
  "[$(Get-Date -Format s)] node host start error" | Add-Content $log
}

Start-Sleep -Seconds 3

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
