import requests, math
url='https://api.coingecko.com/api/v3/coins/markets'
params={'vs_currency':'usd','order':'market_cap_desc','per_page':100,'page':1,'sparkline':'false','price_change_percentage':'1h,24h'}
data=requests.get(url,params=params,timeout=20).json()

def num(x):
    try:
        return float(x)
    except Exception:
        return float('nan')

rows=[]
for d in data:
    pc1=num(d.get('price_change_percentage_1h_in_currency'))
    pc24=num(d.get('price_change_percentage_24h_in_currency'))
    vol=num(d.get('total_volume'))
    mcap=num(d.get('market_cap'))
    vol_mcap=vol/mcap if mcap==mcap and mcap!=0 else float('nan')
    rows.append({
        'symbol':(d.get('symbol') or '').upper(),
        'name':d.get('name'),
        'price':num(d.get('current_price')),
        'pc1h':pc1,
        'pc24h':pc24,
        'vol_mcap':vol_mcap,
        'volume':vol,
        'mcap':mcap
    })

notable=[r for r in rows if (abs(r['pc1h'])>=2) or (abs(r['pc24h'])>=10) or ((r['vol_mcap']==r['vol_mcap'] and r['vol_mcap']>=0.35) and abs(r['pc24h'])>=3)]
notable.sort(key=lambda r:(abs(r['pc24h']),abs(r['pc1h']), (r['vol_mcap'] if r['vol_mcap']==r['vol_mcap'] else 0)), reverse=True)

def fmt(r):
    vm = r['vol_mcap']
    vm_s = f"{vm:.2f}" if vm==vm else 'nan'
    return f"{r['symbol']:>6} | {r['pc1h']:+6.2f}% 1h | {r['pc24h']:+7.2f}% 24h | vol/mcap {vm_s} | ${r['price']:.6g} | {r['name']}"

print('notable_count',len(notable))
for r in notable[:12]:
    print(fmt(r))

rows.sort(key=lambda r:abs(r['pc1h']), reverse=True)
print('\nTop_abs1h')
for r in rows[:10]:
    print(fmt(r))
