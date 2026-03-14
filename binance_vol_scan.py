import requests, math, statistics

bn_url='https://api.binance.com/api/v3/ticker/24hr'
tickers=requests.get(bn_url, timeout=30).json()

rows=[]
for t in tickers:
    sym=t.get('symbol','')
    if not sym.endswith('USDT'): 
        continue
    base=sym[:-4]
    # skip leveraged/meme multipliers and stable pairs
    if base.endswith(('UP','DOWN','BULL','BEAR')):
        continue
    if base in {'USDT','USDC','FDUSD','TUSD','DAI','USDE','PYUSD'}:
        continue
    try:
        ch=float(t.get('priceChangePercent') or 0)
        qv=float(t.get('quoteVolume') or 0)
        trades=float(t.get('count') or 0)
    except Exception:
        continue
    if qv<5_000_000: # ignore illiquid
        continue
    rows.append({'pair':sym,'base':base,'ch24':ch,'qv':qv,'trades':trades})

if not rows:
    print('NO_DATA')
    raise SystemExit

# z-scores
abs_ch=[abs(r['ch24']) for r in rows]
log_qv=[math.log10(r['qv']+1) for r in rows]

def z(x, arr):
    mu=statistics.mean(arr)
    sd=statistics.pstdev(arr) or 1
    return (x-mu)/sd

for r in rows:
    r['z_move']=z(abs(r['ch24']),abs_ch)
    r['z_vol']=z(math.log10(r['qv']+1),log_qv)
    # high vol with low move = "absorption" watchlist
    r['absorption']= r['z_vol'] - r['z_move']
    # breakout = both high
    r['breakout']= r['z_vol'] + r['z_move']

# Top movers
big_up=sorted([r for r in rows if r['ch24']>0], key=lambda r:r['ch24'], reverse=True)[:8]
big_dn=sorted([r for r in rows if r['ch24']<0], key=lambda r:r['ch24'])[:8]
# Volume leaders
vol_lead=sorted(rows, key=lambda r:r['qv'], reverse=True)[:8]
# Absorption candidates
absorb=sorted(rows, key=lambda r:r['absorption'], reverse=True)[:8]
# Breakout candidates
breakout=sorted(rows, key=lambda r:r['breakout'], reverse=True)[:8]

print('TOP_UP')
for r in big_up:
    print(f"{r['pair']}: {r['ch24']:+.1f}% | qVol ${r['qv']/1e6:.0f}M")
print('TOP_DOWN')
for r in big_dn:
    print(f"{r['pair']}: {r['ch24']:+.1f}% | qVol ${r['qv']/1e6:.0f}M")
print('TOP_VOL')
for r in vol_lead:
    print(f"{r['pair']}: qVol ${r['qv']/1e6:.0f}M | 24h {r['ch24']:+.1f}%")
print('ABSORPTION')
for r in absorb:
    print(f"{r['pair']}: qVol ${r['qv']/1e6:.0f}M | 24h {r['ch24']:+.1f}%")
print('BREAKOUT')
for r in breakout:
    print(f"{r['pair']}: qVol ${r['qv']/1e6:.0f}M | 24h {r['ch24']:+.1f}%")
