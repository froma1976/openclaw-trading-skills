$url = 'http://127.0.0.1:8080/autopilot/run'
$body = @{ threshold = '78'; assigned_to = 'alpha-scout' }

$dashboardUser = $env:DASHBOARD_USER
$dashboardPass = $env:DASHBOARD_PASS

if (([string]::IsNullOrWhiteSpace($dashboardUser) -or [string]::IsNullOrWhiteSpace($dashboardPass)) -and (Test-Path 'C:\Users\Fernando\.openclaw\.env')) {
  Get-Content 'C:\Users\Fernando\.openclaw\.env' | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $parts = $_ -split '=', 2
    $key = $parts[0].Trim()
    $value = $parts[1].Trim()
    if ($key -eq 'DASHBOARD_USER' -and [string]::IsNullOrWhiteSpace($dashboardUser)) { $dashboardUser = $value }
    if ($key -eq 'DASHBOARD_PASS' -and [string]::IsNullOrWhiteSpace($dashboardPass)) { $dashboardPass = $value }
  }
}

if ([string]::IsNullOrWhiteSpace($dashboardUser)) { $dashboardUser = 'admin' }
if ([string]::IsNullOrWhiteSpace($dashboardPass)) { $dashboardPass = 'openclaw2026' }

$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${dashboardUser}:${dashboardPass}"))
$headers = @{ Authorization = "Basic $basic" }

try {
  Invoke-WebRequest -Method Post -Uri $url -Body $body -Headers $headers -UseBasicParsing | Out-Null
  Write-Output "OK autopilot"
} catch {
  Write-Output "ERROR autopilot: $($_.Exception.Message)"
}
