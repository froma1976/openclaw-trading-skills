#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from urllib import request
from datetime import datetime, UTC

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
OUT = BASE / "data" / "history" / "public_ohlcv"

SYMBOLS = ["BTCUSDT", "SOLUSDT", "ETHUSDT"]
INTERVAL = "d"


def try_download(url: str):
    req = request.Request(url, headers={"User-Agent": "openclaw-public-ohlcv/1.0"})
    with request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="ignore")


def parse_cdd_csv(raw: str):
    # CryptoDataDownload files often include comment/header line starting with '#'
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not ln.startswith("#")]
    if lines and lines[0].lower().startswith("http"):
        lines = lines[1:]
    if not lines:
        return []

    reader = csv.DictReader(lines)
    out = []
    for r in reader:
        # normalize key case
        rr = {str(k).strip().lower(): v for k, v in r.items()}
        if not rr.get("open") or not rr.get("close"):
            continue
        try:
            ts = rr.get("unix") or ""
            out.append({
                "timestamp": ts,
                "open": float(rr.get("open")),
                "high": float(rr.get("high")),
                "low": float(rr.get("low")),
                "close": float(rr.get("close")),
                "volume": float(rr.get("volume usdt") or rr.get("volume") or 0),
                "symbol": rr.get("symbol") or "",
            })
        except Exception:
            continue
    # CDD often newest-first; normalize oldest-first
    out.sort(key=lambda x: int(float(x["timestamp"])) if str(x["timestamp"]).strip() else 0)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"as_of": datetime.now(UTC).isoformat(), "ok": True, "sources": []}

    for sym in SYMBOLS:
        # Common CryptoDataDownload naming for Binance spot pairs
        url = f"https://www.cryptodatadownload.com/cdd/Binance_{sym}_{INTERVAL}.csv"
        target = OUT / f"{sym}_{INTERVAL}.csv"
        try:
            raw = try_download(url)
            rows = parse_cdd_csv(raw)
            if not rows:
                raise RuntimeError("empty_or_unparsed")

            with target.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close", "volume", "symbol"])
                w.writeheader()
                w.writerows(rows)

            report["sources"].append({"symbol": sym, "url": url, "rows": len(rows), "file": str(target), "ok": True})
        except Exception as e:
            report["sources"].append({"symbol": sym, "url": url, "ok": False, "error": str(e)})

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
