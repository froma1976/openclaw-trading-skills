$ErrorActionPreference = 'Continue'

$tasks = @(
  'OpenClaw Gateway',
  'OpenClaw Node',
  'OpenClaw-Autopilot-15m',
  'OpenClaw-Crypto-Ingest-2m',
  'OpenClaw-Crypto-Scalp-1m',
  'OpenClaw-Crypto-Stream-Probe-3m',
  'OpenClaw-Crypto-Watchdog-10m',
  'OpenClaw-Train-LSTM-Daily',
  'LSTM Train (6h)'
)

$out = @()
foreach ($name in $tasks) {
  $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  if (-not $task) { continue }
  $info = Get-ScheduledTaskInfo -TaskName $name -ErrorAction SilentlyContinue
  $out += [pscustomobject]@{
    task = $name
    state = [string]$task.State
    last_result = $info.LastTaskResult
    last_run = $info.LastRunTime
    next_run = $info.NextRunTime
  }
}

$gatewayListening = @(Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue).Count -gt 0

$dashboard = $null
try {
  $dashboard = (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health -TimeoutSec 5).StatusCode
} catch {
  $dashboard = 'down'
}

[pscustomobject]@{
  checked_at = Get-Date
  gateway_18789 = $gatewayListening
  dashboard_health = $dashboard
  tasks = $out
} | ConvertTo-Json -Depth 4
