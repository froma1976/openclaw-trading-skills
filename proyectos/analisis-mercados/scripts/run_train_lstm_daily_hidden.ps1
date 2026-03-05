$ErrorActionPreference = 'Continue'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'train_lstm_daily.log'

$ts = Get-Date -Format s
"[$ts] START train_lstm_daily" | Add-Content $log

$py = 'C:\Windows\py.exe'
$args = '-3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\train_lstm.py" --ticker BTCUSDT --interval 5m --lookback 32 --epochs 10'

try {
  $out = & $py -3 "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\train_lstm.py" --ticker BTCUSDT --interval 5m --lookback 32 --epochs 10 2>&1
  $exit = $LASTEXITCODE
  if ($out) { $out | Add-Content $log }
  "[$(Get-Date -Format s)] EXITCODE=$exit" | Add-Content $log
  exit $exit
} catch {
  "[$(Get-Date -Format s)] ERROR $_" | Add-Content $log
  exit 1
}
