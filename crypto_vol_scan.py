import requests, statistics, time
from datetime import datetime

def get(url, params=None, tries=5):
    last_err=None
    for i in range(tries):
        try:
            r = requests.get(
                url,
                params=params,
                timeout=25,
                headers={'User-Agent': 'openclaw-vol-scan/1.0 (+https://openclaw.ai)'}
            )
            if r.status_code == 429:
                # CoinGecko public rate limits can be tight; backoff
                wait = 15 * (2 ** i)
                time.sleep(min(wait, 90))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err=e
            time.sleep(min(5 * (i+1), 20))
    raise last_err

# CoinGecko: top by market cap
cg_markets = get(
    'https://api.coingecko.com/api/v3/coins/markets',
    params={
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': 250,
        'page': 1,
        'price_change_percentage': '1h,24h,7d',
        'sparkline': 'false'
    }
)

stables = {
    'tether','usd-coin','dai','binance-usd','true-usd','pax-dollar','frax',
    'first-digital-usd','usdd','tusd','paypal-usd','usde','usds'
}
exclude = {'bitcoin','ethereum'} | stables
alts = [c for c in cg_markets if c.get('id') not in exclude]
# top 100 alts
alts = alts[:100]

# Binance: 24h tickers
bin_tickers = get('https://api.binance.com/api/v3/ticker/24hr')
# USDT spot pairs (ignore leveraged tokens)
bin_map = {
    t['symbol']: t for t in bin_tickers
    if t['symbol'].endswith('USDT')
    and not t['symbol'].endswith('UPUSDT')
    and not t['symbol'].endswith('DOWNUSDT')
    and not t['symbol'].endswith('BULLUSDT')
    and not t['symbol'].endswith('BEARUSDT')
}

# Binance: 1h klines, last closed hour vs median of prior 24h

def kline_stats(symbol, interval='1h', limit=26):
    data = get('https://api.binance.com/api/v3/klines', params={'symbol': symbol, 'interval': interval, 'limit': limit})
    # Exclude the last kline (can be in-progress)
    data = data[:-1]
    vols = [float(k[5]) for k in data]
    closes = [float(k[4]) for k in data]
    if len(vols) < 3:
        return None
    last_vol = vols[-1]
    med_vol = statistics.median(vols[:-1])
    prev_close = closes[-2]
    last_close = closes[-1]
    hour_chg = (last_close - prev_close) / prev_close * 100 if prev_close else 0.0
    return last_vol, med_vol, hour_chg

alerts = []

for c in alts:
    sym = (c.get('symbol') or '').upper()
    bsymbol = f'{sym}USDT'
    bt = bin_map.get(bsymbol)
    if not bt:
        continue

    pc24_bin = float(bt.get('priceChangePercent') or 0)
    qv_bin = float(bt.get('quoteVolume') or 0)  # in USDT

    cg_pc24 = float(c.get('price_change_percentage_24h') or 0)
    cg_vol = float(c.get('total_volume') or 0)  # USD-ish

    div_move = abs(pc24_bin - cg_pc24)
    vol_div = (qv_bin / cg_vol) if cg_vol > 0 else None

    # Heuristics
    extreme_move = abs(pc24_bin) >= 12 or abs(cg_pc24) >= 12
    risk_move = abs(pc24_bin) >= 18

    vol_flag = (vol_div is not None) and (qv_bin > 50_000_000) and (vol_div >= 2.5 or vol_div <= 0.25)
    move_div_flag = (qv_bin > 30_000_000) and (abs(pc24_bin) >= 6) and (div_move >= 6)

    hour_vol_spike = None
    hour_chg = None
    hour_spike_flag = False
    try:
        ks = kline_stats(bsymbol)
        if ks:
            last_vol, med_vol, hour_chg = ks
            if med_vol > 0:
                hour_vol_spike = last_vol / med_vol
                hour_spike_flag = hour_vol_spike >= 4 and abs(hour_chg) >= 2
    except Exception:
        pass

    if extreme_move or vol_flag or move_div_flag or hour_spike_flag:
        alerts.append({
            'rank': c.get('market_cap_rank'),
            'sym': sym,
            'name': c.get('name'),
            'pc24_bin': pc24_bin,
            'pc24_cg': cg_pc24,
            'qv_bin': qv_bin,
            'cg_vol': cg_vol,
            'vol_div': vol_div,
            'div_move': div_move,
            'hour_vol_spike': hour_vol_spike,
            'hour_chg': hour_chg,
            'risk_move': risk_move,
        })

alerts.sort(key=lambda a: (a['risk_move'], abs(a['pc24_bin']), (a['hour_vol_spike'] or 0), a['qv_bin']), reverse=True)

print('asof', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print('found', len(alerts), 'candidates')
for a in alerts[:15]:
    vd = a['vol_div']
    vd_s = f"{vd:.2f}x" if vd is not None else 'n/a'
    hvs = a['hour_vol_spike']
    hvs_s = f"{hvs:.1f}x" if hvs is not None else 'n/a'
    hc = a['hour_chg']
    hc_s = f"{hc:+.1f}%" if hc is not None else 'n/a'
    print(f"#{a['rank']:>3} {a['sym']:<7} {a['name']:<18} 24h: {a['pc24_bin']:+.1f}% (CG {a['pc24_cg']:+.1f}%) | 1h: {hc_s} volSpike {hvs_s} | VolDiv(Bin/CG): {vd_s} | QVol: ${a['qv_bin']/1e6:.0f}M")
