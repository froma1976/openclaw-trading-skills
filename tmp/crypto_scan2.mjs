const sleep = ms => new Promise(r=>setTimeout(r,ms));
const headers = { 'accept':'application/json', 'user-agent':'openclaw-volscan/1.0' };

async function fetchJsonRetry(url, {tries=4, baseDelay=1200}={}){
  let lastErr;
  for(let i=0;i<tries;i++){
    try{
      const res = await fetch(url, { headers });
      if(res.status===429){
        const wait = baseDelay * Math.pow(2,i);
        await sleep(wait);
        continue;
      }
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }catch(e){
      lastErr=e;
      await sleep(baseDelay * Math.pow(2,i));
    }
  }
  throw lastErr;
}

function num(x){ const n = Number(x); return Number.isFinite(n)?n:NaN; }
function abs(x){ return Math.abs(x); }

// Binance scan (always)
const b = await fetchJsonRetry('https://api.binance.com/api/v3/ticker/24hr', {tries:3, baseDelay:800});
const tickers = b.filter(t=>t && t.symbol && t.symbol.endsWith('USDT'))
  .map(t=>({
    symbol: t.symbol,
    base: t.symbol.replace('USDT',''),
    ch24: num(t.priceChangePercent),
    quoteVolume: num(t.quoteVolume),
    lastPrice: num(t.lastPrice),
    trades: num(t.count)
  }))
  .filter(t=>Number.isFinite(t.quoteVolume));

const excludeBases = new Set(['BTC','ETH','USDT','USDC','FDUSD','BUSD','DAI','TUSD','USDS','USDE','PAXG','WBTC']);
const alts = tickers.filter(t=>!excludeBases.has(t.base));

alts.sort((a,b)=>b.quoteVolume-a.quoteVolume);
const top100 = alts.slice(0,100);

// Flag extremes
const extreme = top100.filter(x => Number.isFinite(x.ch24) && abs(x.ch24) >= 15);
const highVolLowMove = top100
  .filter(x => abs(x.ch24||0) <= 2)
  .slice(0,20);

// Try CoinGecko (best-effort)
let cgOk=false; let cgTop=null; let cgErr=null;
try{
  const cgUrl = new URL('https://api.coingecko.com/api/v3/coins/markets');
  cgUrl.searchParams.set('vs_currency','usd');
  cgUrl.searchParams.set('order','market_cap_desc');
  cgUrl.searchParams.set('per_page','100');
  cgUrl.searchParams.set('page','1');
  cgUrl.searchParams.set('sparkline','false');
  cgUrl.searchParams.set('price_change_percentage','1h,24h');
  const cg = await fetchJsonRetry(cgUrl.toString(), {tries:4, baseDelay:1500});
  cgTop = cg;
  cgOk=true;
}catch(e){
  cgErr = String(e && e.message ? e.message : e);
}

const out = {
  coinGecko: cgOk ? { ok:true, count: cgTop.length } : { ok:false, error: cgErr },
  binance: { ok:true, top100Count: top100.length },
  extremes: extreme.sort((a,b)=>abs(b.ch24)-abs(a.ch24)).slice(0,12),
  highVolLowMove: highVolLowMove.map(x=>({symbol:x.symbol, ch24:x.ch24, quoteVolume:x.quoteVolume}))
};

console.log(JSON.stringify(out,null,2));
