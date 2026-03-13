$ErrorActionPreference = 'Stop'

$bin = 'https://api.binance.com/api/v3/ticker/24hr'
$all = Invoke-RestMethod -Uri $bin -Headers @{ accept = 'application/json' }

# Basic filters
$stable = @('USDC','USDT','BUSD','TUSD','FDUSD','DAI','USDP','EUR','EURI','TRY','BRL','GBP','AUD','BIDR','IDRT','UAH','RUB')
function Is-StablePair($sym){
  foreach($s in $stable){ if($sym -like "$s*USDT" -or $sym -like "$s*BUSD" -or $sym -like "$s*USDC"){ return $true } }
  return $false
}
function Is-Junk($sym){
  return ($sym -match 'UPUSDT$|DOWNUSDT$|BULLUSDT$|BEARUSDT$')
}

$pairs = $all |
  Where-Object { $_.symbol -like '*USDT' } |
  Where-Object { -not (Is-StablePair $_.symbol) } |
  Where-Object { -not (Is-Junk $_.symbol) } |
  ForEach-Object {
    [pscustomobject]@{
      symbol = $_.symbol
      last = [double]$_.lastPrice
      change24 = [double]$_.priceChangePercent
      qVol24 = [double]$_.quoteVolume
      trades = [int]$_.count
    }
  }

# Top by volume (proxy for "Top 100" that actually matters on Binance)
$topVol = $pairs | Sort-Object qVol24 -Descending | Select-Object -First 100

# Candidate movers from 24h
$movers = $topVol | Where-Object { [math]::Abs($_.change24) -ge 12 } | Sort-Object { [math]::Abs($_.change24) } -Descending | Select-Object -First 25

# Also include absolute top volume names
$focus = @()
$focus += ($movers)
$focus += ($topVol | Select-Object -First 25)
$focus = $focus | Sort-Object symbol -Unique

# For each focus pair: fetch last 2x 1h candles
$rows = @()
foreach($p in $focus){
  $url = "https://api.binance.com/api/v3/klines?symbol=$($p.symbol)&interval=1h&limit=3"
  try {
    $k = Invoke-RestMethod -Uri $url -Headers @{ accept = 'application/json' }
    if($k.Count -ge 3){
      $prev = $k[$k.Count-2]
      $last = $k[$k.Count-1]
      $prevOpen = [double]$prev[1]; $prevClose=[double]$prev[4]; $prevVol=[double]$prev[5]
      $lastOpen = [double]$last[1]; $lastClose=[double]$last[4]; $lastVol=[double]$last[5]
      $chg1h = if($lastOpen -ne 0){ (($lastClose-$lastOpen)/$lastOpen)*100 } else { 0 }
      $volRatio = if($prevVol -gt 0){ $lastVol / $prevVol } else { $null }
      $rows += [pscustomobject]@{
        symbol=$p.symbol
        lastPrice=$p.last
        chg1h=[double]$chg1h
        chg24h=[double]$p.change24
        qVol24=[double]$p.qVol24
        volRatio1h=$volRatio
        prevVol1h=$prevVol
        lastVol1h=$lastVol
      }
    }
  } catch {
    # ignore per-symbol failures
  }
}

# Signals
$extreme1h = $rows | Where-Object { [math]::Abs($_.chg1h) -ge 4 } | Sort-Object { [math]::Abs($_.chg1h) } -Descending
$extreme24 = $rows | Where-Object { [math]::Abs($_.chg24h) -ge 18 } | Sort-Object { [math]::Abs($_.chg24h) } -Descending
$volSpike = $rows | Where-Object { $_.volRatio1h -ne $null -and $_.volRatio1h -ge 3.0 -and $_.qVol24 -ge 15000000 } | Sort-Object volRatio1h -Descending

$payload = [pscustomobject]@{
  timestamp=(Get-Date).ToString('o')
  focusCount=$rows.Count
  extreme1h=($extreme1h | Select-Object -First 12)
  extreme24=($extreme24 | Select-Object -First 12)
  volSpike=($volSpike | Select-Object -First 12)
}

$payload | ConvertTo-Json -Depth 6
