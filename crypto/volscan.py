import requests, time
from collections import defaultdict

CG_URL = 'https://api.coingecko.com/api/v3/coins/markets'
CG_PARAMS = {
    'vs_currency': 'usd',
    'order': 'market_cap_desc',
    'per_page': 100,
    'page': 1,
    'sparkline': 'false',
    'price_change_percentage': '1h,24h'
}

# Rough stablecoin filter
STABLE_IDS = {
    'tether','usd-coin','binance-usd','dai','true-usd','pax-dollar','frax',
    'first-digital-usd','paypal-usd','usdd','usde','usds','eurc'
}
STABLE_SYMBOLS = {'usdt','usdc','busd','dai','tusd','usdp','frax','fdusd','pyusd','usdd','usde','usds','eurc'}

BINANCE_24H = 'https://api.binance.com/api/v3/ticker/24hr'
BINANCE_KLINES = 'https://api.binance.com/api/v3/klines'

sess = requests.Session()
sess.headers.update({'User-Agent': 'openclaw-vol-alert/1.0'})

# --- CoinGecko top100 ---
resp = sess.get(CG_URL, params=CG_PARAMS, timeout=30)
resp.raise_for_status()
coins = resp.json()

filtered = []
for c in coins:
    if c.get('id') in STABLE_IDS:
        continue
    sym = (c.get('symbol') or '').lower()
    if sym in STABLE_SYMBOLS:
        continue
    if sym in ('btc','eth'):
        continue
    filtered.append(c)

# --- Binance 24h tickers ---
resp = sess.get(BINANCE_24H, timeout=30)
resp.raise_for_status()
tickers = resp.json()
bin_by_symbol = {t['symbol']: t for t in tickers}

usdt_pairs = [t['symbol'] for t in tickers if t['symbol'].endswith('USDT') and not t['symbol'].startswith('USDT')]
set_usdt = set(usdt_pairs)
base_to_pair = defaultdict(list)
for p in usdt_pairs:
    base_to_pair[p[:-4]].append(p)

def find_pair(cg_sym: str):
    s = cg_sym.upper()
    if s + 'USDT' in set_usdt:
        return s + 'USDT'
    # heuristic for 1000* tokens etc.
    for base, pairs in base_to_pair.items():
        if base.endswith(s) and len(base) <= len(s) + 4:
            return pairs[0]
    for base, pairs in base_to_pair.items():
        if base.startswith(s) and len(base) <= len(s) + 3:
            return pairs[0]
    return None

alerts = []  # (severity, score, msg)

for c in filtered:
    sym = (c.get('symbol') or '').lower()
    pair = find_pair(sym)
    if not pair:
        continue
    t = bin_by_symbol.get(pair)
    if not t:
        continue

    try:
        ch24 = float(t.get('priceChangePercent', 0.0))

        r = sess.get(BINANCE_KLINES, params={'symbol': pair, 'interval': '1h', 'limit': 25}, timeout=30)
        r.raise_for_status()
        kl = r.json()
        if len(kl) < 2:
            continue

        last = kl[-1]
        prev = kl[-2]
        close_last = float(last[4])
        close_prev = float(prev[4])
        ret1h = (close_last / close_prev - 1.0) * 100.0 if close_prev else 0.0

        qv_last = float(last[7])  # quote volume in USDT
        qv_list = [float(x[7]) for x in kl[:-1]]
        avg_qv = (sum(qv_list[-24:]) / min(24, len(qv_list[-24:]))) if qv_list else 0.0
        vol_mult = (qv_last / avg_qv) if avg_qv > 0 else 0.0

        # 1) Extreme move (1h)
        if abs(ret1h) >= 6.0:
            severity = 'ALTA' if abs(ret1h) >= 10 else 'MEDIA'
            direction = '↑' if ret1h > 0 else '↓'
            alerts.append((severity, abs(ret1h), f"{pair}: {direction} {ret1h:.1f}% en 1h (vol x{vol_mult:.1f}; 24h {ch24:.1f}%)"))

        # 2) Volume spike w/out price
        if abs(ret1h) <= 2.0 and vol_mult >= 4.0 and qv_last >= 5e6:
            alerts.append(('MEDIA', vol_mult, f"{pair}: volumen anómalo sin mover precio (1h {ret1h:.1f}%; vol x{vol_mult:.1f})"))

        # 3) Dump + volume
        if ret1h <= -4.0 and vol_mult >= 3.0:
            sev = 'ALTA' if ret1h <= -8 else 'MEDIA'
            alerts.append((sev, abs(ret1h) + vol_mult, f"{pair}: posible capitulación (1h {ret1h:.1f}%; vol x{vol_mult:.1f})"))

        # 4) Pump + volume
        if ret1h >= 4.0 and vol_mult >= 3.0:
            sev = 'ALTA' if ret1h >= 8 else 'MEDIA'
            alerts.append((sev, abs(ret1h) + vol_mult, f"{pair}: breakout/short-squeeze (1h {ret1h:.1f}%; vol x{vol_mult:.1f})"))

        time.sleep(0.03)
    except Exception:
        continue

# dedup
seen = set()
uniq = []
for sev, score, msg in alerts:
    if msg in seen:
        continue
    seen.add(msg)
    uniq.append((sev, score, msg))

order = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2}
uniq.sort(key=lambda x: (order.get(x[0], 9), -x[1]))

print('ALERT_COUNT', len(uniq))
for sev, score, msg in uniq[:10]:
    print(sev, msg)
