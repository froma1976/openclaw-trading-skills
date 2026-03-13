$ErrorActionPreference='Stop'

# 1) CoinGecko top coins
$cgUrl = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=120&page=1&sparkline=false&price_change_percentage=1h,24h'
$cg = Invoke-RestMethod -Uri $cgUrl -Headers @{ accept = 'application/json' }

# Keep top 100 altcoins (rough filter: exclude BTC/ETH + common stables)
$excludeSyms = @('btc','eth','usdt','usdc','dai','tusd','fdusd','busd','usde','usdd','lusd','frax','pyusd','usdp')
$coins = $cg | Where-Object { $excludeSyms -notcontains $_.symbol } | Select-Object -First 100

# 2) Binance 24hr tickers (all symbols)
$bnUrl = 'https://api.binance.com/api/v3/ticker/24hr'
$bn = Invoke-RestMethod -Uri $bnUrl -Headers @{ accept = 'application/json' }

$bnMap = @{}
foreach ($t in $bn) {
  if ($t.symbol) { $bnMap[$t.symbol] = $t }
}

# 3) Join + score heuristics
$rows = @()
foreach ($c in $coins) {
  $sym  = ($c.symbol).ToUpperInvariant()
  $pair = $sym + 'USDT'
  $t = $null
  if ($bnMap.ContainsKey($pair)) { $t = $bnMap[$pair] }

  $cg1h = [double]($c.price_change_percentage_1h_in_currency)
  if ([double]::IsNaN($cg1h)) { $cg1h = 0 }
  $cg24 = [double]($c.price_change_percentage_24h_in_currency)
  if ([double]::IsNaN($cg24)) { $cg24 = 0 }

  $vol  = [double]($c.total_volume)
  $mcap = [double]($c.market_cap)
  $volMcap = if ($mcap -gt 0) { $vol / $mcap } else { 0 }

  $bn24 = $null; $bnVol = $null
  if ($t) {
    $bn24  = [double]($t.priceChangePercent)
    $bnVol = [double]($t.quoteVolume)  # in quote asset (USDT)
  }

  $div = if ($t) { [math]::Abs($bn24 - $cg24) } else { 0 }
  $volDiv = if ($t -and $vol -gt 0) { ($bnVol / $vol) } else { 0 }

  # scoring heuristic
  $score = 0
  $score += [math]::Min(30, [math]::Abs($cg1h) * 3)
  $score += [math]::Min(30, [math]::Abs($cg24))
  $score += [math]::Min(20, $volMcap * 50)
  if ($t) { $score += [math]::Min(10, $div * 1.5) }
  if ($t -and ($volDiv -gt 2 -or $volDiv -lt 0.5)) { $score += 8 }

  $rows += [pscustomobject]@{
    name       = $c.name
    sym        = $sym
    mcapRank   = $c.market_cap_rank
    price      = [double]$c.current_price
    cg1h       = $cg1h
    cg24h      = $cg24
    vol        = $vol
    mcap       = $mcap
    volMcap    = $volMcap
    bnPair     = if ($t) { $pair } else { $null }
    bn24h      = $bn24
    bnQuoteVol = $bnVol
    bnCgDiv    = $div
    bnVolVsCg  = $volDiv
    score      = $score
  }
}

# 4) Thresholds for alerting
$alerts = $rows | Where-Object {
  ([math]::Abs($_.cg1h) -ge 6) -or
  (([math]::Abs($_.cg24h) -ge 18) -and ($_.vol -ge 50000000)) -or
  (($_.volMcap -ge 0.45) -and ($_.vol -ge 80000000)) -or
  (($_.bnPair) -and ($_.bnCgDiv -ge 10) -and ($_.bnQuoteVol -ge 50000000))
} | Sort-Object score -Descending | Select-Object -First 8

$top = $rows | Sort-Object score -Descending | Select-Object -First 12

[pscustomobject]@{
  timestamp = (Get-Date).ToString('s')
  alerts    = $alerts
  top       = $top
} | ConvertTo-Json -Depth 5
