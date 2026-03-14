import requests

tickers = requests.get('https://api.binance.com/api/v3/ticker/24hr', timeout=30).json()

stables = {'USDT','USDC','FDUSD','TUSD','DAI','USDE','USDD','USDP','BUSD','PYUSD','EUR','TRY'}
exclude = {'BTC','ETH'}

rows = []
for t in tickers if isinstance(tickers, list) else []:
    s = t.get('symbol','')
    if not s.endswith('USDT'):
        continue
    base = s[:-4]
    if base in exclude or base in stables:
        continue

    pch = float(t.get('priceChangePercent','nan'))
    qv = float(t.get('quoteVolume','nan'))
    trades = int(float(t.get('count',0)))
    last = t.get('lastPrice')

    if qv < 20_000_000:
        continue

    score = 0
    if abs(pch) >= 20:
        score += 3
    elif abs(pch) >= 15:
        score += 2
    elif abs(pch) >= 10:
        score += 1

    if qv >= 300_000_000:
        score += 2
    elif qv >= 100_000_000:
        score += 1

    if trades >= 200_000:
        score += 1

    if score >= 4:
        rows.append((score, base, pch, qv, trades, last))

rows.sort(key=lambda x: (-x[0], -abs(x[2]), -x[3]))

print('N_ALERTS', len(rows))
for score, base, pch, qv, trades, last in rows[:15]:
    print(f"{score} {base}/USDT | {pch:+.2f}% | vol ${qv/1e6:.0f}M | trades {trades:,} | last {last}")
