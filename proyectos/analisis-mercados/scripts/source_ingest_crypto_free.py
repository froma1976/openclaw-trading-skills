#!/usr/bin/env python3
import json
from datetime import datetime, UTC
from pathlib import Path
from urllib import request

OUT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
COINS = ["bitcoin", "ethereum", "solana"]
SYMBOL = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}


def get_json(url: str):
    req = request.Request(url, headers={"User-Agent": "crypto-scout/1.0"})
    with request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ids = ",".join(COINS)
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false&price_change_percentage=24h,7d"
    )
    rows = get_json(url)
    assets = []
    for r in rows:
        p = float(r.get("current_price") or 0)
        ch24 = float(r.get("price_change_percentage_24h") or 0)
        ch7 = float(r.get("price_change_percentage_7d_in_currency") or 0)
        score = 50
        if ch24 > 1:
            score += 10
        if ch7 > 3:
            score += 18
        if ch24 < -2:
            score -= 12
        if ch7 < -5:
            score -= 18
        score = max(0, min(100, int(round(score))))
        state = "WATCH"
        if score >= 65:
            state = "READY"
        if score >= 78:
            state = "TRIGGERED"
        assets.append({
            "id": r.get("id"),
            "ticker": SYMBOL.get(r.get("id"), str(r.get("symbol", "")).upper()),
            "name": r.get("name"),
            "price_usd": p,
            "chg_24h_pct": round(ch24, 2),
            "chg_7d_pct": round(ch7, 2),
            "score": score,
            "state": state,
            "decision_final": "BUY" if score >= 80 else ("HOLD" if score >= 60 else "AVOID"),
            "argumento_en_contra": "Volatilidad alta de cripto; usar tamaño pequeño",
        })

    top = sorted(assets, key=lambda x: x["score"], reverse=True)
    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "assets": assets,
        "top_opportunities": top,
        "source": "coingecko-free",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK crypto snapshot -> {OUT}")


if __name__ == "__main__":
    main()
