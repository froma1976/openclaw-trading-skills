$ErrorActionPreference='Stop'
$statePath = Join-Path $env:USERPROFILE '.openclaw\workspace\memory\crypto-volatility-hourly-state.json'
$stateDir = Split-Path $statePath
if(!(Test-Path $stateDir)){
  New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
}
$now = Get-Date

# CoinGecko top 100 (by market cap) - may be rate-limited
$cg = $null
$cgFilt = @()
$cgOk = $false
try {
  $cgUrl = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=1h,24h'
  $cg = Invoke-RestMethod -Uri $cgUrl -Method Get -Headers @{ 'accept'='application/json' }
  $cgOk = $true
} catch {
  $cgOk = $false
}

# Filter out stablecoins
$stableSymbols = @('USDT','USDC','DAI','FDUSD','TUSD','USDE','USDD','LUSD','BUSD','USTC','FRAX','PYUSD','CRVUSD','USDP','EURS')
if($cgOk){
  $cgFilt = $cg | Where-Object { $stableSymbols -notcontains $_.symbol.ToUpper() }
  $symbols = $cgFilt.symbol.ToUpper() | Select-Object -Unique
} else {
  $symbols = @() # will be set later from Binance fallback
}

# Binance tickers 24hr
$bnUrl = 'https://api.binance.com/api/v3/ticker/24hr'
$bn = Invoke-RestMethod -Uri $bnUrl -Method Get -Headers @{ 'accept'='application/json' }

# Only USDT pairs (exclude leveraged tokens)
$bnUsdt = $bn | Where-Object {
  $_.symbol -like '*USDT' -and
  $_.symbol -notlike '*DOWNUSDT' -and $_.symbol -notlike '*UPUSDT' -and
  $_.symbol -notlike '*BULLUSDT' -and $_.symbol -notlike '*BEARUSDT'
}

# Map base asset => ticker
$bnMap = @{}
foreach($t in $bnUsdt){
  $base = $t.symbol.Substring(0, $t.symbol.Length-4)
  if(-not $bnMap.ContainsKey($base)) { $bnMap[$base] = $t }
}

# If CoinGecko failed, approximate "Top 100" using Binance by 24h quote volume (USDT pairs)
if(-not $cgOk){
  $symbols = $bnUsdt |
    ForEach-Object { $_.symbol.Substring(0, $_.symbol.Length-4) } |
    Where-Object { $stableSymbols -notcontains $_ } |
    Group-Object | ForEach-Object { $_.Name } |
    Select-Object -Unique
  # Actually pick top 100 by quoteVolume
  $symbols = $bnUsdt |
    Sort-Object { [double]$_.quoteVolume } -Descending |
    ForEach-Object { $_.symbol.Substring(0, $_.symbol.Length-4) } |
    Where-Object { $stableSymbols -notcontains $_ } |
    Select-Object -First 100 -Unique
}

# Load previous state
$prev = $null
if(Test-Path $statePath){
  try { $prev = Get-Content $statePath -Raw | ConvertFrom-Json } catch { $prev = $null }
}
$prevMap = @{}
if($prev -and $prev.tickers){
  foreach($pt in $prev.tickers){ $prevMap[$pt.base] = $pt }
}

$alerts = @()
foreach($s in $symbols){
  if($s -in @('BTC','ETH')) { continue }
  if(-not $bnMap.ContainsKey($s)) { continue }

  $t = $bnMap[$s]
  $last = [double]$t.lastPrice
  $pct24 = [double]$t.priceChangePercent
  $qv24  = [double]$t.quoteVolume
  $trades = [int]$t.count

  $cgRow = $cgFilt | Where-Object { $_.symbol.ToUpper() -eq $s } | Select-Object -First 1
  $pct1hCg = $null
  if($cgRow -and ($cgRow.PSObject.Properties.Name -contains 'price_change_percentage_1h_in_currency')){
    $pct1hCg = [double]$cgRow.price_change_percentage_1h_in_currency
  }

  $prevT = $null
  if($prevMap.ContainsKey($s)) { $prevT = $prevMap[$s] }

  $deltaQv = $null
  $deltaPct1h = $null
  $qvSpike = $false

  if($prevT){
    $deltaQv = $qv24 - [double]$prevT.qv24
    if([double]$prevT.last -ne 0){
      $deltaPct1h = ( ($last / [double]$prevT.last) - 1.0 ) * 100.0
    }

    # Spike heuristic: 24h rolling quoteVolume jumped a lot in ~1h
    if($qv24 -gt 0 -and $deltaQv -gt 0){
      $deltaShare = $deltaQv / $qv24
      if($deltaShare -ge 0.18 -and $deltaQv -ge 2500000) { $qvSpike = $true }
    }
  }

  $extremeMove = $false
  if($pct1hCg -ne $null -and [math]::Abs($pct1hCg) -ge 6) { $extremeMove = $true }
  if($deltaPct1h -ne $null -and [math]::Abs($deltaPct1h) -ge 5) { $extremeMove = $true }
  if([math]::Abs($pct24) -ge 18) { $extremeMove = $true }

  if($extremeMove -or $qvSpike){
    $reasonParts = @()
    if($extremeMove){ $reasonParts += 'precio' }
    if($qvSpike){ $reasonParts += 'volumen' }

    $alerts += [pscustomobject]@{
      base=$s; pair=$t.symbol; last=$last; pct24=$pct24; pct1hCg=$pct1hCg; pct1hEst=$deltaPct1h;
      qv24=$qv24; deltaQv=$deltaQv; trades=$trades; reason=($reasonParts -join '+')
    }
  }
}

# Save state for next run
$store = @()
foreach($k in $bnMap.Keys){
  $t = $bnMap[$k]
  $store += [pscustomobject]@{ base=$k; last=[double]$t.lastPrice; qv24=[double]$t.quoteVolume; ts=($now.ToString('o')) }
}
@{ ts=$now.ToString('o'); tickers=$store } | ConvertTo-Json -Depth 4 | Set-Content -Path $statePath -Encoding UTF8

# Rank alerts
$ranked = $alerts | ForEach-Object {
  $score = 0.0
  if($_.pct1hCg -ne $null){ $score += [math]::Min(20,[math]::Abs($_.pct1hCg)) }
  if($_.pct1hEst -ne $null){ $score += [math]::Min(20,[math]::Abs($_.pct1hEst)) }
  $score += [math]::Min(25,[math]::Abs($_.pct24)/1.2)
  if($_.deltaQv -ne $null -and $_.qv24 -gt 0){ $score += [math]::Min(25, (($_.deltaQv/$_.qv24)*100)) }
  $_ | Add-Member -NotePropertyName score -NotePropertyValue $score -PassThru
} | Sort-Object score -Descending

if(-not $ranked -or $ranked.Count -eq 0){
  'OK'
  exit 0
}

$top = $ranked | Select-Object -First 8
$lines = @()
$lines += ('ALERTA crypto (Top100 altcoins) - ' + $now.ToString('yyyy-MM-dd HH:mm') + ' Europe/Madrid')
if(-not $cgOk){ $lines += 'Nota: CoinGecko API rate-limited (429). "Top100" aproximado por Binance (top volumen USDT).'}
$lines += 'Senales: movimiento extremo 1h/24h y/o divergencia de volumen (pico vs ultima hora).'
foreach($a in $top){
  $p1 = if($a.pct1hCg -ne $null){ ('CG1h ' + ([math]::Round($a.pct1hCg,2)) + '%') } else { '' }
  $p1e = if($a.pct1hEst -ne $null){ ('~1h ' + ([math]::Round($a.pct1hEst,2)) + '%') } else { '' }
  $dqv = if($a.deltaQv -ne $null){ ('dVol(1h) $' + [math]::Round(($a.deltaQv/1000000),2) + 'M') } else { '' }
  $v24 = ('Vol24h $' + [math]::Round(($a.qv24/1000000),1) + 'M')
  $mid = ((@($p1,$p1e,$dqv,$v24) | Where-Object { $_ -ne '' }) -join ' | ')
  $lines += ('- ' + $a.pair + ' | last ' + $a.last + ' | 24h ' + ([math]::Round($a.pct24,2)) + '% | ' + $mid + ' | motivo: ' + $a.reason)
}
$lines += 'Criterio trader: subida + volumen pico -> posible breakout/continuacion; caida fuerte + volumen -> riesgo de capitulacion/rebote violento. Confirmar con estructura (H1/H4) y niveles.'
$lines -join "`n"
