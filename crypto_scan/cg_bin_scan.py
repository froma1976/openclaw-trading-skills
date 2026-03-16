import requests
from statistics import mean

CG_MARKETS='https://api.coingecko.com/api/v3/coins/markets'
params={
 'vs_currency':'usd',
 'order':'market_cap_desc',
 'per_page':120,
 'page':1,
 'sparkline':'false',
 'price_change_percentage':'1h,24h'
}
coins=requests.get(CG_MARKETS,params=params,timeout=30).json()

stable_symbols={'usdt','usdc','dai','busd','tusd','fdusd','usde','ustc','lusd','pyusd','susd','usdp','eurc','usds'}
filtered=[]
for c in coins:
    sym=(c.get('symbol') or '').lower()
    if sym in {'btc','eth'}:
        continue
    if sym in stable_symbols:
        continue
    filtered.append(c)

alts=filtered[:100]

BIN_TICKER='https://api.binance.com/api/v3/ticker/24hr'
tickers=requests.get(BIN_TICKER,timeout=30).json()
usdt={t['symbol']:t for t in tickers if t.get('symbol','').endswith('USDT')}

BIN_KLINES='https://api.binance.com/api/v3/klines'
alerts=[]
sess=requests.Session()

mapping={'MIOTA':'IOTA','NANO':'XNO','MATIC':'POL'}

for c in alts:
    sym=c['symbol'].upper()
    pair=f"{sym}USDT"
    if pair not in usdt and sym in mapping:
        pair=f"{mapping[sym]}USDT"
    if pair not in usdt:
        continue

    kl=sess.get(BIN_KLINES,params={'symbol':pair,'interval':'1h','limit':25},timeout=20).json()
    if not isinstance(kl,list) or len(kl)<6:
        continue

    vols=[float(k[5]) for k in kl]
    opens=[float(k[1]) for k in kl]
    closes=[float(k[4]) for k in kl]

    last_vol=vols[-1]
    prev_vols=vols[-21:-1] if len(vols)>=21 else vols[:-1]
    avg_prev=mean(prev_vols) if prev_vols else 0.0
    vol_ratio=(last_vol/avg_prev) if avg_prev>0 else 0.0

    last_ret=(closes[-1]/opens[-1]-1)*100
    prev_ret=(closes[-2]/opens[-2]-1)*100

    mcap=c.get('market_cap') or 0
    vol24=c.get('total_volume') or 0
    vol_mcap=(vol24/mcap) if mcap else 0

    score=0
    reasons=[]

    if abs(last_ret)>=7:
        score+=3; reasons.append(f"movimiento 1h {last_ret:+.1f}%")
    elif abs(last_ret)>=5:
        score+=2; reasons.append(f"movimiento 1h {last_ret:+.1f}%")

    if vol_ratio>=6:
        score+=3; reasons.append(f"volumen 1h x{vol_ratio:.1f} vs media")
    elif vol_ratio>=4:
        score+=2; reasons.append(f"volumen 1h x{vol_ratio:.1f} vs media")
    elif vol_ratio>=3 and abs(last_ret)>=2:
        score+=1; reasons.append(f"volumen 1h x{vol_ratio:.1f} + precio")

    if (last_ret*prev_ret)<0 and abs(last_ret)>=4 and abs(prev_ret)>=4:
        score+=1; reasons.append("posible reversión (cambió el signo vs hora anterior)")

    if vol_mcap>=0.25 and abs(last_ret)>=3:
        score+=1; reasons.append(f"rotación alta (vol24/mcap {vol_mcap:.2f})")

    if score>=4:
        direction='Riesgo (dump)' if last_ret<0 else 'Oportunidad (pump/ruptura)'
        alerts.append({
            'symbol':pair,
            'name':c['name'],
            'score':score,
            'direction':direction,
            'last_ret':last_ret,
            'vol_ratio':vol_ratio,
            'reasons':reasons,
            'price_usd':c.get('current_price')
        })

alerts=sorted(alerts,key=lambda x:(-x['score'], -abs(x['last_ret']), -x['vol_ratio']))

print('ALERTS',len(alerts))
for a in alerts[:10]:
    print(a['symbol'],a['score'],a['direction'],f"1h {a['last_ret']:+.1f}%",f"vol x{a['vol_ratio']:.1f}","|".join(a['reasons']))
