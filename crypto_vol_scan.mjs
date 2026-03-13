const CG='https://api.coingecko.com/api/v3';
const BN='https://api.binance.com';

const sleep = (ms)=>new Promise(r=>setTimeout(r,ms));

async function getJson(url, params){
  const u=new URL(url);
  if(params) Object.entries(params).forEach(([k,v])=>u.searchParams.set(k,String(v)));
  const res=await fetch(u, {headers:{'accept':'application/json'}});
  if(!res.ok) throw new Error(`HTTP ${res.status} ${url}`);
  return res.json();
}

const params={vs_currency:'usd',order:'market_cap_desc',per_page:100,page:1,sparkline:'false',price_change_percentage:'24h'};
const coins=await getJson(`${CG}/coins/markets`, params);

const stableSyms=new Set(['USDT','USDC','DAI','BUSD','TUSD','USDE','FDUSD','USDP','GUSD','LUSD','FRAX','USDD','PYUSD','CRVUSD','SUSD','EURS','EURT','USDS']);
const filtered=coins.filter(c=>!stableSyms.has((c.symbol||'').toUpperCase()));

const ex=await getJson(`${BN}/api/v3/exchangeInfo`);
const baseToSymbol=new Map();
for(const s of (ex.symbols||[])){
  if(s.status!=='TRADING') continue;
  if(s.quoteAsset!=='USDT') continue;
  const base=s.baseAsset;
  if(['UP','DOWN','BULL','BEAR'].some(x=>base.includes(x))) continue;
  if(!baseToSymbol.has(base)) baseToSymbol.set(base, s.symbol);
}

let candidates=[];
for(const c of filtered){
  const base=(c.symbol||'').toUpperCase();
  const sym=baseToSymbol.get(base);
  if(sym) candidates.push([c,sym]);
}

candidates=candidates.slice(0,70);

async function analyzeSymbol(sym){
  const kl=await getJson(`${BN}/api/v3/klines`, {symbol:sym, interval:'1h', limit:25});
  if(!Array.isArray(kl) || kl.length<25) return null;
  const qvols=kl.map(k=>Number(k[7]));
  const opens=kl.map(k=>Number(k[1]));
  const closes=kl.map(k=>Number(k[4]));

  const lastOpen=opens.at(-1), lastClose=closes.at(-1), prevClose=closes.at(-2);
  const lastRet=(lastClose/lastOpen-1)*100;
  const lastRetVsPrev=(lastClose/prevClose-1)*100;
  const lastQvol=qvols.at(-1);
  const prev=qvols.slice(0,-1);
  const avgPrev=prev.reduce((a,b)=>a+b,0)/prev.length;
  const medPrev=[...prev].sort((a,b)=>a-b)[Math.floor(prev.length/2)];
  const volMult=lastQvol/(avgPrev+1e-9);
  const volMultMed=lastQvol/(medPrev+1e-9);

  const high=Number(kl.at(-1)[2]);
  const low=Number(kl.at(-1)[3]);
  const rng=low>0 ? (high/low-1)*100 : 0;

  return {sym,lastRet,lastRetVsPrev,lastQvol,volMult,volMultMed,rng,lastClose};
}

const alerts=[];
for(const [c,sym] of candidates){
  let a=null;
  try{ a=await analyzeSymbol(sym); } catch(e){ a=null; }
  if(!a){ await sleep(120); continue; }

  const bigMove = Math.abs(a.lastRet)>=3.5 || Math.abs(a.lastRetVsPrev)>=3.5 || a.rng>=5.0;
  const bigVol = a.volMult>=3.0 && a.lastQvol>250000; // USDT quote vol in last hour

  let score=0;
  if(bigVol) score+=2;
  if(bigMove) score+=2;
  const cg24=c.price_change_percentage_24h;
  if(Number.isFinite(cg24) && Math.abs(cg24)>=12) score+=1;

  if(score>=3){
    alerts.push({
      score,
      rank:c.market_cap_rank,
      base:(c.symbol||'').toUpperCase(),
      name:c.name,
      sym,
      cg24,
      oneh_ret:a.lastRet,
      oneh_rng:a.rng,
      volx:a.volMult,
      volx_med:a.volMultMed,
      last_qvol:a.lastQvol,
    });
  }

  await sleep(120);
}

alerts.sort((x,y)=> (y.score-x.score) || (Math.abs(y.oneh_ret)-Math.abs(x.oneh_ret)) || (y.volx-x.volx));

console.log(JSON.stringify({meta:{binance_candidates:candidates.length, alerts:alerts.length}, alerts:alerts.slice(0,12)}, null, 2));
