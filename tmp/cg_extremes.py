import requests
cg_url='https://api.coingecko.com/api/v3/coins/markets'
params={'vs_currency':'usd','order':'market_cap_desc','per_page':100,'page':1,'sparkline':'false','price_change_percentage':'1h,24h'}
coins=requests.get(cg_url,params=params,timeout=30).json()

def k(c):
 return (c.get('symbol') or '').upper()

# collect metrics
rows=[]
for c in coins:
 p1=c.get('price_change_percentage_1h_in_currency')
 p24=c.get('price_change_percentage_24h_in_currency')
 vol=c.get('total_volume') or 0
 mcap=c.get('market_cap') or 0
 v= (vol/mcap) if mcap else None
 rows.append((c['name'],k(c),c.get('current_price'),p1,p24,v,vol,mcap))

def top_by(idx,n=8):
 vals=[r for r in rows if r[idx] is not None]
 vals.sort(key=lambda r: abs(r[idx]), reverse=True)
 return vals[:n]

def top_vratio(n=8):
 vals=[r for r in rows if r[5] is not None]
 vals.sort(key=lambda r: r[5], reverse=True)
 return vals[:n]

print('top_abs_1h')
for r in top_by(3):
 print(r)
print('top_abs_24h')
for r in top_by(4):
 print(r)
print('top_vratio')
for r in top_vratio():
 print(r)
