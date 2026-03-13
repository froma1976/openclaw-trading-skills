const base='https://api.binance.com';

async function j(url){
  const r=await fetch(url,{headers:{'accept':'application/json'}});
  if(!r.ok) throw new Error(`HTTP ${r.status} ${url}`);
  return r.json();
}

// 24h tickers
const tickers = await j(`${base}/api/v3/ticker/24hr`);
// keep USDT spot pairs (exclude stable-stable, leveraged tokens heuristically)
const bad = new Set(['BUSDUSDT','USDCUSDT','TUSDUSDT','FDUSDUSDT','USDPUSDT','DAIUSDT','EURUSDT','TRYUSDT']);
const filtered = tickers
  .filter(t => t.symbol.endsWith('USDT') && !bad.has(t.symbol))
  .filter(t => !t.symbol.includes('UPUSDT') && !t.symbol.includes('DOWNUSDT') && !t.symbol.includes('BULLUSDT') && !t.symbol.includes('BEARUSDT'))
  .map(t => ({
    symbol: t.symbol,
    lastPrice: Number(t.lastPrice),
    priceChangePercent: Number(t.priceChangePercent),
    quoteVolume: Number(t.quoteVolume),
    volume: Number(t.volume),
    count: Number(t.count)
  }))
  .filter(t => Number.isFinite(t.quoteVolume) && t.quoteVolume>0 && Number.isFinite(t.priceChangePercent));

filtered.sort((a,b)=>b.quoteVolume-a.quoteVolume);
const top100 = filtered.slice(0,100);

function topMoves(arr, n, asc=false){
  const a=[...arr].sort((x,y)=> asc ? x.priceChangePercent-y.priceChangePercent : y.priceChangePercent-x.priceChangePercent);
  return a.slice(0,n);
}

const topUp = topMoves(top100, 12, false);
const topDn = topMoves(top100, 12, true);

async function volSpike(symbol){
  // last 3 1h candles: [t-2h, t-1h, t] (t = last closed?)
  const kl = await j(`${base}/api/v3/klines?symbol=${symbol}&interval=1h&limit=4`);
  // each kline: [openTime, open, high, low, close, volume, closeTime, quoteAssetVolume, trades, ...]
  const vols = kl.map(k => Number(k[7])); // quoteAssetVolume
  // Compare last completed hour vs average of previous 3
  if (vols.length<4) return null;
  const last = vols[vols.length-2];
  const prev = vols.slice(0,vols.length-2);
  const avg = prev.reduce((s,v)=>s+v,0)/prev.length;
  const ratio = avg>0 ? last/avg : null;
  return { ratio, lastQuoteVol:last, avgPrev:avg };
}

// focus: large move + high liquidity
const candidates = [...new Set([
  ...topUp.slice(0,6).map(x=>x.symbol),
  ...topDn.slice(0,6).map(x=>x.symbol)
])];

const spikes=[];
for (const s of candidates){
  try{
    const sp = await volSpike(s);
    if (sp && Number.isFinite(sp.ratio)) spikes.push({symbol:s, ...sp});
  }catch(e){
    // ignore per-symbol errors
  }
}

spikes.sort((a,b)=>b.ratio-a.ratio);

console.log(JSON.stringify({
  top100ByQuoteVol: top100.slice(0,10),
  topUp, topDn,
  spikes
}, null, 2));
