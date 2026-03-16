import requests, re

headers={'User-Agent':'OpenClaw-Cron/1.0'}
url='https://api.binance.com/api/v3/ticker/24hr'
resp=requests.get(url,headers=headers,timeout=30)
resp.raise_for_status()
tickers=resp.json()

# keep USDT spot pairs, exclude leveraged tokens and obvious stables
bad_suffix=('UPUSDT','DOWNUSDT','BULLUSDT','BEARUSDT')
stable_bases={'USDT','USDC','FDUSD','DAI','TUSD','USDP','BUSD'}
majors={'BTC','ETH'}

def is_spot_symbol(s):
    return s.endswith('USDT') and not any(s.endswith(x) for x in bad_suffix)

def base_asset(symbol):
    return symbol[:-4]

rows=[]
for t in tickers:
    if not isinstance(t,dict):
        continue
    sym=t.get('symbol')
    if not sym or not is_spot_symbol(sym):
        continue
    base=base_asset(sym)
    if base in stable_bases or base in majors:
        continue
    try:
        pc=float(t.get('priceChangePercent'))
        qv=float(t.get('quoteVolume'))
        tr=int(t.get('count'))
    except Exception:
        continue
    rows.append({'sym':sym,'base':base,'pc':pc,'qv':qv,'trades':tr})

# approximate "top 100" as highest quote volume USDT pairs
rows.sort(key=lambda x:x['qv'],reverse=True)
top=rows[:100]

# find extreme movers with meaningful liquidity
candidates=[r for r in top if abs(r['pc'])>=12]
candidates.sort(key=lambda x:(abs(x['pc']), x['qv']), reverse=True)

print('TOP100_COUNT',len(top))
print('EXTREME_COUNT',len(candidates))
for r in candidates[:15]:
    print(f"{r['sym']} 24h={r['pc']:+.2f}% qVol={r['qv']:.0f} trades={r['trades']}")

# also flag: very high volume but flat price (possible absorption/distribution)
flat=[r for r in top if abs(r['pc'])<=1.0]
flat.sort(key=lambda x:x['qv'],reverse=True)
print('\nHIGH_VOL_FLAT')
for r in flat[:10]:
    print(f"{r['sym']} 24h={r['pc']:+.2f}% qVol={r['qv']:.0f}")
