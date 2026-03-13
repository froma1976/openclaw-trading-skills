$ErrorActionPreference='Stop'

# CoinGecko Top 100 by market cap
$cgUrl = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=1h%2C24h%2C7d'
$coins = Invoke-RestMethod -Uri $cgUrl -TimeoutSec 30

$cg = $coins | ForEach-Object {
  $mc  = if ($null -ne $_.market_cap)   { [double]$_.market_cap }   else { 0 }
  $vol = if ($null -ne $_.total_volume) { [double]$_.total_volume } else { 0 }

  $pc1  = $_.price_change_percentage_1h_in_currency
  $pc24 = $_.price_change_percentage_24h_in_currency
  $pc7  = $_.price_change_percentage_7d_in_currency

  $vr = if ($mc -gt 0) { $vol / $mc } else { 0 }

  $score = 0
  if ($pc1  -ne $null) { $score += [math]::Min(10, [math]::Abs([double]$pc1)  / 2) }
  if ($pc24 -ne $null) { $score += [math]::Min(10, [math]::Abs([double]$pc24) / 5) }
  $score += [math]::Min(10, $vr * 50)  # vol=0.20*mcap => 10 pts

  [pscustomobject]@{
    score = $score
    vr    = $vr
    pc1   = $pc1
    pc24  = $pc24
    pc7   = $pc7
    sym   = ($_.symbol.ToUpper())
    name  = $_.name
    mc    = $mc
    vol   = $vol
  }
} | Sort-Object score -Descending

'COINGECKO_TOP_ANOMALIES'
$cg | Select-Object -First 20 | ForEach-Object {
  "$($_.name) ($($_.sym)) score=$([math]::Round($_.score,2)) vol/mcap=$([math]::Round($_.vr,3)) 1h=$($_.pc1) 24h=$($_.pc24) 7d=$($_.pc7)"
}

# Binance 24h tickers
$bnUrl   = 'https://api.binance.com/api/v3/ticker/24hr'
$tickers = Invoke-RestMethod -Uri $bnUrl -TimeoutSec 30

$bn = $tickers |
  Where-Object { $_.symbol -like '*USDT' } |
  ForEach-Object {
    $p  = [double]$_.priceChangePercent
    $qv = [double]$_.quoteVolume
    $tr = [double]$_.count
    [pscustomobject]@{ absP=[math]::Abs($p); p=$p; qv=$qv; sym=$_.symbol; tr=$tr }
  } |
  Sort-Object -Property @{Expression='absP';Descending=$true}, @{Expression='qv';Descending=$true}

''
'BINANCE_USDT_TOP_ABS_MOVE'
$bn | Select-Object -First 25 | ForEach-Object {
  "$($_.sym) 24h%=$([math]::Round($_.p,2)) quoteVol=$([math]::Round($_.qv,0)) trades=$([math]::Round($_.tr,0))"
}
