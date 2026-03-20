$ErrorActionPreference = 'Continue'

$gatewayNeedle = 'openclaw\dist\index.js gateway --port 18789'
$nodeNeedle = 'openclaw\dist\index.js node run --host 127.0.0.1 --port 18789'
$lstmLockPath = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\logs\history_train.lock'
$lstmJobNeedle = 'run_history_update_and_train_hidden.ps1'

function Get-OpenClawProcCount([string]$needle) {
  return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq 'node.exe' -and ($_.CommandLine -like "*$needle*") }).Count
}

function Get-LstmJobCount {
  return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { ($_.CommandLine -like "*$lstmJobNeedle*") -or ($_.CommandLine -like '*train_lstm_from_history.py*') -or ($_.CommandLine -like '*download_binance_history.py*') }).Count
}

function Resolve-TaskHealth($name, $result, $state, $gatewayListening, $nodeRunning, $lstmLock, $lstmProcCount) {
  $status = 'ok'
  $detail = 'healthy'
  $isBad = $false

  if ($result -eq 0 -or $null -eq $result) {
    if ($name -eq 'LSTM Train (6h)' -and $lstmLock.exists -and $lstmProcCount -le 0) {
      $status = 'warning'
      $detail = 'stale_lock_detected'
      $isBad = $true
    }
    return [pscustomobject]@{ status = $status; detail = $detail; is_bad = $isBad }
  }

  if ($result -eq 3221225786 -and $name -eq 'OpenClaw Gateway' -and $gatewayListening) {
    return [pscustomobject]@{ status = 'warning'; detail = 'interrupted_but_listening'; is_bad = $false }
  }
  if ($result -eq 3221225786 -and $name -eq 'OpenClaw Node' -and $nodeRunning) {
    return [pscustomobject]@{ status = 'warning'; detail = 'interrupted_but_running'; is_bad = $false }
  }
  if ($result -eq 2147946720 -and $name -eq 'LSTM Train (6h)') {
    if ($lstmLock.exists -and $lstmProcCount -le 0) {
      return [pscustomobject]@{ status = 'error'; detail = 'blocked_by_stale_lock'; is_bad = $true }
    }
    if ($lstmProcCount -gt 0) {
      return [pscustomobject]@{ status = 'warning'; detail = 'job_running_or_recently_blocked'; is_bad = $false }
    }
  }

  return [pscustomobject]@{ status = 'error'; detail = 'last_result_non_zero'; is_bad = $true }
}

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
$gatewayListening = @(Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue).Count -gt 0
$nodeRunning = (Get-OpenClawProcCount $nodeNeedle) -gt 0
foreach ($name in $tasks) {
  $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  if (-not $task) { continue }
  $info = Get-ScheduledTaskInfo -TaskName $name -ErrorAction SilentlyContinue
  $lstmLockExists = Test-Path $lstmLockPath
  $lstmLockAgeMinutes = $null
  if ($lstmLockExists) {
    try {
      $lstmLockAgeMinutes = [math]::Round(((Get-Date) - (Get-Item $lstmLockPath).LastWriteTime).TotalMinutes, 1)
    } catch {
      $lstmLockAgeMinutes = $null
    }
  }
  $lstmProcCount = Get-LstmJobCount
  $resolved = Resolve-TaskHealth $name $info.LastTaskResult $task.State $gatewayListening $nodeRunning ([pscustomobject]@{ exists = $lstmLockExists; age_minutes = $lstmLockAgeMinutes }) $lstmProcCount
  $out += [pscustomobject]@{
    task = $name
    state = [string]$task.State
    last_result = $info.LastTaskResult
    last_run = $info.LastRunTime
    next_run = $info.NextRunTime
    status = $resolved.status
    status_detail = $resolved.detail
    is_bad = $resolved.is_bad
  }
}

$dashboard = $null
try {
  $dashboard = (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/health -TimeoutSec 5).StatusCode
} catch {
  $dashboard = 'down'
}

[pscustomobject]@{
  checked_at = Get-Date
  gateway_18789 = $gatewayListening
  node_host_running = $nodeRunning
  dashboard_health = $dashboard
  lstm_6h_lock = [pscustomobject]@{
    exists = (Test-Path $lstmLockPath)
    age_minutes = $(if (Test-Path $lstmLockPath) { try { [math]::Round(((Get-Date) - (Get-Item $lstmLockPath).LastWriteTime).TotalMinutes, 1) } catch { $null } } else { $null })
    active_processes = (Get-LstmJobCount)
  }
  tasks = $out
} | ConvertTo-Json -Depth 4
