$ErrorActionPreference = 'Stop'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'crypto_ingest.log'
$lock = Join-Path $logDir 'crypto_ingest.lock'

if (Test-Path $lock) {
  "[$(Get-Date -Format s)] SKIP lock activo" | Add-Content $log
  exit 0
}

New-Item -ItemType File -Path $lock -Force | Out-Null

try {
"[$(Get-Date -Format s)] START crypto_ingest" | Add-Content $log
& "C:\Windows\py.exe" -3 "$base\scripts\source_ingest_crypto_free.py" 2>&1 | Add-Content $log
"[$(Get-Date -Format s)] EXITCODE=$LASTEXITCODE" | Add-Content $log
exit $LASTEXITCODE
} finally {
  if (Test-Path $lock) { Remove-Item $lock -Force -ErrorAction SilentlyContinue }
}
