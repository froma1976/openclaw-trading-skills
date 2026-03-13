#!/usr/bin/env python3
import json, time
from datetime import datetime, UTC
from pathlib import Path
from urllib import request

OUT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_stream_status.json")
ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def main():
    t0 = time.perf_counter()
    ok = False
    try:
        req = request.Request("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", headers={"User-Agent": "crypto-stream-probe/1.0"})
        with request.urlopen(req, timeout=6) as r:
            _ = json.loads(r.read().decode("utf-8"))
        ok = True
    except Exception:
        ok = False
    latency_ms = int((time.perf_counter() - t0) * 1000)

    last_signal_sec = None
    try:
        if ORD.exists():
            d = json.loads(ORD.read_text(encoding="utf-8"))
            active = d.get("active", []) or []
            if active:
                ts = active[-1].get("opened_at")
                if ts:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    last_signal_sec = int((datetime.now(UTC) - dt).total_seconds())
    except Exception:
        pass

    out = {
        "ts": now_iso(),
        "stream_active": ok,
        "latency_ms": latency_ms,
        "last_signal_sec": last_signal_sec,
        "source": "binance-probe"
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
