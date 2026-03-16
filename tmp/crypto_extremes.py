import requests

def f(x):
    try:
        return float(x)
    except Exception:
        return None

CG_URL = 'https://api.coingecko.com/api/v3/coins/markets'
coins = requests.get(
    CG_URL,
    params={
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': 120,
        'page': 1,
        'sparkline': 'false',
        'price_change_percentage': '1h,24h',
    },
    timeout=30,
).json()

stable = {'usdt','usdc','dai','busd','tusd','fdusd','usde','frax','lusd','pyusd','usdd','usdp','gusd','susd','usd0'}
alts=[]
for c in coins:
    sym=(c.get('symbol') or '').lower()
    if sym in {'btc','eth'} or sym in stable:
        continue
    alts.append(c)
    if len(alts)>=100:
        break

ext=[]
for c in alts:
    p1=f(c.get('price_change_percentage_1h_in_currency'))
    p24=f(c.get('price_change_percentage_24h_in_currency'))
    if (p1 is not None and abs(p1)>=6) or (p24 is not None and abs(p24)>=20):
        ext.append({
            'rank': c.get('market_cap_rank'),
            'name': c.get('name'),
            'sym': (c.get('symbol') or '').upper(),
            'p1': p1,
            'p24': p24,
        })

ext.sort(key=lambda x: (abs(x['p24'] or 0), abs(x['p1'] or 0)), reverse=True)
print('EXT_COUNT', len(ext))
for x in ext[:12]:
    p1='n/a' if x['p1'] is None else f"{x['p1']:.2f}%"
    p24='n/a' if x['p24'] is None else f"{x['p24']:.2f}%"
    print(f"- #{x['rank']} {x['name']} ({x['sym']}) | 1h {p1} | 24h {p24}")
