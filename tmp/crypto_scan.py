import requests

vs='usd'
url='https://api.coingecko.com/api/v3/coins/markets'
params={'vs_currency':vs,'order':'market_cap_desc','per_page':100,'page':1,'sparkline':'false','price_change_percentage':'1h,24h'}
coins=requests.get(url,params=params,timeout=30).json()

stables=set(['tether','usd-coin','dai','true-usd','first-digital-usd','frax','usdd','usde','paypal-usd','tusd','usds','fdusd','usdt','usdc'])

def is_stable(c):
    sym=(c.get('symbol') or '').lower()
    cid=(c.get('id') or '').lower()
    name=(c.get('name') or '').lower()
    return sym in stables or cid in stables or ('usd' in name and ('coin' in name or 'dollar' in name))

items=[]
for c in coins:
    if is_stable(c):
        continue
    ch1=c.get('price_change_percentage_1h_in_currency')
    ch24=c.get('price_change_percentage_24h_in_currency')
    vol=c.get('total_volume') or 0
    mcap=c.get('market_cap') or 1
    vol_ratio=vol/mcap if mcap else 0
    items.append({
        'sym': c['symbol'].upper(),
        'name': c['name'],
        'ch1': ch1,
        'ch24': ch24,
        'vol': vol,
        'mcap': mcap,
        'vr': vol_ratio,
        'px': c.get('current_price'),
    })

# Extremes
by_abs_1h=sorted([i for i in items if i['ch1'] is not None], key=lambda x: abs(x['ch1']), reverse=True)
by_abs_24h=sorted([i for i in items if i['ch24'] is not None], key=lambda x: abs(x['ch24']), reverse=True)

# Simple "volume divergence": high vol/mcap and meaningful 1h move
vol_rank=sorted(items, key=lambda x: x['vr'], reverse=True)

print('COINGECKO_TOP_1H')
for i in by_abs_1h[:10]:
    print(i['sym'], f"1h={i['ch1']:.2f}%", f"24h={i['ch24']:.2f}%" if i['ch24'] is not None else "24h=?", f"vol/mcap={i['vr']:.3f}")

print('\nCOINGECKO_TOP_24H')
for i in by_abs_24h[:10]:
    print(i['sym'], f"1h={i['ch1']:.2f}%" if i['ch1'] is not None else "1h=?", f"24h={i['ch24']:.2f}%", f"vol/mcap={i['vr']:.3f}")

print('\nCOINGECKO_VOL_DIVERGENCE')
# Show top 15 by vol/mcap, but keep those with abs(1h) >= 1.5%
shown=0
for i in vol_rank:
    if i['ch1'] is None:
        continue
    if abs(i['ch1']) < 1.5:
        continue
    print(i['sym'], f"vol/mcap={i['vr']:.3f}", f"1h={i['ch1']:.2f}%", f"24h={i['ch24']:.2f}%" if i['ch24'] is not None else "24h=?")
    shown+=1
    if shown>=10:
        break
