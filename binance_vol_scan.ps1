$ErrorActionPreference='Stop'

$bn = Invoke-RestMethod 'https://api.binance.com/api/v3/ticker/24hr'

# Keep USDT spot pairs; drop common leveraged suffixes
$exclude = @('UPUSDT','DOWNUSDT','BULLUSDT','BEARUSDT')

$rows = $bn |
  Where-Object { $_.symbol -like '*USDT' -and ($exclude -notcontains $_.symbol) } |
  ForEach-Object {
    [pscustomobject]@{
      sym    = $_.symbol
      chg24h = [double]$_.priceChangePercent
      qvUsdt = [double]$_.quoteVolume
      trades = [int]$_.count
      last   = [double]$_.lastPrice
    }
  }

# High liquidity universe
$liq = $rows | Sort-Object qvUsdt -Descending | Select-Object -First 250

$alerts = @()
# Big upside moves with big volume
$alerts += $liq | Where-Object { $_.qvUsdt -ge 100000000 -and $_.chg24h -ge 20 } | Sort-Object chg24h -Descending | Select-Object -First 5
# Big downside moves with big volume
$alerts += $liq | Where-Object { $_.qvUsdt -ge 100000000 -and $_.chg24h -le -15 } | Sort-Object chg24h | Select-Object -First 5
# Any very high-volume pair with large move
$alerts += $liq | Where-Object { $_.qvUsdt -ge 250000000 -and ([math]::Abs($_.chg24h) -ge 10) } | Sort-Object qvUsdt -Descending | Select-Object -First 5

$alerts = $alerts | Sort-Object qvUsdt -Descending -Unique | Select-Object -First 8

[pscustomobject]@{
  timestamp  = (Get-Date).ToString('s')
  coinGecko  = 'rate_limited_429'
  alerts     = $alerts
  topGainers = ($liq | Sort-Object chg24h -Descending | Select-Object -First 5)
  topLosers  = ($liq | Sort-Object chg24h | Select-Object -First 5)
} | ConvertTo-Json -Depth 4
