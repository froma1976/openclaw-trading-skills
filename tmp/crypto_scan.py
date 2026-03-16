import requests

cg_url='https://api.coingecko.com/api/v3/coins/markets'
params={
    'vs_currency':'usd',
    'order':'market_cap_desc',
    'per_page':100,
    'page':1,
    'sparkline':'false',
    'price_change_percentage':'1h,24h,7d'
}
coins=requests.get(cg_url,params=params,timeout=30).json()

binance_url='https://api.binance.com/api/v3/ticker/24hr'
tickers=requests.get(binance_url,timeout=30).json()
bmap={t['symbol']:t for t in tickers if isinstance(t,dict) and 'symbol' in t}

exc={
    'miota':'IOTA',
    'polygon':'POL',
    'the-open-network':'TON',
    'internet-computer':'ICP',
    'filecoin':'FIL',
    'near':'NEAR',
    'okb':'OKB',
    'pepe':'PEPE',
    'first-digital-usd':'FDUSD',
    'binancecoin':'BNB'
}

def bsym(c):
    s=(c.get('symbol') or '').upper()
    cid=c.get('id')
    if cid in exc:
        s=exc[cid]
    return s+'USDT'

alerts=[]
for c in coins:
    name=c.get('name')
    sym=(c.get('symbol') or '').upper()
    mcap=c.get('market_cap') or 0
    vol=c.get('total_volume') or 0
    pc1h=c.get('price_change_percentage_1h_in_currency')
    pc24=c.get('price_change_percentage_24h_in_currency')
    turnover=(vol/mcap) if mcap else 0

    b=bmap.get(bsym(c))
    b_pc=None
    if b:
        try:
            b_pc=float(b.get('priceChangePercent'))
        except Exception:
            b=None

    extreme=(pc1h is not None and abs(pc1h)>=10) or (pc24 is not None and abs(pc24)>=20)
    hot=(pc24 is not None and abs(pc24)>=12) and turnover>=0.35
    risk=(pc24 is not None and pc24<=-15) and turnover>=0.25

    if extreme or hot or risk:
        alerts.append({
            'name':name,'sym':sym,
            'pc1h':pc1h,'pc24':pc24,
            'turn':turnover,
            'bin':bool(b),'bs':bsym(c),
            'b_pc':b_pc
        })

alerts.sort(key=lambda x:(abs(x['pc24'] or 0),abs(x['pc1h'] or 0),x['turn']),reverse=True)

print(len(alerts))
for a in alerts[:25]:
    pc1h=a['pc1h']
    pc24=a['pc24']
    print(f"{a['name']} ({a['sym']}) 1h={pc1h:.2f}% 24h={pc24:.2f}% turn={a['turn']:.2f} bin={a['bin']} {a['bs']} b24h={a['b_pc'] if a['b_pc'] is not None else 'NA'}")
