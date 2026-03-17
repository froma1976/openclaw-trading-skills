$ErrorActionPreference = 'Stop'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'

# 1) refrescar señales y cards
& py -3 "$base\scripts\source_ingest_free.py" | Out-Null
& py -3 "$base\scripts\generate_claw_cards_mvp.py" | Out-Null

# 2) generar reporte diario
& py -3 "$base\scripts\generate_daily_report.py" | Out-Null

# 2b) generar auditoria operativa del sistema
& py -3 "$base\scripts\generate_system_audit_report.py" | Out-Null

# 3) enviar por Telegram con OpenClaw CLI
& py -3 "$base\scripts\send_daily_telegram_report.py" | Out-Null

# 4) enviar auditoria operativa por Telegram
& py -3 "$base\scripts\send_system_audit_report.py" | Out-Null

exit $LASTEXITCODE
