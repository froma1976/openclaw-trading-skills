import requests, statistics, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

COINGECKO = 'https://api.coingecko.com/api/v3/coins/markets'
BINANCE_KLINES = 'https://api.binance.com/api/v3/klines'

SESSION = requests.Session()
SESSION.headers.update({'User-Agent':'Mozilla/5.0'})

def fetch_json(url, params=None, timeout=20):
    for attempt in range(4):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                time.sleep(1.0*(attempt+1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 3:
                return None
            time.sleep(0.7*(attempt+1))
    return None

def get_top100_altcoins():
    params = {
        'vs_currency':'usd',
        'order':'market_cap_desc',
        'per_page':100,
        'page':1,
        'sparkline':'false',
        'price_change_percentage':'1h,24h,7d'
    }
    data = fetch_json(COINGECKO, params=params)
    if not data:
        return []
    stables = {'usdt','usdc','dai','busd','tusd','fdusd','usde','susde','usdd','lusd','frax','pyusd','usd0','usds'}
    out=[]
    for c in data:
        sym = (c.get('symbol') or '').lower()
        if sym in {'btc','eth'}:
            continue
        if sym in stables:
            continue
        if (c.get('name','').lower().endswith(' usd')):
            continue
        out.append({
            'symbol':sym,
            'name':c.get('name'),
            'mcap_rank':c.get('market_cap_rank'),
            'cg_1h':c.get('price_change_percentage_1h_in_currency'),
            'cg_24h':c.get('price_change_percentage_24h_in_currency'),
        })
    return out

def analyze_klines(kl):
    if not kl or len(kl) < 3:
        return None
    closes=[float(x[4]) for x in kl]
    vols=[float(x[5]) for x in kl]
    last=closes[-1]; prev=closes[-2]
    chg1h=(last/prev-1)*100
    vol_last=vols[-1]
    vol_med=statistics.median(vols[:-1]) if len(vols)>1 else vol_last
    base=closes[-7] if len(closes)>=7 else closes[0]
    chg6h=(last/base-1)*100
    vol_ratio = vol_last/(vol_med if vol_med>0 else 1)
    return {'chg1h': chg1h,'chg6h': chg6h,'vol_ratio': vol_ratio}

def fetch_binance_klines(symbol):
    pair = symbol.upper()+'USDT'
    params={'symbol':pair,'interval':'1h','limit':24}
    data = fetch_json(BINANCE_KLINES, params=params)
    if isinstance(data, dict) and 'code' in data:
        return None
    return pair, data

def main():
    top = get_top100_altcoins()
    if not top:
        print('OK'); return

    results=[]
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(fetch_binance_klines, c['symbol']): c for c in top}
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                res = fut.result()
            except Exception:
                continue
            if not res:
                continue
            pair, kl = res
            a = analyze_klines(kl)
            if not a:
                continue
            results.append({**c,'pair':pair,**a})

    alerts=[]
    for r in results:
        chg1h=r['chg1h']; vr=r['vol_ratio']; chg6h=r['chg6h']
        score=0; tags=[]
        if abs(chg1h) >= 8:
            score += 4; tags.append(f"MOV1h {chg1h:+.1f}%")
        elif abs(chg1h) >= 5:
            score += 2; tags.append(f"mov1h {chg1h:+.1f}%")

        if vr >= 6:
            score += 4; tags.append(f"VOLx{vr:.1f}")
        elif vr >= 4:
            score += 3; tags.append(f"volx{vr:.1f}")
        elif vr >= 3:
            score += 2; tags.append(f"volx{vr:.1f}")

        if vr >= 4 and abs(chg1h) < 1.2:
            score += 2; tags.append('diverg(Vol>>Price)')

        if chg1h > 5 and chg6h > 12:
            score += 2; tags.append(f"extended6h {chg6h:+.1f}%")
        if chg1h < -5 and vr >= 3:
            score += 1; tags.append('selloff+vol')

        if score >= 6:
            alerts.append((score, r, tags))

    alerts.sort(key=lambda x:(-x[0], -abs(x[1]['chg1h']), -x[1]['vol_ratio']))

    if not alerts:
        print('OK'); return

    now = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
    print(f"ALERTA Crypto (Top100 alt, CoinGecko+Binance) — {now}")
    print("Señales: movimiento 1h extremo y/o spike de volumen 1h vs mediana 24h (vela 1h puede estar en curso).\n")

    for score, r, tags in alerts[:8]:
        cg1h=r.get('cg_1h'); cg24=r.get('cg_24h')
        cg1h_s = f"CG1h {cg1h:+.1f}%" if isinstance(cg1h,(int,float)) and cg1h==cg1h else "CG1h n/d"
        cg24_s = f"CG24h {cg24:+.1f}%" if isinstance(cg24,(int,float)) and cg24==cg24 else "CG24h n/d"

        if r['vol_ratio']>=4 and abs(r['chg1h'])<1.2:
            direction = 'Atención (absorción/rotación)'
        else:
            direction = 'Riesgo (dump)' if r['chg1h']<0 else 'Oportunidad/Breakout'

        print(f"- {r['pair']} ({r['name']}, rank#{r['mcap_rank']}) | {direction}")
        print(f"  Binance: 1h {r['chg1h']:+.2f}%, 6h {r['chg6h']:+.2f}%, VolSpike x{r['vol_ratio']:.1f}")
        print(f"  CoinGecko: {cg1h_s}, {cg24_s} | Tags: {', '.join(tags)} | Score {score}")

    print("\nChecklist: confirmar en 5m/15m (ruptura de rango + nivel). Si es spike de volumen sin movimiento, vigilar fakeout; usar stops y tamaño pequeño.")

if __name__ == '__main__':
    main()
