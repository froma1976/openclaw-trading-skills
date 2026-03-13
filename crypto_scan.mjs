const CG_URL = 'https://api.coingecko.com/api/v3/coins/markets';
const cgParams = new URLSearchParams({
  vs_currency: 'usd',
  order: 'market_cap_desc',
  per_page: '250',
  page: '1',
  sparkline: 'false',
  price_change_percentage: '1h,24h,7d'
});

const stableSyms = new Set('usdt usdc dai busd tusd fdusd usde usdd ustc pax gusd frax usdp usdn lusd susd eurc eur'.split(' '));
const excludeSyms = new Set(['btc','eth','wbtc','steth']);

function toNum(x){
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

async function jget(url){
  const res = await fetch(url, { headers: { 'accept': 'application/json' } });
  if(!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.json();
}

const coins = await jget(`${CG_URL}?${cgParams.toString()}`);
let alt = [];
for(const c of coins){
  const s = String(c.symbol || '').toLowerCase();
  if(stableSyms.has(s) || excludeSyms.has(s)) continue;
  alt.push(c);
}
alt = alt.slice(0, 100);

let tickers = [];
try{
  tickers = await jget('https://api.binance.com/api/v3/ticker/24hr');
}catch(e){
  tickers = [];
}
const bn = new Map();
for(const t of tickers){
  if(t && t.symbol) bn.set(t.symbol, t);
}

const cands = [];
for(const c of alt){
  const sym = String(c.symbol || '').toUpperCase();
  const bnSym = `${sym}USDT`;
  const t = bn.get(bnSym);

  const mc = toNum(c.market_cap) ?? 0;
  const vol = toNum(c.total_volume) ?? 0;
  const volMc = mc ? (vol/mc) : 0;

  const ch1 = toNum(c.price_change_percentage_1h_in_currency);
  const ch24 = toNum(c.price_change_percentage_24h_in_currency);
  const bnCh24 = t ? toNum(t.priceChangePercent) : null;
  const bnQv = t ? toNum(t.quoteVolume) : null;

  let score = 0;
  const flags = [];

  if(ch1 !== null && Math.abs(ch1) >= 2){ score += 2; flags.push(`1h ${ch1>=0?'+':''}${ch1.toFixed(1)}%`); }

  if(ch24 !== null && Math.abs(ch24) >= 8){ score += 3; flags.push(`24h ${ch24>=0?'+':''}${ch24.toFixed(1)}%`); }
  else if(ch24 !== null && Math.abs(ch24) >= 5){ score += 2; flags.push(`24h ${ch24>=0?'+':''}${ch24.toFixed(1)}%`); }

  if((volMc >= 0.35 && mc > 2e8) || volMc >= 0.60){ score += 2; flags.push(`Vol/MC ${volMc.toFixed(2)}`); }

  if(bnQv !== null && bnQv >= 80_000_000){ score += 2; flags.push(`Binance QV $${Math.round(bnQv/1e6)}M`); }

  if(ch24 !== null && bnCh24 !== null && Math.abs(ch24 - bnCh24) >= 3.5){
    score += 1;
    const d = ch24 - bnCh24;
    flags.push(`Div CG vs BN Δ${d>=0?'+':''}${d.toFixed(1)}pp`);
  }

  if(score >= 4){
    cands.push({
      id: c.id,
      name: c.name,
      sym,
      score,
      ch1, ch24,
      mc,
      volMc,
      bnQv,
      flags
    });
  }
}

cands.sort((a,b)=>{
  const keyA = [-a.score, -(Math.abs(a.ch24 ?? 0)), -(a.bnQv ?? 0), -(a.mc ?? 0)];
  const keyB = [-b.score, -(Math.abs(b.ch24 ?? 0)), -(b.bnQv ?? 0), -(b.mc ?? 0)];
  for(let i=0;i<keyA.length;i++) if(keyA[i]!==keyB[i]) return keyA[i]-keyB[i];
  return 0;
});

console.log(`N_ALT ${alt.length} N_CANDS ${cands.length}`);
for(const x of cands.slice(0, 12)){
  console.log(`${x.sym} ${x.name} score ${x.score} | ${x.flags.join(', ')}`);
}
