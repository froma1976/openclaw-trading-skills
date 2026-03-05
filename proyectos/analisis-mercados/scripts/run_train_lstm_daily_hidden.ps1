$ErrorActionPreference = 'Continue'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'train_lstm_daily.log'

$ts = Get-Date -Format s
"[$ts] START train_lstm_daily" | Add-Content $log

$py = 'C:\Windows\py.exe'
try {
  # 1) Actualizar histórico incremental (15m) para BTC y SOL
  $out0 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\download_binance_history.py" --symbols BTCUSDT,SOLUSDT --interval 15m --years 1 --incremental 2>&1
  $exit0 = $LASTEXITCODE
  if ($out0) { $out0 | Add-Content $log }
  "[$(Get-Date -Format s)] HISTORY_EXITCODE=$exit0" | Add-Content $log

  # 2) Entrenar BTCUSDT (15m)
  $out1 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\train_lstm.py" --ticker BTCUSDT --interval 15m --lookback 32 --epochs 12 2>&1
  $exit1 = $LASTEXITCODE
  if ($out1) { $out1 | Add-Content $log }
  "[$(Get-Date -Format s)] BTC_EXITCODE=$exit1" | Add-Content $log

  # 3) Entrenar SOLUSDT (15m)
  $out2 = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\train_lstm.py" --ticker SOLUSDT --interval 15m --lookback 32 --epochs 12 2>&1
  $exit2 = $LASTEXITCODE
  if ($out2) { $out2 | Add-Content $log }
  "[$(Get-Date -Format s)] SOL_EXITCODE=$exit2" | Add-Content $log

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

  if ($exit0 -ne 0 -or $exit1 -ne 0 -or $exit2 -ne 0 -or $exit3 -ne 0 -or $exit4 -ne 0 -or $exit5 -ne 0 -or $exit6 -ne 0) {
    exit 1
  }
  exit 0
} catch {
  "[$(Get-Date -Format s)] ERROR $_" | Add-Content $log
  exit 1
}
