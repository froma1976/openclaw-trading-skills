import requests

N=100
vs='usd'

cg_markets='https://api.coingecko.com/api/v3/coins/markets'
params={
    'vs_currency':vs,
    'order':'market_cap_desc',
    'per_page':N,
    'page':1,
    'sparkline':'false',
    'price_change_percentage':'1h,24h'
}

cg = requests.get(cg_markets, params=params, timeout=20)
cg.raise_for_status()
coins=cg.json()

bn_url='https://api.binance.com/api/v3/ticker/24hr'
bn = requests.get(bn_url, timeout=20)
bn.raise_for_status()
tickers=bn.json()
bn_map={t['symbol']:t for t in tickers}

def bn_symbol(symbol:str):
    base=symbol.upper()
    for quote in ['USDT','FDUSD','BUSD','USDC','TUSD']:
        s=base+quote
        if s in bn_map:
            return s
    return None

alerts=[]
for c in coins:
    sym=c['symbol']
    name=c['name']
    p1h=c.get('price_change_percentage_1h_in_currency')
    p24=c.get('price_change_percentage_24h_in_currency')
    vol=c.get('total_volume') or 0

    bs=bn_symbol(sym)
    if not bs:
        continue
    t=bn_map[bs]
    try:
        bn_pchg=float(t['priceChangePercent'])
        bn_qvol=float(t['quoteVolume'])
        last=float(t['lastPrice'])
        high=float(t['highPrice']); low=float(t['lowPrice'])
    except Exception:
        continue

    move=max(abs(bn_pchg), abs(p24 or 0))
    imp=abs(p1h or 0)
    rng=(high-low)/last*100 if last else 0

    div=None
    if p24 is not None:
        div=abs(bn_pchg - p24)

    vol_ratio=None
    if vol and bn_qvol:
        vol_ratio=bn_qvol/vol

    score=0
    reasons=[]
    if move>=15:
        score+=3; reasons.append(f"mov 24h {bn_pchg:.1f}% (BN) / {p24:.1f}% (CG)" if p24 is not None else f"mov 24h {bn_pchg:.1f}%")
    elif move>=10:
        score+=2; reasons.append(f"mov 24h {bn_pchg:.1f}% (BN) / {p24:.1f}% (CG)" if p24 is not None else f"mov 24h {bn_pchg:.1f}%")

    if imp>=5:
        score+=2; reasons.append(f"impulso 1h {p1h:.1f}%")
    elif imp>=3:
        score+=1; reasons.append(f"impulso 1h {p1h:.1f}%")

    if rng>=12:
        score+=2; reasons.append(f"rango 24h {rng:.1f}%")
    elif rng>=8:
        score+=1; reasons.append(f"rango 24h {rng:.1f}%")

    if div is not None and div>=6:
        score+=2; reasons.append(f"divergencia %24h BN vs CG {div:.1f}pp")
    elif div is not None and div>=4:
        score+=1; reasons.append(f"divergencia %24h BN vs CG {div:.1f}pp")

    if vol_ratio is not None:
        if vol_ratio>=2.5:
            score+=2; reasons.append(f"volumen BN/CG {vol_ratio:.1f}x")
        elif vol_ratio<=0.35:
            score+=1; reasons.append(f"volumen BN/CG {vol_ratio:.2f}x (BN bajo vs CG)")

    liquid = bn_qvol>=20_000_000

    if score>=5 and liquid:
        alerts.append((score, name, sym.upper(), bs, bn_pchg, p24, p1h, bn_qvol, rng, div, vol_ratio, reasons))

alerts.sort(key=lambda x:(-x[0], -abs(x[4])))

print(len(alerts))
for a in alerts[:12]:
    score,name,base,bs,bn_pchg,p24,p1h,bn_qvol,rng,div,vol_ratio,reasons=a
    p24v=p24 if p24 is not None else float('nan')
    p1hv=p1h if p1h is not None else float('nan')
    divv=div if div is not None else float('nan')
    vr=vol_ratio if vol_ratio is not None else float('nan')
    print(f"{name} ({base}) [{bs}] score={score} | BN24h={bn_pchg:.1f}% CG24h={p24v:.1f}% CG1h={p1hv:.1f}% | qVol=${bn_qvol/1e6:.0f}M | range={rng:.1f}% | div={divv:.1f}pp | volRatio={vr:.2f} | {', '.join(reasons)}")
