$ErrorActionPreference = 'Continue'
$base = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados'
$logDir = Join-Path $base 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir 'research_experiment_queue.log'

$ts = Get-Date -Format s
"[$ts] START research_experiment_queue" | Add-Content $log

$py = 'C:\Windows\py.exe'
$script = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\run_research_experiment_queue.py'

try {
  $out = & $py -3 $script 2>&1
  $exitCode = $LASTEXITCODE
  if ($out) { $out | Add-Content $log }
  "[$(Get-Date -Format s)] RESEARCH_EXPERIMENT_QUEUE_EXITCODE=$exitCode" | Add-Content $log
  exit $exitCode
} catch {
  "[$(Get-Date -Format s)] ERROR $_" | Add-Content $log
  exit 1
}
