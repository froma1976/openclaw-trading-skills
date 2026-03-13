const url = new URL('https://api.coingecko.com/api/v3/coins/markets');
url.search = new URLSearchParams({
  vs_currency: 'usd',
  order: 'market_cap_desc',
  per_page: '100',
  page: '1',
  sparkline: 'false',
  price_change_percentage: '1h,24h',
});

const num = (x) => (x === null || x === undefined || x === '' ? NaN : Number(x));
const fmt = (n) => (Number.isFinite(n) ? n.toFixed(2) : '');
const money = (n) => (Number.isFinite(n) ? `$${(n / 1e9).toFixed(2)}B` : '');

function line(r) {
  const vmc = Number.isFinite(r.vol_mc) ? r.vol_mc.toFixed(2) : '';
  return `${r.sym} ${fmt(r.ch1h)}% 1h | ${fmt(r.ch24h)}% 24h | vol/MC ${vmc} | vol ${money(r.vol)} mc ${money(r.mc)}`;
}

(async () => {
  const res = await fetch(url);
  const rows = await res.json();

  const data = rows
    .map((r) => ({
      sym: String(r.symbol || '').toUpperCase(),
      name: r.name,
      price: num(r.current_price),
      mc: num(r.market_cap),
      vol: num(r.total_volume),
      ch1h: num(r.price_change_percentage_1h_in_currency),
      ch24h: num(r.price_change_percentage_24h_in_currency),
    }))
    .map((r) => ({ ...r, vol_mc: r.vol / r.mc }));

  const movers = data
    .filter((r) => Math.abs(r.ch1h) > 3 || Math.abs(r.ch24h) > 8)
    .sort((a, b) => Math.abs(b.ch1h) - Math.abs(a.ch1h));

  const volTop = data
    .filter((r) => r.vol_mc > 0.25 && r.mc > 2e8)
    .sort((a, b) => b.vol_mc - a.vol_mc);

  const risk = data
    .filter((r) => r.ch1h < -2 && r.vol_mc > 0.15 && r.mc > 5e8)
    .sort((a, b) => a.ch1h - b.ch1h || b.vol_mc - a.vol_mc);

  console.log(`MOVERS ${movers.length}`);
  console.log(movers.slice(0, 15).map(line).join('\n'));
  console.log('\nVOL/MC TOP');
  console.log(
    volTop
      .slice(0, 15)
      .map(
        (r) =>
          `${r.sym} vol/MC ${r.vol_mc.toFixed(2)} | ${fmt(r.ch1h)}% 1h | ${fmt(
            r.ch24h,
          )}% 24h | vol ${money(r.vol)} mc ${money(r.mc)}`,
      )
      .join('\n'),
  );
  console.log('\nRISK (down 1h + high vol)');
  console.log(risk.slice(0, 15).map(line).join('\n'));
})();
