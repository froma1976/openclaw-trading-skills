$url = 'http://127.0.0.1:8080/autopilot/run'
$body = @{ threshold = '50'; assigned_to = 'alpha-scout' }
try {
  Invoke-WebRequest -Method Post -Uri $url -Body $body -UseBasicParsing | Out-Null
  Write-Output "OK autopilot"
} catch {
  Write-Output "ERROR autopilot: $($_.Exception.Message)"
}
