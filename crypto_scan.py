import requests, math

# CoinGecko top 100 by market cap
cg_url='https://api.coingecko.com/api/v3/coins/markets'
params={
    'vs_currency':'usd',
    'order':'market_cap_desc',
    'per_page':100,
    'page':1,
    'sparkline':'false',
    'price_change_percentage':'1h,24h,7d'
}
coins = requests.get(cg_url, params=params, timeout=30).json()

# Binance exchange info & 24h tickers
exinfo = requests.get('https://api.binance.com/api/v3/exchangeInfo', timeout=30).json()
syms = [s for s in exinfo.get('symbols', [])
        if s.get('status')=='TRADING' and s.get('quoteAsset') in ('USDT','FDUSD','USDC','BUSD')]

# Prefer USDT quoting when multiple exist
pref_rank = {'USDT':0,'FDUSD':1,'USDC':2,'BUSD':3}
sym_by_base = {}
for s in syms:
    base, quote, symbol = s['baseAsset'], s['quoteAsset'], s['symbol']
    rank = pref_rank.get(quote, 9)
    if base not in sym_by_base or rank < sym_by_base[base][0]:
        sym_by_base[base] = (rank, symbol, quote)

all_tickers = requests.get('https://api.binance.com/api/v3/ticker/24hr', timeout=30).json()
ticker_map = {t['symbol']: t for t in all_tickers if isinstance(t, dict) and 'symbol' in t}


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def hour_spike(symbol: str):
    """Return (last_hour_return_pct, volume_spike_ratio_vs_prev_hours_avg)."""
    url = 'https://api.binance.com/api/v3/klines'
    p = {'symbol': symbol, 'interval': '1h', 'limit': 25}
    r = requests.get(url, params=p, timeout=30)
    if r.status_code != 200:
        return None
    k = r.json()
    if not k or len(k) < 10:
        return None
    vols = [float(x[5]) for x in k]
    opens = [float(x[1]) for x in k]
    closes = [float(x[4]) for x in k]

    last_vol = vols[-1]
    avg_prev = sum(vols[:-1]) / max(1, (len(vols) - 1))
    last_ret = (closes[-1] - opens[-1]) / opens[-1] * 100
    ratio = (last_vol / avg_prev) if avg_prev > 0 else None
    return last_ret, ratio


interesting = []
for c in coins:
    base = (c.get('symbol') or '').upper()
    if base not in sym_by_base:
        continue

    name = c.get('name')
    _, bsymbol, quote = sym_by_base[base]
    t = ticker_map.get(bsymbol)
    if not t:
        continue

    chg24 = f(t.get('priceChangePercent'))
    qv = float(t.get('quoteVolume') or 0.0)  # quote currency
    trades = int(float(t.get('count') or 0))

    cg_1h = c.get('price_change_percentage_1h_in_currency')
    cg_24h = c.get('price_change_percentage_24h_in_currency')
    cg_7d = c.get('price_change_percentage_7d_in_currency')

    hs = hour_spike(bsymbol)
    last_ret, vol_ratio = (hs if hs else (None, None))

    extreme = (chg24 is not None and abs(chg24) >= 12) or (cg_1h is not None and abs(cg_1h) >= 3.5)
    vol_big = qv >= 80_000_000
    vol_spike = (vol_ratio is not None and vol_ratio >= 2.8 and last_ret is not None and abs(last_ret) >= 1.8)
    divergence = (vol_ratio is not None and vol_ratio >= 3.5 and last_ret is not None and abs(last_ret) <= 0.6)

    score = 0
    reasons = []
    if extreme:
        score += 2; reasons.append('movimiento fuerte')
    if vol_big:
        score += 1; reasons.append('volumen alto')
    if vol_spike:
        score += 2; reasons.append('spike 1h (precio+vol)')
    if divergence:
        score += 2; reasons.append('divergencia vol/price 1h')

    if score >= 4:
        interesting.append({
            'name': name, 'base': base, 'pair': bsymbol, 'quote': quote,
            'chg24': chg24, 'cg1h': cg_1h, 'cg24': cg_24h, 'cg7d': cg_7d,
            'qv': qv, 'trades': trades,
            'last_ret': last_ret, 'vol_ratio': vol_ratio,
            'reasons': reasons, 'score': score
        })

interesting.sort(key=lambda x: (-x['score'], -(abs(x['chg24']) if x['chg24'] is not None else 0.0), -x['qv']))

print(len(interesting))
for x in interesting[:10]:
    print(
        x['pair'],
        x['name'],
        f"24h={x['chg24']:.2f}%" if x['chg24'] is not None else '24h=?',
        f"CG1h={x['cg1h']:.2f}%" if isinstance(x['cg1h'], (int,float)) else 'CG1h=?',
        f"1h={x['last_ret']:.2f}%" if x['last_ret'] is not None else '1h=?',
        f"volSpike={x['vol_ratio']:.2f}x" if x['vol_ratio'] is not None else 'volSpike=?',
        f"qVol=${x['qv']/1e6:.1f}M",
        ','.join(x['reasons'])
    )
