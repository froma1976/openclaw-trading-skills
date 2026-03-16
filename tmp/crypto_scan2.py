import requests, sys

cg_url='https://api.coingecko.com/api/v3/coins/markets'
params={'vs_currency':'usd','order':'market_cap_desc','per_page':100,'page':1,'sparkline':'false','price_change_percentage':'1h,24h,7d'}
headers={'User-Agent':'OpenClaw-Cron/1.0'}
resp=requests.get(cg_url,params=params,headers=headers,timeout=30)
if resp.status_code!=200:
    print('CG_HTTP',resp.status_code, resp.text[:200])
    sys.exit(2)
coins=resp.json()
if not isinstance(coins,list):
    print('CG_BAD',str(coins)[:200])
    sys.exit(2)

binance_url='https://api.binance.com/api/v3/ticker/24hr'
resp2=requests.get(binance_url,headers=headers,timeout=30)
if resp2.status_code!=200:
    tickers=[]
else:
    tickers=resp2.json()
bmap={t['symbol']:t for t in tickers if isinstance(t,dict) and 'symbol' in t}

exc={'miota':'IOTA','polygon':'POL','the-open-network':'TON','internet-computer':'ICP','filecoin':'FIL','near':'NEAR','okb':'OKB','pepe':'PEPE','first-digital-usd':'FDUSD','binancecoin':'BNB'}

def bsym(c):
    s=(c.get('symbol') or '').upper(); cid=c.get('id')
    if cid in exc: s=exc[cid]
    return s+'USDT'

def enrich(c):
    mcap=c.get('market_cap') or 0
    vol=c.get('total_volume') or 0
    turn=(vol/mcap) if mcap else 0
    pc1h=c.get('price_change_percentage_1h_in_currency')
    pc24=c.get('price_change_percentage_24h_in_currency')
    pc1h=0.0 if pc1h is None else float(pc1h)
    pc24=0.0 if pc24 is None else float(pc24)
    b=bmap.get(bsym(c))
    b_pc=None
    if b:
        try: b_pc=float(b.get('priceChangePercent'))
        except Exception: b=None
    return {
        'name':c.get('name') or '', 'sym':(c.get('symbol') or '').upper(),
        'pc1h':pc1h,'pc24':pc24,'turn':turn,
        'bin':bool(b), 'bs':bsym(c),'b_pc':b_pc,
        'vol':vol,'mcap':mcap
    }

data=[enrich(c) for c in coins]

by1h=sorted(data,key=lambda x:abs(x['pc1h']),reverse=True)[:10]
by24=sorted(data,key=lambda x:abs(x['pc24']),reverse=True)[:10]
byturn=sorted(data,key=lambda x:x['turn'],reverse=True)[:10]

print('TOP_ABS_1H')
for a in by1h:
    print(f"{a['name']} {a['sym']} 1h={a['pc1h']:.2f}% 24h={a['pc24']:.2f}% turn={a['turn']:.2f} bin={a['bin']}")
print('\nTOP_ABS_24H')
for a in by24:
    print(f"{a['name']} {a['sym']} 1h={a['pc1h']:.2f}% 24h={a['pc24']:.2f}% turn={a['turn']:.2f} bin={a['bin']}")
print('\nTOP_TURNOVER')
for a in byturn:
    print(f"{a['name']} {a['sym']} 1h={a['pc1h']:.2f}% 24h={a['pc24']:.2f}% turn={a['turn']:.2f} bin={a['bin']}")
