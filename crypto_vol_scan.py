import json, math
from urllib.request import urlopen, Request
from urllib.parse import urlencode

CG_URL='https://api.coingecko.com/api/v3'
BN_URL='https://api.binance.com'

stable_syms=set('usdt usdc dai fdusd tusd busd usde usd0 usds pax gusd usdp lusd frax usdd usdn mim susd eurc eurs eurt usdg'.lower().split())

UA='Mozilla/5.0 (compatible; OpenClaw/1.0)'

def get_json(url, params=None, timeout=30, retries=3, backoff=2.0):
    if params:
        url = url + ('&' if '?' in url else '?') + urlencode(params)
    last_err=None
    for i in range(retries):
        try:
            req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last_err=e
            # simple backoff (helps with CoinGecko 429)
            import time
            time.sleep(backoff * (i+1))
    raise last_err

# 1) CoinGecko: top by market cap
coins = get_json(f'{CG_URL}/coins/markets', params={
    'vs_currency':'usd',
    'order':'market_cap_desc',
    'per_page':120,
    'page':1,
    'sparkline':'false'
}, timeout=30, retries=4, backoff=3.0)

alt=[]
for c in coins:
    sym=(c.get('symbol') or '').lower()
    if not sym:
        continue
    if sym in stable_syms:
        continue
    if sym.startswith('usd') and len(sym)<=5:
        continue
    alt.append(c)
    if len(alt)>=100:
        break

# 2) Binance: tradable symbols
ex = get_json(f'{BN_URL}/api/v3/exchangeInfo', timeout=30)
tradable=set(s['symbol'] for s in ex.get('symbols', []) if s.get('status')=='TRADING')

pairs=[]
for c in alt:
    sym=c['symbol'].upper()
    pair=sym+'USDT'
    if pair in tradable:
        pairs.append((sym, pair, c.get('market_cap') or 0))

# 3) Scan last 1h candle + volume divergence vs previous hour
alerts=[]

for sym, pair, mcap in pairs:
    try:
        k = get_json(f'{BN_URL}/api/v3/klines', params={'symbol':pair,'interval':'1h','limit':3}, timeout=20)
    except Exception:
        continue
    if not isinstance(k, list) or len(k) < 2:
        continue

    prev, cur = k[-2], k[-1]
    try:
        o_cur=float(cur[1]); c_cur=float(cur[4])
        v_cur=float(cur[5]); v_prev=float(prev[5])
    except Exception:
        continue

    ret=(c_cur/o_cur-1.0)*100 if o_cur else 0.0
    vol_ratio=(v_cur/(v_prev+1e-12)) if v_prev>0 else (math.inf if v_cur>0 else 1.0)

    if mcap>=2e9:
        move_th=6
    elif mcap>=5e8:
        move_th=8
    else:
        move_th=10

    if abs(ret) >= move_th:
        alerts.append((abs(ret), f'{sym} ({pair}) movimiento 1h {ret:+.2f}% (MCAP~${mcap/1e9:.1f}B)'))

    if vol_ratio >= 3.5 and abs(ret) >= 2.0:
        alerts.append((vol_ratio, f'{sym} ({pair}) volumen 1h x{vol_ratio:.1f} vs hora previa; precio 1h {ret:+.2f}%'))

# de-dup + top 10
seen=set(); final=[]
for score, txt in sorted(alerts, key=lambda x: x[0], reverse=True):
    if txt in seen:
        continue
    seen.add(txt)
    final.append(txt)

final = final[:10]

if not final:
    print('OK')
else:
    print('ALERTA — movimientos/volumen anómalos (última vela 1h en Binance):')
    for line in final:
        print('- ' + line)
    print('\nNotas: confirma en 15m/1h; ojo con fakeouts y reversión tras spike de volumen.')
