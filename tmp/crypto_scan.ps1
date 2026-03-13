$ErrorActionPreference='Stop'

$cg = Invoke-RestMethod -Uri 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=1h,24h,7d'
$bn = Invoke-RestMethod -Uri 'https://api.binance.com/api/v3/ticker/24hr'

$bnUSDT = $bn | Where-Object { $_.symbol -like '*USDT' -and $_.symbol -notlike '*BUSDUSDT' -and $_.symbol -notlike '*USDCUSDT' -and $_.symbol -notlike '*TUSDUSDT' }

# group by base
$bnByBase = @{}
foreach($t in $bnUSDT){
  $base = $t.symbol.Substring(0, $t.symbol.Length-4)
  if(-not $bnByBase.ContainsKey($base)) { $bnByBase[$base] = @() }
  $bnByBase[$base] += $t
}

function ToDouble($x){
  try { return [double]$x } catch { return $null }
}

$rows=@(); $vols=@()
foreach($c in $cg){
  $sym = ($c.symbol).ToUpper()
  if($sym -in @('BTC','ETH')){ continue }
  if(-not $bnByBase.ContainsKey($sym)) { continue }
  $best = $bnByBase[$sym] | Sort-Object { ToDouble($_.quoteVolume) } -Descending | Select-Object -First 1
  $qv = ToDouble($best.quoteVolume)
  if($qv) { $rows += ,@($c,$best,$qv); $vols += $qv }
}

$alerts=@()
if($vols.Count -gt 0){
  $volsSorted = $vols | Sort-Object
  $med = $volsSorted[[int]($volsSorted.Count/2)]
  $absDev = $vols | ForEach-Object { [math]::Abs($_-$med) } | Sort-Object
  $mad = $absDev[[int]($absDev.Count/2)]
  if(-not $mad){ $mad = 1.0 }

  foreach($r in $rows){
    $c=$r[0]; $best=$r[1]; $qv=[double]$r[2]
    $sym=($c.symbol).ToUpper()
    $p1h = ToDouble($c.price_change_percentage_1h_in_currency)
    $p24h = ToDouble($c.price_change_percentage_24h_in_currency)
    $reason=@(); $extreme=$false

    if($p1h -ne $null -and [math]::Abs($p1h) -ge 6){ $extreme=$true; $reason += ('1h {0:+0.0;-0.0;0.0}%' -f $p1h) }
    if($p24h -ne $null -and [math]::Abs($p24h) -ge 20){ $extreme=$true; $reason += ('24h {0:+0.0;-0.0;0.0}%' -f $p24h) }

    $robustZ = 0.6745*($qv-$med)/$mad
    $volMult = if($med -ne 0){ $qv/$med } else { $null }
    $volFlag = ([math]::Abs($robustZ) -ge 3.5) -or ($volMult -ne $null -and $volMult -ge 4)
    if($volFlag){ $reason += ('vol {0}M USDT (~{1}x med)' -f ([math]::Round($qv/1e6)), ([math]::Round($volMult,1))) }

    $score = if($extreme -and $volFlag){3} elseif($extreme -or $volFlag){2} else {0}
    if($score -ge 2){
      $alerts += [pscustomobject]@{
        sym=$sym; name=$c.name; rank=$c.market_cap_rank; price=$c.current_price;
        p1h=$p1h; p24h=$p24h;
        bn_symbol=$best.symbol; bn_p24=ToDouble($best.priceChangePercent);
        qv=$qv; reasons=($reason -join ', '); score=$score
      }
    }
  }
}

$alerts = $alerts | Sort-Object score,qv -Descending

# Output as JSON-ish lines for caller
[pscustomobject]@{
  generatedAt = (Get-Date).ToString('s')
  alerts = $alerts
  medQuoteVolume = $med
  count = $alerts.Count
} | ConvertTo-Json -Depth 4
