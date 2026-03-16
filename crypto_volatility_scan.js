const fetch = global.fetch;

const COINS = new Set(['bitcoin','ethereum','tether','usd-coin']);

async function j(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    const r = await fetch(url, { headers: { accept: 'application/json' } });
    if (r.ok) return r.json();
    await new Promise(res => setTimeout(res, 350 * (i + 1)));
  }
  throw new Error('Fetch failed: ' + url);
}

function fmtPct(n, d = 2) {
  const sign = n >= 0 ? '+' : '';
  return sign + n.toFixed(d) + '%';
}

(async () => {
  // CoinGecko: pull a bit more than 100 to exclude stables/majors cleanly
  const cgUrl = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=120&page=1&sparkline=false';
  const cgData = await j(cgUrl);
  const alts = cgData.filter(c => !COINS.has(c.id)).slice(0, 100);

  // Binance: list tradable USDT pairs
  const ex = await j('https://api.binance.com/api/v3/exchangeInfo');
  const tradable = new Set(
    ex.symbols
      .filter(s => s.status === 'TRADING' && s.quoteAsset === 'USDT')
      .map(s => s.symbol)
  );

  // Map CoinGecko symbols -> Binance SYMBOLUSDT when available
  const map = [];
  for (const c of alts) {
    const sym = (c.symbol || '').toUpperCase();
    const pair = sym + 'USDT';
    if (tradable.has(pair)) {
      map.push({ id: c.id, name: c.name, symbol: sym, pair, mc_rank: c.market_cap_rank });
    }
  }

  const alerts = [];
  const chunk = 15; // concurrency cap

  for (let i = 0; i < map.length; i += chunk) {
    const batch = map.slice(i, i + chunk);
    await Promise.all(
      batch.map(async (a) => {
        try {
          const [t, k] = await Promise.all([
            j('https://api.binance.com/api/v3/ticker/24hr?symbol=' + a.pair),
            j('https://api.binance.com/api/v3/klines?symbol=' + a.pair + '&interval=1h&limit=24')
          ]);

          const kl = k.map(x => ({
            open: +x[1], high: +x[2], low: +x[3], close: +x[4], vol: +x[5]
          }));
          if (kl.length < 6) return;

          const last = kl[kl.length - 1];
          const prev = kl[kl.length - 2];

          const ret1h = (last.close / prev.close - 1) * 100;
          const range1h = (last.high / last.low - 1) * 100;

          const vols = kl.slice(0, -1).slice(-20).map(x => x.vol);
          const avgVol = vols.reduce((s, v) => s + v, 0) / vols.length;
          const volRatio = avgVol ? (last.vol / avgVol) : 0;

          const ret24 = +t.priceChangePercent;
          const qVol = +t.quoteVolume; // USDT 24h quoted volume
          const price = +t.lastPrice;

          // Heuristic scoring (trader-ish, not a signal):
          const score = Math.abs(ret1h) * 1.2 + Math.max(0, volRatio - 1) * 2 + Math.abs(ret24) * 0.3;

          const extreme = (
            Math.abs(ret1h) > 6 ||
            Math.abs(ret24) > 15 ||
            (volRatio > 4 && Math.abs(ret1h) > 3) ||
            (range1h > 8 && volRatio > 3)
          );

          if (extreme) {
            alerts.push({ pair: a.pair, name: a.name, mc_rank: a.mc_rank, ret1h, range1h, volRatio, ret24, qVol, score, price });
          }
        } catch {
          // ignore per-symbol failures
        }
      })
    );
  }

  alerts.sort((a, b) => b.score - a.score);

  if (alerts.length === 0) {
    console.log('OK');
    return;
  }

  const top = alerts.slice(0, 8);

  console.log('ALERTA CRYPTO (CoinGecko Top100 alts ∩ Binance USDT) — extremos recientes');
  console.log('Filtro: vela 1h violenta y/o volumen 1h x>4 vs media 20h, o 24h >15%.');
  console.log('');

  top.forEach((a, idx) => {
    const v = a.volRatio >= 10 ? a.volRatio.toFixed(1) : a.volRatio.toFixed(2);
    const volUsd = (a.qVol / 1e6) >= 1 ? (a.qVol / 1e6).toFixed(1) + 'M' : (a.qVol / 1e3).toFixed(0) + 'K';

    console.log(`${idx + 1}) ${a.pair} (${a.name}, MC#${a.mc_rank})  price ${a.price}`);
    console.log(`   1h: ${fmtPct(a.ret1h)} | rango 1h: ${a.range1h.toFixed(2)}% | vol 1h: x${v} vs avg20h`);
    console.log(`   24h: ${fmtPct(a.ret24)} | 24h quoteVol aprox: ${volUsd} USDT`);
  });

  console.log('');
  console.log('Lectura rápida (gestión de riesgo):');
  console.log('- Spike alcista con vol x>4: típico pullback/mean reversion; evita perseguir, busca retest (VWAP/prev high).');
  console.log('- Dump con vol x>4: riesgo de continuación; esperar reclaim + estructura antes de long.');
})();
