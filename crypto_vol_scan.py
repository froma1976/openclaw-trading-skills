import requests, time, math
from datetime import datetime

CG_BASE = 'https://api.coingecko.com/api/v3'
STABLE_IDS = {
    'tether','usd-coin','dai','true-usd','pax-dollar','binance-usd','frax','first-digital-usd','usdd',
    'paypal-usd','gemini-dollar','usdc','usdt','tusd','busd','usdp','lusd','usde','fdusd'
}
STABLE_SYMS = {'USDT','USDC','DAI','BUSD','TUSD','FDUSD','USDE'}

sess = requests.Session()
sess.headers.update({'User-Agent':'openclaw-volatility/1.0'})

# 1) Top coins by market cap (CoinGecko)
coins = []
for page in (1, 2):
    r = sess.get(
        f"{CG_BASE}/coins/markets",
        params={
            'vs_currency':'usd',
            'order':'market_cap_desc',
            'per_page':250,
            'page':page,
            'sparkline':'false',
            'price_change_percentage':'1h,24h'
        },
        timeout=25
    )
    r.raise_for_status()
    coins.extend(r.json())

filtered = []
for c in coins:
    if c.get('id') in STABLE_IDS:
        continue
    if (c.get('symbol') or '').upper() in STABLE_SYMS:
        continue
    filtered.append(c)

filtered = sorted(filtered, key=lambda x: x.get('market_cap_rank') or 10**9)[:100]

# 2) Binance symbols universe
exinfo = sess.get('https://api.binance.com/api/v3/exchangeInfo', timeout=30).json()
trading = {s['symbol'] for s in exinfo.get('symbols', []) if s.get('status') == 'TRADING'}

def pick_binance_symbol(sym: str):
    sym = sym.upper()
    repl = {'MIOTA':'IOTA', 'XBT':'BTC'}
    sym = repl.get(sym, sym)
    for cand in (sym+'USDT', sym+'FDUSD', sym+'USDC', sym+'BUSD'):
        if cand in trading:
            return cand
    return None

mapped = [(c, pick_binance_symbol(c['symbol'])) for c in filtered]

# 3) Binance 24h stats (single call)
stats = sess.get('https://api.binance.com/api/v3/ticker/24hr', timeout=30).json()
stats_by = {s['symbol']: s for s in stats if isinstance(s, dict) and 'symbol' in s}

def fnum(x):
    try:
        return float(x)
    except Exception:
        return float('nan')

# Preselect coins to limit kline calls
cands = []
for c, b in mapped:
    if not b:
        continue
    s = stats_by.get(b)
    if not s:
        continue
    oneh = c.get('price_change_percentage_1h_in_currency')
    oneh = float(oneh) if oneh is not None else 0.0
    qv = fnum(s.get('quoteVolume'))
    cands.append((abs(oneh), qv, c, b, oneh))

by1h = sorted(cands, key=lambda t: t[0], reverse=True)[:35]
byqv = sorted(cands, key=lambda t: t[1], reverse=True)[:35]
sel = {t[3] for t in (by1h + byqv)}
sel_list = [t for t in cands if t[3] in sel]

alerts = []
now_ms = int(time.time() * 1000)
for _, _, c, b, oneh in sel_list:
    try:
        kl = sess.get(
            'https://api.binance.com/api/v3/klines',
            params={'symbol': b, 'interval': '1h', 'limit': 4},
            timeout=20
        ).json()
        if not isinstance(kl, list) or len(kl) < 3:
            continue

        last = kl[-1]
        # if last kline already closed, use it, otherwise use the previous closed one
        idx = -1 if now_ms > int(last[6]) + 2000 else -2

        cur = kl[idx]
        prev = kl[idx - 1]

        cur_o, cur_c = float(cur[1]), float(cur[4])
        cur_v = float(cur[5])
        prev_o, prev_c = float(prev[1]), float(prev[4])
        prev_v = float(prev[5])

        hour_chg = (cur_c / cur_o - 1) * 100 if cur_o else 0.0
        vr = (cur_v / prev_v) if prev_v > 0 else (math.inf if cur_v > 0 else 1.0)

        s = stats_by.get(b, {})
        pchg24 = fnum(s.get('priceChangePercent'))

        extreme = abs(hour_chg) >= 6 or abs(oneh) >= 6 or (pchg24 == pchg24 and abs(pchg24) >= 18)
        voldiv = (vr >= 3)

        if extreme or (abs(hour_chg) >= 3 and voldiv):
            alerts.append({
                'name': c['name'],
                'symbol': c['symbol'].upper(),
                'binance': b,
                'hour_chg': hour_chg,
                'oneh_cg': oneh,
                'pchg24': pchg24,
                'vr': vr,
            })
    except Exception:
        continue

# scoring
for a in alerts:
    score = 0.0
    score += min(10.0, abs(a['hour_chg']) / 2)
    if a['pchg24'] == a['pchg24']:
        score += min(6.0, abs(a['pchg24']) / 6)
    vr = a['vr']
    score += (8.0 if vr == math.inf else min(8.0, math.log(vr + 1, 2)))
    a['score'] = score

alerts = sorted(alerts, key=lambda x: x['score'], reverse=True)

if not alerts:
    print('OK')
    raise SystemExit

alerts = alerts[:7]
print('ALERTA (Top divergencias/movimientos, CoinGecko + Binance)')
print('Hora: ' + datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z'))
print('')
for a in alerts:
    vr = a['vr']
    vr_s = '∞' if vr == math.inf else f"{vr:.1f}x"
    p = a['pchg24']
    p_s = 'n/a' if p != p else f"{p:+.1f}%"
    print(f"- {a['name']} ({a['symbol']}) [{a['binance']}] | 1h(candle): {a['hour_chg']:+.1f}% | 1h(CG): {a['oneh_cg']:+.1f}% | 24h: {p_s} | Vol spike vs prev 1h: {vr_s}")

print('\nLectura trader (heurística):')
print('- 1h fuerte + Vol spike >=3x: posible breakout/breakdown; ojo fakeout, confirmar con cierres 15m/1h.')
print('- 24h extremo (>18%): riesgo de mean reversion; ajustar tamaño / usar stops.')
