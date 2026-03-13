$ErrorActionPreference = 'SilentlyContinue'
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupRoot = 'C:\Users\Fernando\.openclaw\workspace\backups\state'
$dest = Join-Path $backupRoot $ts
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$paths = @(
  'C:\Users\Fernando\.openclaw\workspace\agent_activity_registry.db',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\latest_snapshot_free.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\autopilot_log.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\portfolio_usd_sample.json',
  'C:\Users\Fernando\.openclaw\workspace\memory\2026-02-28.md',
  'C:\Users\Fernando\.openclaw\workspace\memory\2026-03-01.md'
)

foreach($p in $paths){
  if(Test-Path $p){
    $name = Split-Path $p -Leaf
    Copy-Item $p (Join-Path $dest $name) -Force
  }
}

# índice rápido
"backup_at=$ts" | Set-Content (Join-Path $dest '_meta.txt')
Write-Output "OK backup $dest"
