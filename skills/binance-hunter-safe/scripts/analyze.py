#!/usr/bin/env python3
import json
import sys
from urllib import request


def get_json(url: str):
    req = request.Request(url, headers={"User-Agent": "binance-hunter-safe/1.0"})
    with request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT").upper().replace("/", "")

    ticker = get_json(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}")
    klines = get_json(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=40")

    closes = [float(k[4]) for k in klines]
    vols = [float(k[5]) for k in klines]

    p_now = float(ticker.get("lastPrice") or 0)
    chg = float(ticker.get("priceChangePercent") or 0)
    vol_q = float(ticker.get("quoteVolume") or 0)

    ma9 = sum(closes[-9:]) / 9 if len(closes) >= 9 else p_now
    ma21 = sum(closes[-21:]) / 21 if len(closes) >= 21 else p_now
    v_now = sum(vols[-5:]) / 5 if len(vols) >= 5 else 0
    v_ref = sum(vols[-20:-5]) / 15 if len(vols) >= 20 else (v_now or 1)

    bias = "ALCISTA" if (p_now > ma9 > ma21) else ("BAJISTA" if (p_now < ma9 < ma21) else "LATERAL")
    flow = "FUERTE" if v_now > v_ref * 1.4 else ("MEDIO" if v_now > v_ref else "DÉBIL")

    out = {
        "symbol": symbol,
        "price": round(p_now, 6),
        "change_24h_pct": round(chg, 2),
        "quote_volume": round(vol_q, 2),
        "ma9": round(ma9, 6),
        "ma21": round(ma21, 6),
        "bias": bias,
        "flow": flow,
        "note": "SOLO LECTURA (sin órdenes)",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
