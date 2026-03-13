const cgUrl = 'https://api.coingecko.com/api/v3/coins/markets';
const params = new URLSearchParams({
  vs_currency: 'usd',
  order: 'market_cap_desc',
  per_page: '100',
  page: '1',
  sparkline: 'false',
  price_change_percentage: '1h,24h,7d'
});

const r = await fetch(`${cgUrl}?${params.toString()}`, { headers: { 'accept': 'application/json' } });
if (!r.ok) throw new Error(`CoinGecko HTTP ${r.status}`);
const js = await r.json();

const rows = js.map(c => ({
  sym: (c.symbol || '').toUpperCase(),
  name: c.name,
  mc: c.market_cap || 0,
  vol: c.total_volume || 0,
  price: c.current_price || 0,
  ch1h: c.price_change_percentage_1h_in_currency,
  ch24h: c.price_change_percentage_24h_in_currency,
  vol_mc: (c.market_cap && c.total_volume) ? (c.total_volume / c.market_cap) : null
}));

function topBy(col, n, asc=false) {
  const filtered = rows.filter(r => Number.isFinite(r[col]));
  filtered.sort((a,b) => asc ? a[col]-b[col] : b[col]-a[col]);
  return filtered.slice(0,n).map(r => ({sym:r.sym,[col]:r[col],ch1h:r.ch1h,ch24h:r.ch24h,vol_mc:r.vol_mc}));
}

function topVolMc(n){
  const filtered = rows.filter(r => Number.isFinite(r.vol_mc));
  filtered.sort((a,b)=>b.vol_mc-a.vol_mc);
  return filtered.slice(0,n).map(r => ({sym:r.sym, ch1h:r.ch1h, ch24h:r.ch24h, vol_mc:r.vol_mc}));
}

console.log('TOP_1H_UP', JSON.stringify(topBy('ch1h',10,false)));
console.log('TOP_1H_DOWN', JSON.stringify(topBy('ch1h',10,true)));
console.log('TOP_24H_UP', JSON.stringify(topBy('ch24h',10,false)));
console.log('TOP_24H_DOWN', JSON.stringify(topBy('ch24h',10,true)));
console.log('TOP_VOL_MC', JSON.stringify(topVolMc(15)));
