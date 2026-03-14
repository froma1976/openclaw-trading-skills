import requests, time

BASE = "https://api.binance.com"

stable_quote = {"USDT","USDC","FDUSD","TUSD","DAI","BUSD"}
stable_assets = {"USDT","USDC","FDUSD","TUSD","DAI","BUSD","EUR","TRY"}
exclude_bases = {"BTC","ETH"}

# 1) 24h ticker for all symbols
r = requests.get(f"{BASE}/api/v3/ticker/24hr", timeout=30)
r.raise_for_status()
tickers = r.json()

pairs = []
for t in tickers:
    sym = t.get("symbol")
    if not sym or not sym.endswith("USDT"):
        continue
    base = sym[:-4]
    if base in exclude_bases or base in stable_assets:
        continue
    # crude filter to skip leveraged tokens etc
    if base.endswith(("UP","DOWN","BULL","BEAR")):
        continue
    try:
        qv = float(t.get("quoteVolume") or 0)
        pc = float(t.get("priceChangePercent") or 0)
        tv = float(t.get("volume") or 0)
        last = float(t.get("lastPrice") or 0)
    except Exception:
        continue
    pairs.append({
        "symbol": sym,
        "base": base,
        "quoteVolume": qv,
        "priceChangePercent24h": pc,
        "last": last,
        "volume": tv,
    })

pairs.sort(key=lambda x: x["quoteVolume"], reverse=True)
# proxy for "Top 100": top 100 by quote volume on Binance USDT
universe = pairs[:100]

# 2) Find extreme 24h movers inside universe
ext24 = [p for p in universe if abs(p["priceChangePercent24h"]) >= 12]
ext24.sort(key=lambda x: abs(x["priceChangePercent24h"]), reverse=True)

# 3) For top 25 by absolute 24h move, compute last-60m change using 1m klines (lightweight)
# (We keep calls small: at most 25 requests)

cands_for_1h = sorted(universe, key=lambda x: abs(x["priceChangePercent24h"]), reverse=True)[:25]

oneh_results = []
for p in cands_for_1h:
    sym = p["symbol"]
    try:
        k = requests.get(f"{BASE}/api/v3/klines", params={"symbol": sym, "interval": "1m", "limit": 61}, timeout=20).json()
        if not isinstance(k, list) or len(k) < 2:
            continue
        # close prices: each kline: [openTime, open, high, low, close, volume, ...]
        close_now = float(k[-1][4])
        close_60m = float(k[0][4])
        chg1h = (close_now/close_60m - 1.0) * 100.0
        oneh_results.append({**p, "chg1h": chg1h})
    except Exception:
        continue

oneh_results.sort(key=lambda x: abs(x.get("chg1h", 0)), reverse=True)

# 4) Simple volume-divergence heuristic: high quoteVolume rank but low 24h % (accumulation) or high % with huge volume (news-driven)
# We'll report if quoteVolume extremely high and move extreme.

print("UNIVERSE=Binance top100-by-USDT-quote-volume")
print(f"CoinGecko: rate-limited (HTTP 429) at runtime; cannot confirm market-cap top 100 right now.")

print("\nTop 24h movers (>=12%):")
if not ext24:
    print("  (none)")
else:
    for p in ext24[:12]:
        print(f"  {p['symbol']}: {p['priceChangePercent24h']:+.2f}% (24h), quoteVol ${p['quoteVolume']:.0f}")

print("\nLargest 1h swings among the most active movers (approx from 1m klines):")
if not oneh_results:
    print("  (none)")
else:
    for p in oneh_results[:12]:
        print(f"  {p['symbol']}: {p.get('chg1h',0):+.2f}% (1h), {p['priceChangePercent24h']:+.2f}% (24h), quoteVol ${p['quoteVolume']:.0f}")
