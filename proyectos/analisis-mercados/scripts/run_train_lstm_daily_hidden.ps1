param([switch]$HiddenChild)

if (-not $HiddenChild) {
  Start-Process -FilePath 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath, '-HiddenChild') -WindowStyle Hidden
  exit 0
}

$ErrorActionPreference = 'Continue'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'train_lstm_daily.log'

$ts = Get-Date -Format s
"[$ts] START train_lstm_daily" | Add-Content $log

$py = 'C:\Windows\py.exe'
try {
  # 0) Ingesta pública OHLCV (CryptoDataDownload, diario)
  $outp = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\ingest_public_ohlcv.py" 2>&1
  $exitp = $LASTEXITCODE
  if ($outp) { $outp | Add-Content $log }
  "[$(Get-Date -Format s)] PUBLIC_OHLCV_EXITCODE=$exitp" | Add-Content $log

  # 1) Actualizar histórico incremental (5m) para BTC, ETH y SOL
  $out0 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\download_binance_history.py" --symbols BTCUSDT,ETHUSDT,SOLUSDT --interval 5m --years 1 --incremental 2>&1
  $exit0 = $LASTEXITCODE
  if ($out0) { $out0 | Add-Content $log }
  "[$(Get-Date -Format s)] HISTORY_EXITCODE=$exit0" | Add-Content $log

  # 2) Entrenar LSTM por simbolo en procesos separados para evitar acumulacion de memoria
  $trainScript = "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\train_lstm_from_history.py"
  $trainSymbols = @('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
  $trainExitCodes = @()
  foreach ($trainSymbol in $trainSymbols) {
    $out1 = & $py -3 $trainScript --symbols $trainSymbol --interval 5m --lookback 32 --epochs 8 --patience 5 --batch-size 128 --max-samples 40000 --eval-batch-size 256 2>&1
    $symbolExit = $LASTEXITCODE
    if ($out1) { $out1 | Add-Content $log }
    "[$(Get-Date -Format s)] TRAIN_${trainSymbol}_EXITCODE=$symbolExit" | Add-Content $log
    $trainExitCodes += $symbolExit
  }
  $exit1 = 0
  if ($trainExitCodes | Where-Object { $_ -ne 0 }) { $exit1 = 1 }
  "[$(Get-Date -Format s)] TRAIN_FROM_HISTORY_EXITCODE=$exit1" | Add-Content $log

  # 3) Compat: se mantiene variable para la validación final del script
  $exit2 = 0

  # 4) Calidad de dataset (trade-by-trade limpio desde órdenes disponibles)
  $out3 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\dataset_quality.py" 2>&1
  $exit3 = $LASTEXITCODE
  if ($out3) { $out3 | Add-Content $log }
  "[$(Get-Date -Format s)] DATASET_QUALITY_EXITCODE=$exit3" | Add-Content $log

  # 5) Walk-forward + baseline
  $out4 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\walkforward_eval.py" 2>&1
  $exit4 = $LASTEXITCODE
  if ($out4) { $out4 | Add-Content $log }
  "[$(Get-Date -Format s)] WALKFORWARD_EXITCODE=$exit4" | Add-Content $log

  # 6) Actualizar registry de modelos (champion + historial)
  $out5 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\model_registry_update.py" 2>&1
  $exit5 = $LASTEXITCODE
  if ($out5) { $out5 | Add-Content $log }
  "[$(Get-Date -Format s)] REGISTRY_EXITCODE=$exit5" | Add-Content $log

  # 7) Resumen diario aprendizaje
  $out6 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\learning_daily.py" 2>&1
  $exit6 = $LASTEXITCODE
  if ($out6) { $out6 | Add-Content $log }
  "[$(Get-Date -Format s)] LEARNING_EXITCODE=$exit6" | Add-Content $log

  # 8) Breakdown de edge
  $out7 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\edge_breakdown.py" 2>&1
  $exit7 = $LASTEXITCODE
  if ($out7) { $out7 | Add-Content $log }
  "[$(Get-Date -Format s)] EDGE_BREAKDOWN_EXITCODE=$exit7" | Add-Content $log

  # 9) Reclasificacion de universo
  $out8 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\classify_universe.py" 2>&1
  $exit8 = $LASTEXITCODE
  if ($out8) { $out8 | Add-Content $log }
  "[$(Get-Date -Format s)] UNIVERSE_EXITCODE=$exit8" | Add-Content $log

  # 10) Snapshot actualizado con nuevo universo
  $out9 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\source_ingest_crypto_free.py" 2>&1
  $exit9 = $LASTEXITCODE
  if ($out9) { $out9 | Add-Content $log }
  "[$(Get-Date -Format s)] SNAPSHOT_EXITCODE=$exit9" | Add-Content $log

  if ($exit0 -ne 0 -or $exit1 -ne 0 -or $exit3 -ne 0 -or $exit4 -ne 0 -or $exit5 -ne 0 -or $exit6 -ne 0 -or $exit7 -ne 0 -or $exit8 -ne 0 -or $exit9 -ne 0) {
    exit 1
  }
  exit 0
} catch {
  "[$(Get-Date -Format s)] ERROR $_" | Add-Content $log
  exit 1
}
