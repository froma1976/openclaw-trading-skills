import requests

BASE='https://api.binance.com'
ex=requests.get(BASE+'/api/v3/exchangeInfo',timeout=30).json()
spot=set([s['symbol'] for s in ex.get('symbols',[]) if s.get('status')=='TRADING' and s.get('isSpotTradingAllowed')])

# Map common tickers to Binance symbols (USDT pairs)
watch=['PI','TAO','TRUMP','RENDER','NIGHT','ENA','PENGU','BONK','SUI','DOGE','ZEC','WLD','VIRTUAL','WLFI']
pairs=[]
for t in watch:
    sym=t+'USDT'
    if sym in spot:
        pairs.append(sym)

# helper: last 2 hourly candles
out=[]
for sym in pairs:
    kl=requests.get(BASE+'/api/v3/klines',params={'symbol':sym,'interval':'1h','limit':2},timeout=30).json()
    if not isinstance(kl,list) or len(kl)<2:
        continue
    prev, last = kl[-2], kl[-1]
    def f(x):
        return float(x)
    prev_o, prev_c, prev_v = f(prev[1]), f(prev[4]), f(prev[5])
    last_o, last_c, last_v = f(last[1]), f(last[4]), f(last[5])
    ret = (last_c/last_o-1)*100 if last_o else 0
    vol_ratio = (last_v/prev_v) if prev_v else None
    out.append((sym, ret, vol_ratio, last_v))

# sort by abs return then by vol ratio
out_sorted=sorted(out, key=lambda x: (abs(x[1]), x[2] if x[2] is not None else 0), reverse=True)
print('BINANCE_1H_MOVERS (spot USDT pairs found)')
for sym, ret, vr, lv in out_sorted:
    vr_s = f"volx={vr:.2f}" if vr is not None else "volx=?"
    print(sym, f"1h={ret:.2f}%", vr_s)

# Flag "massive" volume divergence: volx>=2.5 and abs(ret)>=1.5
flags=[x for x in out if x[2] is not None and x[2]>=2.5 and abs(x[1])>=1.5]
print('\nBINANCE_FLAGS')
for sym, ret, vr, lv in sorted(flags, key=lambda x: (x[2], abs(x[1])), reverse=True):
    print(sym, f"1h={ret:.2f}%", f"volx={vr:.2f}")
