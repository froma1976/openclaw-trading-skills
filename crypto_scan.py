import requests
import math


def quantile(values, q):
    """Simple quantile (0..1) with linear interpolation."""
    xs = sorted(v for v in values if v is not None and not math.isnan(v))
    if not xs:
        return None
    if q <= 0:
        return xs[0]
    if q >= 1:
        return xs[-1]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def main():
    # CoinGecko top by market cap
    cg_url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 120,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h,7d",
    }
    coins = requests.get(cg_url, params=params, timeout=20).json()

    stable = {
        "usdt","usdc","dai","tusd","busd","usde","fdusd","usdd","lusd","frax",
        "pyusd","gusd","susd","eurs","usdp","usdn","ustc","mim","crvusd","usdy"
    }

    alts = []
    for c in coins:
        sym = (c.get("symbol") or "").lower()
        if sym in stable or sym in {"btc", "eth"}:
            continue
        if c.get("market_cap_rank") is None:
            continue
        alts.append({
            "symbol": sym.upper(),
            "name": c.get("name"),
            "mc_rank": c.get("market_cap_rank"),
            "cg_vol_24h": float(c.get("total_volume") or 0.0),
            "cg_chg_24h": c.get("price_change_percentage_24h_in_currency"),
        })

    alts.sort(key=lambda x: x["mc_rank"])
    alts = alts[:100]

    # Binance 24h tickers
    tickers = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=20).json()
    bmap = {t["symbol"]: t for t in tickers if isinstance(t, dict) and "symbol" in t}

    mapped = 0
    merged = []
    for a in alts:
        pair = a["symbol"] + "USDT"
        t = bmap.get(pair)
        if not t:
            continue
        mapped += 1
        try:
            qv = float(t.get("quoteVolume", 0.0))
            chg = float(t.get("priceChangePercent", 0.0))
            last = float(t.get("lastPrice", 0.0))
            high = float(t.get("highPrice", 0.0))
            low = float(t.get("lowPrice", 0.0))
            rng = (high - low) / last * 100 if last else None
        except Exception:
            continue

        cg_vol = a["cg_vol_24h"]
        vol_ratio = (qv / cg_vol) if cg_vol else None

        merged.append({
            **a,
            "pair": pair,
            "bn_quoteVol": qv,
            "bn_chg_24h": chg,
            "bn_range_pct": rng,
            "vol_ratio": vol_ratio,
        })

    print(f"TOTAL_COINS {len(alts)} BINANCE_MAPPED {mapped}")

    if not merged:
        print("OK")
        return

    qv_q3 = quantile([m["bn_quoteVol"] for m in merged], 0.75)
    if qv_q3 is None:
        print("OK")
        return

    cands = []
    for m in merged:
        if m["bn_quoteVol"] < qv_q3:
            continue
        vr = m["vol_ratio"]
        if vr is None or m["bn_range_pct"] is None:
            continue
        extreme = (
            abs(m["bn_chg_24h"]) >= 15
            or (m["bn_range_pct"] >= 20)
            or (vr >= 2.5)
            or (vr <= 0.35)
        )
        if not extreme:
            continue

        divergence = max(vr, 1.0 / vr) if vr > 0 else 0
        score = (abs(m["bn_chg_24h"]) / 10.0) + (m["bn_range_pct"] / 15.0) + (divergence / 2.0)
        m["score"] = score
        cands.append(m)

    cands.sort(key=lambda x: x["score"], reverse=True)
    cands = cands[:8]

    if not cands:
        print("OK")
        return

    for r in cands:
        cg24 = r.get("cg_chg_24h")
        cg24_s = f"{cg24:+.1f}%" if isinstance(cg24, (int, float)) else "n/a"
        print(
            f"{r['symbol']}/USDT "
            f"24h:{r['bn_chg_24h']:+.1f}% "
            f"range:{r['bn_range_pct']:.1f}% "
            f"Vol(Binance):${r['bn_quoteVol']/1e6:.1f}M "
            f"VolRatio(Bn/CG):{r['vol_ratio']:.2f} "
            f"CG24h:{cg24_s}"
        )


if __name__ == "__main__":
    main()
