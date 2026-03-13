import json
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from statistics import mean

UA='Mozilla/5.0 (OpenClaw)'

def get_json(url, params=None, timeout=30):
    if params:
        url = url + ('?' + urlencode(params))
    req=Request(url, headers={'User-Agent': UA})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

bt=get_json('https://api.binance.com/api/v3/ticker/24hr')
# USDT spot pairs, exclude leveraged tokens
rows=[]
for t in bt:
    s=t['symbol']
    if not s.endswith('USDT'): 
        continue
    if any(s.endswith(x) for x in ['UPUSDT','DOWNUSDT','BULLUSDT','BEARUSDT']):
        continue
    try:
        rows.append({
            'symbol':s,
            'lastPrice':float(t['lastPrice']),
            'priceChangePercent':float(t['priceChangePercent']),
            'quoteVolume':float(t['quoteVolume'])
        })
    except Exception:
        pass

rows.sort(key=lambda r:r['quoteVolume'], reverse=True)

def klines(symbol, interval='1h', limit=24):
    return get_json('https://api.binance.com/api/v3/klines', params={'symbol':symbol,'interval':interval,'limit':limit})

alerts=[]
TOP=40
for r in rows[:TOP]:
    s=r['symbol']
    ch24=r['priceChangePercent']
    bvol=r['quoteVolume']

    vol_ratio=0
    last_ret=0
    last_vol=0
    try:
        ks=klines(s,'1h',24)
        vols=[float(k[7]) for k in ks]
        rets=[(float(k[4])-float(k[1]))/float(k[1])*100 for k in ks]
        last_vol=vols[-1]
        prev_avg=mean(vols[:-1]) if len(vols)>1 else 0
        vol_ratio=(last_vol/prev_avg) if prev_avg>0 else 0
        last_ret=rets[-1]
    except Exception:
        pass

    reasons=[]
    score=0
    if abs(ch24)>=15 and bvol>30_000_000:
        reasons.append(f"24h {ch24:+.1f}% con vol alto")
        score+=2
    if abs(last_ret)>=3 and vol_ratio>=3 and last_vol>5_000_000:
        reasons.append(f"última 1h {last_ret:+.1f}% con spike vol x{vol_ratio:.1f}")
        score+=3

    if score>=3:
        alerts.append({
            'symbol':s,
            'price':r['lastPrice'],
            'ch24':ch24,
            'bvol':bvol,
            'reasons':reasons
        })

alerts.sort(key=lambda a:(len(a['reasons']), abs(a['ch24']), a['bvol']), reverse=True)

print(len(alerts))
for a in alerts[:10]:
    print(f"{a['symbol']} | Px {a['price']:.6g} | 24h {a['ch24']:+.1f}% | Vol24h ${a['bvol']/1e6:.0f}M | {'; '.join(a['reasons'])}")
