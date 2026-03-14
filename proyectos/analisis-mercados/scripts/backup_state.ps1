$ErrorActionPreference = 'SilentlyContinue'
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupRoot = 'C:\Users\Fernando\.openclaw\workspace\backups\state'
$dest = Join-Path $backupRoot $ts
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$paths = @(
  'C:\Users\Fernando\.openclaw\workspace\agent_activity_registry.db',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\latest_snapshot_free.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\autopilot_log.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\crypto_orders_sim.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\crypto_snapshot_free.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\trade_edge_model.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\universe_status.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\learning_status.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\market_regime.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\models\registry.json',
  'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\config\risk.yaml'
)

foreach($p in $paths){
  if(Test-Path $p){
    $name = Split-Path $p -Leaf
    Copy-Item $p (Join-Path $dest $name) -Force
  }
}

# indice rapido
"backup_at=$ts" | Set-Content (Join-Path $dest '_meta.txt')
Write-Output "OK backup $dest"

# --- RETENTION: eliminar backups con mas de 14 dias ---
$maxAgeDays = 14
$cutoff = (Get-Date).AddDays(-$maxAgeDays)
$allBackups = Get-ChildItem -Path $backupRoot -Directory -ErrorAction SilentlyContinue
$removed = 0
foreach($dir in $allBackups) {
    if($dir.CreationTime -lt $cutoff) {
        try {
            Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction Stop
            $removed++
        } catch {
            # silently skip if unable to delete
        }
    }
}
if($removed -gt 0) {
    Write-Output "PRUNED $removed backups older than $maxAgeDays days"
}

# --- KEEP at most 30 backups (safety cap) ---
$maxBackups = 30
$allBackups = Get-ChildItem -Path $backupRoot -Directory -ErrorAction SilentlyContinue | Sort-Object CreationTime -Descending
if($allBackups.Count -gt $maxBackups) {
    $toRemove = $allBackups | Select-Object -Skip $maxBackups
    foreach($dir in $toRemove) {
        try {
            Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction Stop
            $removed++
        } catch {}
    }
    Write-Output "CAPPED to $maxBackups backups (removed excess)"
}
