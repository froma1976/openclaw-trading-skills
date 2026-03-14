$ErrorActionPreference='Stop'

$cgUrl='https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false'
$coins=Invoke-RestMethod -Uri $cgUrl -Headers @{accept='application/json'}

$ex=Invoke-RestMethod -Uri 'https://api.binance.com/api/v3/exchangeInfo' -Headers @{accept='application/json'}
$binanceSyms=New-Object 'System.Collections.Generic.HashSet[string]'
foreach($s in $ex.symbols){
  if($s.status -eq 'TRADING' -and $s.quoteAsset -eq 'USDT'){
    [void]$binanceSyms.Add($s.symbol)
  }
}

$top=@()
foreach($c in $coins){
  $sym=($c.symbol).ToUpper()
  $pair=($sym+'USDT')
  if($binanceSyms.Contains($pair)){
    $top += [pscustomobject]@{ id=$c.id; symbol=$sym; name=$c.name; pair=$pair; mc_rank=$c.market_cap_rank }
  }
}

function Get-Json([string]$u){
  try { Invoke-RestMethod -Uri $u -Headers @{accept='application/json'} -TimeoutSec 20 }
  catch { $null }
}

$tickers=Get-Json 'https://api.binance.com/api/v3/ticker/24hr'
$tickerMap=@{}
foreach($t in $tickers){ $tickerMap[$t.symbol]=$t }

$alerts=@()
foreach($c in $top){
  $t=$tickerMap[$c.pair]
  if(-not $t){ continue }

  $last=[double]$t.lastPrice
  $high=[double]$t.highPrice
  $low=[double]$t.lowPrice
  $chg24=[double]$t.priceChangePercent
  $quoteVol=[double]$t.quoteVolume
  $trades=[int]$t.count

  $kUrl=('https://api.binance.com/api/v3/klines?symbol='+$c.pair+'&interval=1h&limit=3')
  $k=Get-Json $kUrl
  if($k -and $k.Count -ge 3){
    # Use previous closed 1h candle vs its previous
    $prev=$k[1]; $prev2=$k[0]

    $o=[double]$prev[1];  $cl=[double]$prev[4]
    $o2=[double]$prev2[1]; $cl2=[double]$prev2[4]
    $v=[double]$prev[5];  $v2=[double]$prev2[5]

    $chg1h = if($o -ne 0){ (($cl-$o)/$o)*100 } else { 0 }
    $chgPrev1h = if($o2 -ne 0){ (($cl2-$o2)/$o2)*100 } else { 0 }
    $volRatio = if($v2 -gt 0){ $v/$v2 } else { 999 }

    # Heuristics
    $isExtreme = ([math]::Abs($chg1h) -ge 4) -or ([math]::Abs($chg24) -ge 12)
    $isVolSpike = ($volRatio -ge 3 -and [math]::Abs($chg1h) -ge 1.5)
    $isDivergence = ($volRatio -ge 4 -and [math]::Abs($chg1h) -lt 1.2)

    if($isExtreme -or $isVolSpike -or $isDivergence){
      $kind = if($isExtreme){ 'MOV' } elseif($isVolSpike){ 'VOL+MOV' } else { 'VOL-DIV' }
      $alerts += [pscustomobject]@{
        rank=$c.mc_rank; pair=$c.pair; name=$c.name; kind=$kind;
        last=[math]::Round($last,8);
        chg1h=[math]::Round($chg1h,2); chg24=[math]::Round($chg24,2);
        volRatio=[math]::Round($volRatio,2);
        high=[math]::Round($high,8); low=[math]::Round($low,8);
        qVol24=[math]::Round($quoteVol/1000000,1);
        trades=$trades;
        prev1h=[math]::Round($chgPrev1h,2)
      }
    }
  }
}

$alerts=$alerts | Sort-Object -Property @{Expression={[math]::Abs($_.chg1h)};Descending=$true}, @{Expression={$_.volRatio};Descending=$true} | Select-Object -First 12

if(-not $alerts -or $alerts.Count -eq 0){
  'OK'
  exit 0
}

$now=Get-Date
'CRYPTO VOL ALERT — ' + $now.ToString('yyyy-MM-dd HH:mm') + ' Europe/Madrid'
'Señales (Top100 CoinGecko + Binance USDT):'
foreach($a in $alerts){
  '- ['+$a.kind+'] '+$a.pair+' ('+$a.name+' #'+$a.rank+'): px '+$a.last+' | 1h '+$a.chg1h+'% | 24h '+$a.chg24+'% | vol x'+$a.volRatio+' | 24h range ['+$a.low+' - '+$a.high+'] | qVol ~'+$a.qVol24+'M | trades '+$a.trades
}
