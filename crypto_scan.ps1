$ErrorActionPreference = 'Stop'

$cgUri = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=1h%2C24h'
$cg = Invoke-RestMethod -Uri $cgUri -TimeoutSec 30

$bnAll = Invoke-RestMethod -Uri 'https://api.binance.com/api/v3/ticker/24hr' -TimeoutSec 30
$bn = @{}
foreach ($t in $bnAll) {
  if ($null -ne $t.symbol -and $t.symbol -ne '') {
    $bn[$t.symbol] = $t
  }
}

function Get-Candidates([string]$sym) {
  $s = $sym.ToUpper()
  $map = @{
    'MATIC' = 'POLUSDT'
    'POL'   = 'POLUSDT'
    'TON'   = 'TONUSDT'
  }
  if ($map.ContainsKey($s)) { return @($map[$s]) }
  return @($s + 'USDT', $s + 'BUSD', $s + 'USDC')
}

$rows = @()
foreach ($c in $cg) {
  $sym  = ($c.symbol).ToUpper()
  $name = $c.name

  $mcap = [double]($c.market_cap)
  if (-not $mcap) { $mcap = 0 }
  $vol = [double]($c.total_volume)
  if (-not $vol) { $vol = 0 }

  $p1h = $c.price_change_percentage_1h_in_currency
  $p24 = $c.price_change_percentage_24h_in_currency

  $pair = $null
  $t = $null
  foreach ($cand in (Get-Candidates $c.symbol)) {
    if ($bn.ContainsKey($cand)) { $pair = $cand; $t = $bn[$cand]; break }
  }

  $bnP24 = $null
  if ($t) {
    try { $bnP24 = [double]$t.priceChangePercent } catch { }
  }

  $volMcap = 0
  if ($mcap -gt 0) { $volMcap = $vol / $mcap }

  $score = 0
  if ($p24 -ne $null) {
    $score += [math]::Min(20, [math]::Abs([double]$p24)) * 1.5
  } elseif ($bnP24 -ne $null) {
    $score += [math]::Min(20, [math]::Abs($bnP24)) * 1.4
  }
  if ($p1h -ne $null) {
    $score += [math]::Min(10, [math]::Abs([double]$p1h)) * 1.8
  }
  $score += [math]::Min(50, $volMcap * 100) * 0.6

  $flags = @()
  if ($p24 -ne $null -and [math]::Abs([double]$p24) -ge 12) {
    $flags += ('24h {0}{1:N1}%' -f ($(if ([double]$p24 -ge 0) { '+' } else { '' }), [double]$p24))
  } elseif ($bnP24 -ne $null -and [math]::Abs($bnP24) -ge 12) {
    $flags += ('24h(BN) {0}{1:N1}%' -f ($(if ($bnP24 -ge 0) { '+' } else { '' }), $bnP24))
  }
  if ($p1h -ne $null -and [math]::Abs([double]$p1h) -ge 3.5) {
    $flags += ('1h {0}{1:N1}%' -f ($(if ([double]$p1h -ge 0) { '+' } else { '' }), [double]$p1h))
  }
  if ($volMcap -ge 0.35) {
    $flags += ('Vol/MCap {0:N2}' -f $volMcap)
  }

  if ($flags.Count -gt 0 -and $score -ge 25) {
    $rows += [pscustomobject]@{
      sym     = $sym
      name    = $name
      pair    = $pair
      p1h     = $p1h
      p24     = $p24
      bnP24   = $bnP24
      volMcap = $volMcap
      score   = $score
      flags   = ($flags -join ', ')
    }
  }
}

$rows = $rows | Sort-Object score -Descending
if (-not $rows -or $rows.Count -eq 0) {
  Write-Output 'OK'
  exit 0
}

Write-Output 'ALERTA: movimientos/extremos (Top100 altcoins) detectados en la última hora/24h (CoinGecko + Binance, best-effort).'
$top = $rows | Select-Object -First 10
foreach ($r in $top) {
  $p24x = $(if ($r.p24 -ne $null) { [double]$r.p24 } else { $r.bnP24 })
  $line = '- {0} ({1})' -f $r.sym, $r.name
  if ($r.pair) { $line += ' [' + $r.pair + ']' }
  if ($r.p1h -ne $null) { $line += (' | 1h {0}{1:N1}%' -f ($(if ([double]$r.p1h -ge 0) { '+' } else { '' }), [double]$r.p1h)) }
  if ($p24x -ne $null) { $line += (' | 24h {0}{1:N1}%' -f ($(if ($p24x -ge 0) { '+' } else { '' }), $p24x)) }
  $line += (' | Vol/MCap {0:N2}' -f $r.volMcap)
  $line += ' | Señales: ' + $r.flags
  Write-Output $line
}

Write-Output ''
Write-Output 'Lectura rápida (criterio trader):'
Write-Output '- Subidas fuertes + Vol/MCap alto => posible breakout/squeeze; ojo fakeout si la vela 1h está demasiado vertical.'
Write-Output '- Caídas fuertes + Vol/MCap alto => posible capitulación; mejor esperar confirmación (estructura + pérdida de momentum) antes de comprar.'
