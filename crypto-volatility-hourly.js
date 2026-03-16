const fetch = global.fetch;

const COINGECKO = 'https://api.coingecko.com/api/v3';
const BINANCE = 'https://api.binance.com';

function pct(a, b) { return (a / b - 1) * 100; }
const abs = Math.abs;

async function getJSON(url) {
  const r = await fetch(url, { headers: { accept: 'application/json' } });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`${r.status} ${r.statusText} for ${url}: ${t.slice(0, 200)}`);
  }
  return r.json();
}

(async () => {
  const marketsUrl = `${COINGECKO}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&price_change_percentage=1h,24h&sparkline=false`;
  const top = await getJSON(marketsUrl);

  const exchangeInfo = await getJSON(`${BINANCE}/api/v3/exchangeInfo`);
  const binanceSet = new Set(
    exchangeInfo.symbols
      .filter(s => s.status === 'TRADING' && s.quoteAsset === 'USDT')
      .map(s => s.symbol)
  );

  const candidates = top
    .map(c => ({
      id: c.id,
      name: c.name,
      sym: (c.symbol || '').toUpperCase(),
      mcap: c.market_cap || 0,
      cg_1h: c.price_change_percentage_1h_in_currency,
      cg_24h: c.price_change_percentage_24h_in_currency,
      price: c.current_price,
    }))
    .map(c => ({ ...c, pair: `${c.sym}USDT` }))
    .filter(c => binanceSet.has(c.pair));

  const list = candidates.slice(0, 80);
  const results = [];
  const now = Date.now();

  const chunkSize = 10;
  for (let i = 0; i < list.length; i += chunkSize) {
    const chunk = list.slice(i, i + chunkSize);
    const chunkData = await Promise.all(
      chunk.map(async c => {
        try {
          const kl = await getJSON(`${BINANCE}/api/v3/klines?symbol=${c.pair}&interval=1h&limit=3`);
          if (!Array.isArray(kl) || kl.length < 2) return null;
          const last = kl[kl.length - 2];
          const prev = kl[kl.length - 3] || null;
          const open = +last[1], high = +last[2], low = +last[3], close = +last[4], vol = +last[5];
          const prevVol = prev ? +prev[5] : null;
          const chg = pct(close, open);
          const range = pct(high, low);
          const volRatio = (prevVol && prevVol > 0) ? (vol / prevVol) : null;
          return { ...c, open, close, high, low, vol, prevVol, chg1h: chg, range1h: range, volRatio };
        } catch {
          return null;
        }
      })
    );
    for (const d of chunkData) if (d) results.push(d);
    await new Promise(r => setTimeout(r, 250));
  }

  function thresholds(mcap) {
    if (mcap >= 10e9) return { move: 3, vol: 2.5 };
    if (mcap >= 2e9) return { move: 5, vol: 3 };
    return { move: 8, vol: 4 };
  }

  const alerts = [];
  for (const r of results) {
    const th = thresholds(r.mcap);
    const move = abs(r.chg1h);
    const volRatio = r.volRatio;
    const volHit = volRatio ? (volRatio >= th.vol) : false;
    const moveHit = move >= th.move;
    const wickiness = abs(r.range1h) >= th.move * 2;

    const divergenceVol = volHit && move < th.move * 0.6;
    const divergenceMove = moveHit && (!volRatio || volRatio < 1.5);

    let score = 0;
    score += Math.min(10, (move / th.move) * 4);
    if (volRatio) score += Math.min(10, (volRatio / th.vol) * 4);
    if (wickiness) score += 2;
    if (divergenceVol || divergenceMove) score += 2;

    if (moveHit || volHit) {
      alerts.push({ r, th, move, volRatio, moveHit, volHit, divergenceVol, divergenceMove, wickiness, score });
    }
  }

  alerts.sort((a, b) => b.score - a.score);
  const topAlerts = alerts.slice(0, 8).filter(a => a.score >= 6);

  if (topAlerts.length === 0) {
    console.log('OK');
    return;
  }

  const lines = [];
  lines.push(`ALERTA (Top 100 altcoins, Binance USDT, última vela 1h cerrada) — ${new Date(now).toISOString()}`);
  for (const a of topAlerts) {
    const r = a.r;
    const tags = [];
    if (a.moveHit) tags.push('MOVE');
    if (a.volHit) tags.push('VOLUMEN');
    if (a.divergenceVol) tags.push('VOL↑ sin precio');
    if (a.divergenceMove) tags.push('PRECIO↑/↓ sin vol');
    if (a.wickiness) tags.push('RANGO');

    const vr = (a.volRatio == null) ? 'n/a' : a.volRatio.toFixed(2) + 'x';
    const cg1h = (r.cg_1h == null) ? 'n/a' : r.cg_1h.toFixed(2) + '%';
    const cg24 = (r.cg_24h == null) ? 'n/a' : r.cg_24h.toFixed(2) + '%';

    lines.push(`${r.pair.padEnd(12)} 1h:${r.chg1h.toFixed(2)}%  VolRatio:${vr.padEnd(7)}  CG(1h/24h):${cg1h}/${cg24}  [${tags.join(', ')}]`);
  }
  lines.push('');
  lines.push('Lectura trader:');
  lines.push('- MOVE + VOLUMEN: probable ruptura/continuación; ojo a reversión si viene tras spike fuerte en 24h.');
  lines.push('- VOL↑ sin precio: posible absorción/accum/distrib; esperar confirmación (close por encima/debajo de rango).');

  console.log(lines.join('\n'));
})();
