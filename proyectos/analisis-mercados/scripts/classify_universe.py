#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
EDGE = BASE / "reports" / "edge_breakdown.json"
OUT = BASE / "data" / "universe_status.json"

MANUAL_EXCLUDED = {"PEPE"}
STABLECOINS = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE"}


def classify(row: dict):
    ticker = str(row.get("key") or "?").upper()
    count = int(row.get("count") or 0)
    win_rate = float(row.get("win_rate") or 0)
    expectancy = float(row.get("expectancy_usd") or 0)
    pnl = float(row.get("pnl_usd") or 0)

    if ticker in MANUAL_EXCLUDED or ticker in STABLECOINS:
        return "excluded", "exclusion manual o activo no operativo"
    if count < 5:
        return "watch", "muestra insuficiente"
    if count >= 15 and expectancy > 0.015 and win_rate >= 52 and pnl > 0:
        return "core", "edge suficiente en ventana reciente"
    if count >= 10 and (expectancy < 0 or win_rate < 35):
        return "excluded", "deterioro claro en ventana reciente"
    return "watch", "seguir observando antes de promover o expulsar"


def main():
    data = {"by_ticker": []}
    if EDGE.exists():
        data = json.loads(EDGE.read_text(encoding="utf-8"))

    core = []
    watch = []
    excluded = []
    details = []

    for row in data.get("by_ticker", []):
        bucket, reason = classify(row)
        item = {
            "ticker": str(row.get("key") or "?").upper(),
            "bucket": bucket,
            "reason": reason,
            "count": int(row.get("count") or 0),
            "win_rate": float(row.get("win_rate") or 0),
            "expectancy_usd": float(row.get("expectancy_usd") or 0),
            "pnl_usd": float(row.get("pnl_usd") or 0),
        }
        details.append(item)
        if bucket == "core":
            core.append(item["ticker"])
        elif bucket == "watch":
            watch.append(item["ticker"])
        else:
            excluded.append(item["ticker"])

    out = {
        "as_of": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "policy": {
            "core": "count>=15, expectancy>0.015, win_rate>=52, pnl>0",
            "watch": "muestra insuficiente o edge mixed",
            "excluded": "manual/stablecoin o count>=10 con expectancy<0 o win_rate<35",
        },
        "core": core,
        "watch": watch,
        "excluded": sorted(set(excluded + list(MANUAL_EXCLUDED) + list(STABLECOINS))),
        "details": details,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
