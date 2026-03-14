$ErrorActionPreference = 'Continue'

$ollamaExe = 'C:\Users\Fernando\AppData\Local\Programs\Ollama\ollama.exe'
$log = 'C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\data\ensure_ollama.log'

"[$(Get-Date -Format s)] ensure_ollama start" | Add-Content $log

try {
  $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 3
  if ($r.StatusCode -eq 200) {
    "[$(Get-Date -Format s)] ollama already healthy" | Add-Content $log
    exit 0
  }
} catch {}

Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden
Start-Sleep -Seconds 4

try {
  $r2 = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 6
  if ($r2.StatusCode -eq 200) {
    "[$(Get-Date -Format s)] ollama recovered" | Add-Content $log
    exit 0
  }
} catch {}

"[$(Get-Date -Format s)] ollama recovery failed" | Add-Content $log
exit 1
