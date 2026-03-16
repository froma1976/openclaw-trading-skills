import requests

cg_url = 'https://api.coingecko.com/api/v3/coins/markets'
params = {
    'vs_currency': 'usd',
    'order': 'market_cap_desc',
    'per_page': 100,
    'page': 1,
    'sparkline': 'false',
    'price_change_percentage': '1h,24h'
}
coins = requests.get(cg_url, params=params, timeout=30).json()

stable_kw = {
    'usdt','usdc','dai','tusd','usde','fdusd','usdp','busd','eurc','pyusd','susd','usdd','lusd','frax',
    'usd1','usdx','usdr','crvusd','gho'
}

def is_stable(c):
    s = (c.get('symbol') or '').lower()
    n = (c.get('name') or '').lower()
    if s in stable_kw:
        return True
    p24 = c.get('price_change_percentage_24h_in_currency')
    price = c.get('current_price')
    if price and 0.98 <= price <= 1.02 and (p24 is None or abs(p24) < 0.5):
        return True
    if any(k in n for k in ['stable', 'dollar']) and 'gold' not in n:
        return True
    return False

alts = [c for c in coins if not is_stable(c)]

alerts = []
for c in alts:
    name = c['name']
    sym = c['symbol'].upper()
    p1h = c.get('price_change_percentage_1h_in_currency')
    p24 = c.get('price_change_percentage_24h_in_currency')
    vol = c.get('total_volume') or 0
    mcap = c.get('market_cap') or 0
    vratio = (vol / mcap) if mcap else None

    flags = []
    score = 0

    if p1h is not None:
        if abs(p1h) >= 8:
            flags.append(f"1h {p1h:+.1f}%")
            score += 3
        elif abs(p1h) >= 5:
            flags.append(f"1h {p1h:+.1f}%")
            score += 2

    if p24 is not None:
        if abs(p24) >= 25:
            flags.append(f"24h {p24:+.1f}%")
            score += 3
        elif abs(p24) >= 15:
            flags.append(f"24h {p24:+.1f}%")
            score += 2

    if vratio is not None:
        if vratio >= 0.9:
            flags.append(f"Vol/MCap {vratio:.2f} (muy alto)")
            score += 3
        elif vratio >= 0.5:
            flags.append(f"Vol/MCap {vratio:.2f}")
            score += 2
        elif vratio >= 0.3:
            flags.append(f"Vol/MCap {vratio:.2f}")
            score += 1

    if score >= 4:
        alerts.append((score, name, sym, c.get('current_price'), vol, mcap, flags, p1h, p24, vratio))

alerts.sort(reverse=True, key=lambda x: (x[0], abs(x[7] or 0), abs(x[8] or 0)))

# Binance 24h tickers (best-effort)
binance_tickers = {}
try:
    t = requests.get('https://api.binance.com/api/v3/ticker/24hr', timeout=30).json()
    if isinstance(t, list):
        for row in t:
            s = row.get('symbol')
            if s:
                binance_tickers[s] = row
except Exception:
    pass

def binfo(sym):
    pair = sym + 'USDT'
    r = binance_tickers.get(pair)
    if not r:
        return None
    def f(x):
        try:
            return float(x)
        except Exception:
            return 0.0
    return {
        'pair': pair,
        'quoteVolume': f(r.get('quoteVolume')),
        'priceChangePercent': f(r.get('priceChangePercent')),
        'tradeCount': int(r.get('count') or 0),
        'lastPrice': f(r.get('lastPrice')),
    }

out = []
for a in alerts[:12]:
    score, name, sym, price, vol, mcap, flags, p1h, p24, vratio = a
    out.append({
        'score': score,
        'name': name,
        'sym': sym,
        'price': price,
        'vol': vol,
        'mcap': mcap,
        'flags': flags,
        'p1h': p1h,
        'p24': p24,
        'vratio': vratio,
        'binance': binfo(sym)
    })

print({'total_candidates': len(alerts), 'top': out})
