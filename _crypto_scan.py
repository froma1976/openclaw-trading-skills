import json, statistics
from urllib.request import urlopen, Request
from urllib.parse import urlencode

def get_json(url, params=None, headers=None, timeout=30):
    if params:
        url = url + ('?' + urlencode(params))
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

# CoinGecko top 100 markets
url='https://api.coingecko.com/api/v3/coins/markets'
params={
 'vs_currency':'usd',
 'order':'market_cap_desc',
 'per_page':100,
 'page':1,
 'sparkline':'false',
 'price_change_percentage':'1h,24h,7d'
}
coins=get_json(url,params=params,headers={'accept':'application/json'})

rows=[]
for c in coins:
    mc=c.get('market_cap') or 0
    vol=c.get('total_volume') or 0
    v_mc=(vol/mc) if mc else 0
    rows.append({
        'id':c.get('id'),
        'name':c.get('name',''),
        'sym':(c.get('symbol','') or '').upper(),
        'rank':c.get('market_cap_rank'),
        'mc':mc,
        'vol':vol,
        'v_mc':v_mc,
        'ch1':c.get('price_change_percentage_1h_in_currency'),
        'ch24':c.get('price_change_percentage_24h_in_currency'),
        'ch7':c.get('price_change_percentage_7d_in_currency'),
    })

v_mcs=[x['v_mc'] for x in rows if x['v_mc']>0]
med=statistics.median(v_mcs) if v_mcs else 0
q90=statistics.quantiles(v_mcs,n=10)[8] if len(v_mcs)>=20 else (max(v_mcs) if v_mcs else 0)

signals=[]
for x in rows:
    ch1=float(x['ch1']) if x['ch1'] is not None else 0.0
    ch24=float(x['ch24']) if x['ch24'] is not None else 0.0
    v=float(x['v_mc'])

    move_score=0
    if abs(ch1)>=6: move_score+=3
    elif abs(ch1)>=4: move_score+=2
    elif abs(ch1)>=2.5: move_score+=1
    if abs(ch24)>=20: move_score+=3
    elif abs(ch24)>=12: move_score+=2
    elif abs(ch24)>=8: move_score+=1

    vol_score=0
    if v>=max(0.25, q90): vol_score+=3
    elif v>=max(0.15, med*2): vol_score+=2
    elif v>=max(0.10, med*1.5): vol_score+=1

    divergence=0
    if vol_score>=2 and abs(ch1)<1.0 and abs(ch24)<3.0:
        divergence=2
    if move_score>=3 and v<med*0.8:
        divergence=max(divergence,1)

    score=move_score+vol_score+divergence
    if score>=5 or (abs(ch1)>=6 and v>=0.08) or (abs(ch24)>=20):
        signals.append((score, x, ch1, ch24, v, move_score, vol_score, divergence))

signals.sort(key=lambda t:(t[0], abs(t[2])+abs(t[3]), t[4]), reverse=True)

# Binance cross-check
binance_map={}
try:
    tickers=get_json('https://api.binance.com/api/v3/ticker/24hr',headers={'accept':'application/json'})
    for t in tickers:
        s=t.get('symbol','')
        if s.endswith('USDT'):
            base=s[:-4]
            if base.endswith(('UP','DOWN','BULL','BEAR')):
                continue
            binance_map[base]=t
except Exception:
    binance_map=None

print('MED_VMC',med,'Q90_VMC',q90,'TOTAL_SIGNALS',len(signals))
for score,x,ch1,ch24,v,ms,vs,dv in signals[:12]:
    base=x['sym']
    bn=binance_map.get(base) if binance_map else None
    bn_pct=float(bn['priceChangePercent']) if bn else None
    bn_qv=float(bn['quoteVolume']) if bn else None
    bn_tr=int(float(bn['count'])) if bn else None
    print(json.dumps({
        'rank':x['rank'],
        'sym':base,
        'name':x['name'],
        'score':score,
        'ch1':ch1,
        'ch24':ch24,
        'ch7':float(x['ch7']) if x['ch7'] is not None else None,
        'v_mc':v,
        'binance': bool(bn),
        'bn24': bn_pct,
        'bnQuoteVol': bn_qv,
        'bnTrades': bn_tr,
        'reason': {'move_score':ms,'vol_score':vs,'divergence':dv}
    }))
