$t = Invoke-RestMethod -Uri 'https://api.binance.com/api/v3/ticker/24hr' -TimeoutSec 20

$usdt = $t |
  Where-Object { $_.symbol -match 'USDT$' -and [int]$_.count -gt 1000 } |
  ForEach-Object {
    [pscustomobject]@{
      sym    = $_.symbol
      pc     = [double]$_.priceChangePercent
      qv     = [double]$_.quoteVolume
      trades = [int]$_.count
    }
  }

$top = $usdt |
  Where-Object { $_.qv -gt 50000000 } |
  Sort-Object { [math]::Abs($_.pc) } -Descending |
  Select-Object -First 10

$top | ForEach-Object {
  '{0} 24h={1:N2}% qVol=${2:N0} trades={3}' -f $_.sym, $_.pc, $_.qv, $_.trades
}
