param([switch]$HiddenChild)

if (-not $HiddenChild) {
  Start-Process -FilePath 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath, '-HiddenChild') -WindowStyle Hidden
  exit 0
}

$ErrorActionPreference = 'Continue'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'universe_maintenance.log'

$ts = Get-Date -Format s
"[$ts] START universe_maintenance" | Add-Content $log

$py = 'C:\Windows\py.exe'

try {
  $steps = @(
    @{ Name = 'DATASET_QUALITY'; Cmd = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\dataset_quality.py' },
    @{ Name = 'EDGE_BREAKDOWN'; Cmd = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\edge_breakdown.py' },
    @{ Name = 'LEARNING_DAILY'; Cmd = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\learning_daily.py' },
    @{ Name = 'TRADE_EDGE_LEARNER'; Cmd = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\learn_from_crypto_trades.py' },
    @{ Name = 'CLASSIFY_UNIVERSE'; Cmd = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\classify_universe.py' },
    @{ Name = 'CRYPTO_SNAPSHOT'; Cmd = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\source_ingest_crypto_free.py' }
  )

  $failed = $false
  foreach ($step in $steps) {
    $out = & $py -3 $step.Cmd 2>&1
    $exitCode = $LASTEXITCODE
    if ($out) { $out | Add-Content $log }
    "[$(Get-Date -Format s)] $($step.Name)_EXITCODE=$exitCode" | Add-Content $log
    if ($exitCode -ne 0) { $failed = $true }
  }

  if ($failed) { exit 1 }
  exit 0
} catch {
  "[$(Get-Date -Format s)] ERROR $_" | Add-Content $log
  exit 1
}
