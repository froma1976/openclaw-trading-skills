const fetch = global.fetch;
const cgUrl = 'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=150&page=1&sparkline=false&price_change_percentage=1h,24h,7d';

async function fetchJsonWithRetry(url, opts, tries=4){
  let lastErr;
  for(let i=0;i<tries;i++){
    try{
      const res = await fetch(url, opts);
      if(res.status===429){
        const waitMs = 1200 * Math.pow(2,i);
        await new Promise(r=>setTimeout(r, waitMs));
        continue;
      }
      if(!res.ok) throw new Error('HTTP '+res.status);
      return await res.json();
    }catch(e){
      lastErr=e;
      const waitMs = 800 * Math.pow(2,i);
      await new Promise(r=>setTimeout(r, waitMs));
    }
  }
  throw lastErr || new Error('fetch failed');
}

const binUrl = 'https://api.binance.com/api/v3/ticker/24hr';
const stable = new Set(['tether','usd-coin','dai','true-usd','pax-dollar','first-digital-usd','frax','usdd','usde','usds','paypal-usd','eurc','stasis-eurs','tusd','busd']);
const major = new Set(['bitcoin','ethereum']);
function pct(n){ return (n==null||Number.isNaN(n))?null:Number(n); }
function fmtPct(n){ if(n==null) return 'n/a'; const s = n>=0?'+':''; return s + n.toFixed(1) + '%'; }
function fmtNum(n){ if(n==null||Number.isNaN(n)) return 'n/a'; if(n>=1e9) return (n/1e9).toFixed(2)+'B'; if(n>=1e6) return (n/1e6).toFixed(2)+'M'; if(n>=1e3) return (n/1e3).toFixed(2)+'K'; return n.toFixed(2); }

(async ()=>{
  const headers = { 'accept':'application/json', 'user-agent':'openclaw-vol-alert/1.0' };
  const [cg, bin] = await Promise.all([
    fetchJsonWithRetry(cgUrl,{headers}, 5),
    fetchJsonWithRetry(binUrl,{headers}, 4)
  ]);

  const binBySymbol = new Map();
  for(const r of bin){
    if(!r.symbol.endsWith('USDT')) continue;
    if(r.symbol.includes('UPUSDT')||r.symbol.includes('DOWNUSDT')||r.symbol.includes('BULLUSDT')||r.symbol.includes('BEARUSDT')) continue;
    binBySymbol.set(r.symbol, r);
  }

  const alts = cg
    .filter(x=>!major.has(x.id) && !stable.has(x.id) && x.market_cap_rank && x.market_cap_rank<=150)
    .sort((a,b)=>a.market_cap_rank-b.market_cap_rank)
    .slice(0,100);

  const scored = [];
  for(const c of alts){
    const sym = (c.symbol||'').toUpperCase();
    const b = binBySymbol.get(sym+'USDT');

    const ch1h = pct(c.price_change_percentage_1h_in_currency);
    const ch24 = pct(c.price_change_percentage_24h_in_currency);
    const ch7d = pct(c.price_change_percentage_7d_in_currency);
    const vol24 = c.total_volume;
    const mcap = c.market_cap;
    const vM = (vol24 && mcap) ? (vol24/mcap) : null;

    const bCh24 = b ? pct(Number(b.priceChangePercent)) : null;
    const bQVol = b ? Number(b.quoteVolume) : null;

    let score = 0;
    if(ch1h!=null) score += Math.min(12, Math.abs(ch1h))*1.2;
    if(ch24!=null) score += Math.min(20, Math.abs(ch24))*0.4;
    if(vM!=null) score += Math.min(3, vM)*8;
    if(bQVol!=null) score += Math.log10(Math.max(1,bQVol/1e6))*2;

    const flags = [];
    if(ch1h!=null && Math.abs(ch1h)>=8) flags.push('1h-extremo');
    if(ch24!=null && Math.abs(ch24)>=15) flags.push('24h-extremo');
    if(vM!=null && vM>=0.35) flags.push('vol/MCAP-alto');
    if(bQVol!=null && bQVol>=150e6) flags.push('Binance-vol-alto');

    const interesting = (ch1h!=null && Math.abs(ch1h)>=8)
      || ((ch24!=null && Math.abs(ch24)>=18) && (vM!=null && vM>=0.25))
      || (vM!=null && vM>=0.6);

    scored.push({interesting, score, sym, name:c.name, rank:c.market_cap_rank, price:c.current_price, ch1h, ch24, ch7d, vol24, mcap, vM, bCh24, bQVol, flags});
  }

  scored.sort((a,b)=>b.score-a.score);
  const interesting = scored.filter(x=>x.interesting).slice(0,8);

  if(interesting.length===0){
    console.log('OK');
    return;
  }

  const lines=[];
  lines.push('ALERTA (Top100 alts) — movimientos/volumen anómalos (CoinGecko + Binance 24h)');
  lines.push('Hora: 2026-03-09 12:00 Europe/Madrid');
  lines.push('');
  for(const x of interesting){
    lines.push(`${x.rank}. ${x.sym} (${x.name})`);
    lines.push(`  Precio: $${x.price} | 1h: ${fmtPct(x.ch1h)} | 24h(CG): ${fmtPct(x.ch24)} | 24h(Binance): ${fmtPct(x.bCh24)} | 7d: ${fmtPct(x.ch7d)}`);
    lines.push(`  Vol 24h: ${fmtNum(x.vol24)} | Mcap: ${fmtNum(x.mcap)} | Vol/Mcap: ${x.vM==null?'n/a':x.vM.toFixed(2)} | Binance quoteVol: ${fmtNum(x.bQVol)}`);
    lines.push(`  Señales: ${x.flags.length?x.flags.join(', '):'—'}`);
    lines.push('');
  }
  lines.push('Notas rápidas:');
  lines.push('- Pump 1h + vol/Mcap alto => alto riesgo de reversión; confirmar en 15m/1h y vigilar ruptura/fakeout.');
  lines.push('- Dump 1h + vol alto => posible capitulación; buscar absorción antes de intentar cuchillo.');
  console.log(lines.join('\n'));
})();
