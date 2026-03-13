const fetch = global.fetch;

const cgUrl = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=120&page=1&sparkline=false&price_change_percentage=1h,24h';
const stable = new Set([
  'tether','usd-coin','dai','true-usd','frax','paypal-usd','first-digital-usd','usdd','usde','tusd'
]);

function sleep(ms){ return new Promise(r=>setTimeout(r, ms)); }
function pct(a,b){ return (b-a)/a*100; }

(async () => {
  const cg = await (await fetch(cgUrl, { headers: { accept: 'application/json' } })).json();
  const top = cg
    .filter(x => !stable.has(x.id) && !['bitcoin','ethereum'].includes(x.id))
    .slice(0, 100);

  const tickers = await (await fetch('https://api.binance.com/api/v3/ticker/24hr')).json();
  const tmap = new Map(tickers.map(t => [t.symbol, t]));

  const candidates = [];

  for (const c of top) {
    const base = c.symbol.toUpperCase();
    const sym = base + 'USDT';
    if (!tmap.has(sym)) continue;

    const t = tmap.get(sym);
    const change24 = parseFloat(t.priceChangePercent);
    const quoteVol = parseFloat(t.quoteVolume);
    const ch1h = c.price_change_percentage_1h_in_currency;

    // Preselect to reduce API calls
    const preselect = Math.abs(change24) > 6 || quoteVol > 50_000_000 || (typeof ch1h === 'number' && Math.abs(ch1h) > 2);
    if (!preselect) continue;

    await sleep(70);
    const kUrl = `https://api.binance.com/api/v3/klines?symbol=${sym}&interval=1m&limit=120`;
    const kl = await (await fetch(kUrl)).json();
    if (!Array.isArray(kl) || kl.length < 60) continue;

    const closes = kl.map(r => parseFloat(r[4]));
    const vols   = kl.map(r => parseFloat(r[5]));

    const lastPx = closes[closes.length - 1];
    const px15a  = closes[closes.length - 16];
    const move15 = pct(px15a, lastPx);

    const sum = arr => arr.reduce((a,b)=>a+b, 0);
    const vLast30 = sum(vols.slice(-30));
    const vPrev30 = sum(vols.slice(-60, -30));
    const vRatio30 = vPrev30 > 0 ? vLast30 / vPrev30 : null;

    const vLast10 = sum(vols.slice(-10));
    const vPrev10 = sum(vols.slice(-20, -10));
    const vRatio10 = vPrev10 > 0 ? vLast10 / vPrev10 : null;

    const last = kl[kl.length - 1];
    const h = parseFloat(last[2]), l = parseFloat(last[3]), clp = parseFloat(last[4]);
    const rangePct = (h - l) / clp * 100;

    let score = 0;
    if (Math.abs(move15) >= 3) score += 3;
    if (vRatio30 && vRatio30 >= 3) score += 3;
    if (vRatio10 && vRatio10 >= 4) score += 2;
    if (rangePct >= 1.5) score += 1;

    if (score >= 4) {
      candidates.push({ sym, move15, vRatio30, vRatio10, rangePct, change24, quoteVol });
    }
  }

  candidates.sort((a,b) => {
    const av = a.vRatio30 || 1;
    const bv = b.vRatio30 || 1;
    return (Math.abs(b.move15) + Math.log(bv)) - (Math.abs(a.move15) + Math.log(av));
  });

  if (candidates.length === 0) {
    console.log('OK');
    return;
  }

  console.log('ALERTA CRYPTO (últimos ~15-30 min, Binance spot USDT)');
  for (const x of candidates.slice(0, 8)) {
    const dir = x.move15 >= 0 ? '↑' : '↓';
    const vr30 = x.vRatio30 ? x.vRatio30.toFixed(2) + 'x' : 'n/a';
    const vr10 = x.vRatio10 ? x.vRatio10.toFixed(2) + 'x' : 'n/a';
    const qv = x.quoteVol >= 1e9 ? (x.quoteVol/1e9).toFixed(2)+'B'
             : x.quoteVol >= 1e6 ? (x.quoteVol/1e6).toFixed(1)+'M'
             : x.quoteVol.toFixed(0);

    console.log(`- ${x.sym}: ${dir}${x.move15.toFixed(2)}%/15m | Vol 30m ${vr30} (10m ${vr10}) | rango 1m ${x.rangePct.toFixed(2)}% | 24h ${x.change24.toFixed(2)}% | QVol24h ${qv} USDT`);
  }

  console.log('\nCriterio trader (rápido):');
  console.log('- Subida con Vol>=3x: posible continuación; esperar pullback (VWAP/EMA) + stop corto.');
  console.log('- Movimiento fuerte con Vol bajo: más probable fakeout/stop-hunt.');
  console.log('- Caída con Vol alto: riesgo de cascada; evitar longs hasta base clara.');
})().catch(e => {
  console.error('OK');
});
