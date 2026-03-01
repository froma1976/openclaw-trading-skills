$ErrorActionPreference = 'SilentlyContinue'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'

# 1) refrescar señales y cards
& py -3 "$base\scripts\source_ingest_free.py" | Out-Null
& py -3 "$base\scripts\generate_claw_cards_mvp.py" | Out-Null

# 2) generar reporte diario
& py -3 "$base\scripts\generate_daily_report.py" | Out-Null

# 3) enviar por Telegram con OpenClaw CLI
$reportPath = "$base\data\daily_report_latest.txt"
if (Test-Path $reportPath) {
  $msg = Get-Content $reportPath -Raw
  if ($msg -and $msg.Trim().Length -gt 0) {
    & openclaw message send --channel telegram --target 161518227 --message "$msg" | Out-Null
  }
}
