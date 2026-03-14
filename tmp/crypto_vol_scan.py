import requests, math

CG_URL = 'https://api.coingecko.com/api/v3/coins/markets'
params = {
    'vs_currency': 'usd',
    'order': 'market_cap_desc',
    'per_page': 250,
    'page': 1,
    'sparkline': 'false',
    'price_change_percentage': '1h,24h,7d',
}
import time

# Be gentle with CoinGecko free tier
params['per_page'] = 120

coins = None
last = None
for i in range(3):
    resp = requests.get(CG_URL, params=params, timeout=30)
    if resp.status_code == 429:
        last = resp.json() if resp.headers.get('content-type','').startswith('application/json') else resp.text
        time.sleep(12*(i+1))
        continue
    resp.raise_for_status()
    coins = resp.json()
    break

if not isinstance(coins, list):
    raise SystemExit(f"CoinGecko markets unavailable (likely rate-limit). Last: {str(last)[:200]}")

stables = {
    'usdt','usdc','dai','fdusd','tusd','usde','usdd','usdp','usds','lusd','frax','pyusd','busd','ustc','eurt','eurs','usd1'
}
exclude = {'bitcoin','ethereum'}

alts = []
for c in coins:
    sym = (c.get('symbol') or '').lower()
    cid = (c.get('id') or '').lower()
    if cid in exclude:
        continue
    if sym in stables:
        continue
    alts.append(c)

alts = alts[:100]

B_URL = 'https://api.binance.com/api/v3/ticker/24hr'
try:
    tickers = requests.get(B_URL, timeout=30).json()
except Exception:
    tickers = []

usdt = {}
btc = {}
if isinstance(tickers, list):
    for t in tickers:
        s = t.get('symbol','')
        if s.endswith('USDT'):
            usdt[s[:-4].lower()] = t
        elif s.endswith('BTC'):
            btc[s[:-3].lower()] = t

def fnum(x):
    try:
        return float(x)
    except Exception:
        return float('nan')

alerts = []
for c in alts:
    sym = (c.get('symbol') or '').lower()
    mcap = c.get('market_cap') or 0
    vol = c.get('total_volume') or 0
    ch1 = c.get('price_change_percentage_1h_in_currency')
    ch24 = c.get('price_change_percentage_24h_in_currency')
    ch1 = float(ch1) if ch1 is not None else float('nan')
    ch24 = float(ch24) if ch24 is not None else float('nan')

    bt = usdt.get(sym) or btc.get(sym)
    b_qv = fnum(bt.get('quoteVolume')) if bt else float('nan')
    b_pch = fnum(bt.get('priceChangePercent')) if bt else float('nan')

    vol_mcap = (vol / mcap) if mcap else float('nan')

    extreme_move = (abs(ch1) >= 7) or (abs(ch24) >= 20)
    unusual_turnover = (vol_mcap >= 0.30 and mcap > 200_000_000)

    div = None
    if (not math.isnan(b_qv)) and vol:
        div = b_qv / vol if vol else None
    divergence = (div is not None and (div >= 2.5 or div <= 0.4) and mcap > 500_000_000)

    score = 0
    if extreme_move:
        score += 2
    if unusual_turnover:
        score += 1
    if divergence:
        score += 1
    if bt and (not math.isnan(b_pch)) and abs(b_pch) >= 15:
        score += 1

    if score >= 3:
        alerts.append((score, c, bt, vol_mcap, div, b_qv, b_pch))

alerts.sort(key=lambda x: (-x[0], -(abs(float(x[1].get('price_change_percentage_24h_in_currency') or 0))), -(x[1].get('market_cap') or 0)))

print('N_ALTS', len(alts))
print('N_ALERTS', len(alerts))
for score, c, bt, vol_mcap, div, b_qv, b_pch in alerts[:12]:
    name = c.get('name')
    symU = (c.get('symbol') or '').upper()
    ch1 = c.get('price_change_percentage_1h_in_currency')
    ch24 = c.get('price_change_percentage_24h_in_currency')
    mcap = c.get('market_cap')
    vol = c.get('total_volume')
    price = c.get('current_price')
    print('---')
    print(f"{score} | {name} ({symU})")
    print(f"Price ${price:,} | 1h {ch1:.2f}% | 24h {ch24:.2f}% | mcap ${mcap:,}")
    print(f"CG vol24h ${vol:,} | turnover vol/mcap {vol_mcap:.2f}")
    if bt:
        print(f"Binance 24h pch {b_pch:.2f}% | quoteVol ${b_qv:,.0f} | symbol {bt.get('symbol')}")
    if div is not None:
        print(f"Binance/CG volume ratio {div:.2f}")
