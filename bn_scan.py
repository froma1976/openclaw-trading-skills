import requests, re

data=requests.get('https://api.binance.com/api/v3/ticker/24hr',timeout=20).json()

# keep USDT spot pairs (exclude BTCUSDT/ETHUSDT as majors maybe still), exclude UP/DOWN/BULL/BEAR and stable-stable
bad_suffix=('UPUSDT','DOWNUSDT','BULLUSDT','BEARUSDT')
exclude={'USDCUSDT','BUSDUSDT','TUSDUSDT','FDUSDUSDT','USDPUSDT','DAIUSDT','PAXUSDT'}
rows=[]
for d in data:
    sym=d.get('symbol','')
    if not sym.endswith('USDT'): continue
    if sym in exclude: continue
    if any(sym.endswith(s) for s in bad_suffix):
        continue
    # ignore very illiquid
    try:
        qv=float(d.get('quoteVolume','0'))
        pc=float(d.get('priceChangePercent','0'))
        lp=float(d.get('lastPrice','0'))
        trades=int(d.get('count','0'))
    except Exception:
        continue
    rows.append((sym, pc, qv, lp, trades))

# rank by quoteVolume to approximate "top" coins on Binance
rows.sort(key=lambda x:x[2], reverse=True)
top=rows[:200]  # take 200 liquid usdt pairs

# find extremes: abs % change >= 12% and qv high
ext=[r for r in top if abs(r[1])>=12 and r[2]>=20_000_000]
ext.sort(key=lambda x:(abs(x[1]), x[2]), reverse=True)

# also potential volume divergence: high qv but muted move (pc small) could indicate accumulation or distribution; flag top qv with abs pc <1%
flat=[r for r in top[:50] if abs(r[1])<1 and r[2]>=200_000_000]

print('Top liquid USDT pairs scanned:',len(top))
print('\nExtreme movers (24h, liquid):',len(ext))
for sym,pc,qv,lp,tr in ext[:12]:
    print(f"{sym:12} {pc:+6.2f}% | qVol ${qv/1e6:,.0f}M | last {lp} | trades {tr:,}")

print('\nHigh-volume but flat (<1%):',len(flat))
for sym,pc,qv,lp,tr in flat[:10]:
    print(f"{sym:12} {pc:+6.2f}% | qVol ${qv/1e6:,.0f}M")
