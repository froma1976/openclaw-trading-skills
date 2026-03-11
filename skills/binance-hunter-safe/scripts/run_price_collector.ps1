$ErrorActionPreference = 'Stop'

$node = "C:\Program Files\nodejs\node.exe"
$script = "C:\Users\Fernando\.openclaw\workspace\skills\binance-hunter-safe\scripts\price_collector.mjs"

if (-not (Test-Path $node)) {
  throw "No se encontro node.exe en $node"
}

if (-not (Test-Path $script)) {
  throw "No se encontro el script en $script"
}

& $node $script
