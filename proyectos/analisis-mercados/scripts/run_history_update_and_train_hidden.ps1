param([switch]$HiddenChild)

if (-not $HiddenChild) {
  Start-Process -FilePath 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath, '-HiddenChild') -WindowStyle Hidden
  exit 0
}

$ErrorActionPreference = 'Continue'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'history_update_and_train.log'

"[$(Get-Date -Format s)] START history incremental + train" | Add-Content $log

& "C:\Windows\py.exe" -3 "$base\scripts\download_binance_history.py" --symbols BTCUSDT,ETHUSDT,SOLUSDT --interval 5m --years 5 --incremental 2>&1 | Add-Content $log
$e1 = $LASTEXITCODE
$trainSymbols = @('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
$trainExitCodes = @()
foreach ($trainSymbol in $trainSymbols) {
  & "C:\Windows\py.exe" -3 "$base\scripts\train_lstm_from_history.py" --symbols $trainSymbol --interval 5m --lookback 32 --epochs 8 --batch-size 128 --max-samples 40000 --eval-batch-size 256 2>&1 | Add-Content $log
  $symbolExit = $LASTEXITCODE
  "[$(Get-Date -Format s)] TRAIN_${trainSymbol}_EXITCODE=$symbolExit" | Add-Content $log
  $trainExitCodes += $symbolExit
}
$e2 = 0
if ($trainExitCodes | Where-Object { $_ -ne 0 }) { $e2 = 1 }

$exitCode = 0
if ($e1 -ne 0) { $exitCode = $e1 }
if ($e2 -ne 0) { $exitCode = $e2 }
"[$(Get-Date -Format s)] END exit=$exitCode" | Add-Content $log
exit $exitCode
