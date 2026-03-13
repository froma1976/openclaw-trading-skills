const API = 'https://api.binance.com/api/v3/ticker/24hr';

const STABLE_BASES = new Set([
  'USDT','USDC','BUSD','TUSD','DAI','FDUSD','USDP','PAX','USD','EUR','TRY','BRL','GBP','AUD','BIDR','IDRT','UAH','RUB','ZAR','NGN','VAI'
]);

function isUsdtPair(sym){
  return sym.endsWith('USDT');
}
function baseOfUsdt(sym){
  return sym.slice(0, -4);
}

const num = (x) => (x === null || x === undefined || x === '' ? NaN : Number(x));
const fmt = (n) => (Number.isFinite(n) ? n.toFixed(2) : '');
const money = (n) => {
  if (!Number.isFinite(n)) return '';
  if (n >= 1e9) return `$${(n/1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n/1e6).toFixed(2)}M`;
  if (n >= 1e3) return `$${(n/1e3).toFixed(2)}K`;
  return `$${n.toFixed(2)}`;
};

(async () => {
  const res = await fetch(API, { headers: { 'accept': 'application/json' } });
  if (!res.ok) {
    const t = await res.text();
    console.log('Binance fetch failed', res.status, t.slice(0,200));
    process.exit(2);
  }
  const rows = await res.json();

  const usdt = rows
    .filter(r => isUsdtPair(r.symbol))
    .map(r => {
      const base = baseOfUsdt(r.symbol);
      return {
        symbol: r.symbol,
        base,
        last: num(r.lastPrice),
        chgPct: num(r.priceChangePercent),
        quoteVol: num(r.quoteVolume),
        trades: num(r.count),
        high: num(r.highPrice),
        low: num(r.lowPrice)
      };
    })
    // remove stables and obvious fiat-like bases
    .filter(r => !STABLE_BASES.has(r.base))
    // remove weird legacy tickers with zero volume
    .filter(r => Number.isFinite(r.quoteVol) && r.quoteVol > 2_000_000);

  // extreme moves, but require meaningful liquidity
  const extreme = usdt
    .filter(r => Math.abs(r.chgPct) >= 10)
    .sort((a,b) => Math.abs(b.chgPct) - Math.abs(a.chgPct));

  // volume leaders (potentially "something just happened" even if price quiet)
  const volLeaders = usdt
    .slice()
    .sort((a,b) => b.quoteVol - a.quoteVol)
    .slice(0, 20);

  // "divergence" heuristic: high volume but small % move (abs<1.2%)
  const volDivergence = usdt
    .filter(r => Math.abs(r.chgPct) < 1.2)
    .sort((a,b) => b.quoteVol - a.quoteVol)
    .slice(0, 12);

  const printLine = r => `${r.symbol} ${fmt(r.chgPct)}% | vol ${money(r.quoteVol)} | H/L ${r.high}/${r.low}`;

  console.log(`USDT pairs scanned (liq>=$2M quoteVol): ${usdt.length}`);
  console.log(`Extreme movers (|24h|>=10%): ${extreme.length}`);
  console.log(extreme.slice(0, 12).map(printLine).join('\n'));

  console.log('\nTop quoteVolume (USDT):');
  console.log(volLeaders.slice(0, 12).map(printLine).join('\n'));

  console.log('\nHigh volume + low % move (possible accumulation/distribution):');
  console.log(volDivergence.map(printLine).join('\n'));
})();
