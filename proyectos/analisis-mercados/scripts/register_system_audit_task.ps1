$ErrorActionPreference = 'Stop'

$taskName = 'OpenClaw-System-Audit-6h'
$taskCmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\scripts\run_system_audit_hidden.ps1"'

schtasks /Create /TN $taskName /SC HOURLY /MO 6 /TR $taskCmd /F | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State | ConvertTo-Json -Depth 2
