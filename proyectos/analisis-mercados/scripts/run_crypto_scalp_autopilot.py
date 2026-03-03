#!/usr/bin/env python3
import json
from datetime import datetime, UTC, timedelta
from pathlib import Path

SNAP = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")

TARGET_PCT = 1.2
STOP_PCT = 0.7
TIMEOUT_MIN = 45
MAX_TRADES_DAY = 30


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(ts: str):
    return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))


def load_json(p: Path, default):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    snap = load_json(SNAP, {})
    if not isinstance(snap, dict):
        print("NO_SNAPSHOT")
        return

    top = snap.get("top_opportunities", []) or []
    assets = snap.get("assets", []) or []
    px = {a.get("ticker"): float(a.get("price_usd")) for a in assets if a.get("ticker") and a.get("price_usd")}

    book = load_json(ORD, {"active": [], "completed": [], "daily": {}})
    active = book.get("active", []) or []
    completed = book.get("completed", []) or []
    daily = book.get("daily", {}) or {}

    today = datetime.now(UTC).date().isoformat()
    if daily.get("date") != today:
        daily = {"date": today, "trades": 0}

    closed_now = 0
    # Close logic: target/stop/timeout
    still_active = []
    for o in active:
        t = o.get("ticker")
        cur = px.get(t)
        if cur is None:
            still_active.append(o)
            continue
        o["current_price"] = round(cur, 6)
        result = None
        if cur >= float(o.get("target_price", 0)):
            result = "ganada"
        elif cur <= float(o.get("stop_price", 0)):
            result = "perdida"
        else:
            try:
                age = datetime.now(UTC) - parse_iso(o.get("opened_at"))
                if age >= timedelta(minutes=TIMEOUT_MIN):
                    result = "timeout"
            except Exception:
                pass

        if result:
            o["closed_at"] = now_iso()
            o["close_price"] = round(cur, 6)
            o["result"] = result
            completed.append(o)
            closed_now += 1
        else:
            still_active.append(o)

    active = still_active

    opened_now = 0
    active_tickers = {o.get("ticker") for o in active}

    for c in top:
        if daily.get("trades", 0) >= MAX_TRADES_DAY:
            break
        t = c.get("ticker")
        if t in active_tickers:
            continue
        if c.get("decision_final") != "BUY":
            continue
        if c.get("state") not in {"READY", "TRIGGERED"}:
            continue
        p = px.get(t)
        if p is None:
            continue

        order = {
            "id": f"crp_{t.lower()}_{int(datetime.now().timestamp())}",
            "ticker": t,
            "opened_at": now_iso(),
            "entry_price": round(p, 6),
            "target_price": round(p * (1 + TARGET_PCT / 100), 6),
            "stop_price": round(p * (1 - STOP_PCT / 100), 6),
            "state": "ACTIVE",
            "mode": "scalp_intradia",
            "confidence": c.get("confidence_pct"),
            "score": c.get("score"),
        }
        active.append(order)
        active_tickers.add(t)
        opened_now += 1
        daily["trades"] = int(daily.get("trades", 0)) + 1

    book["active"] = active
    book["completed"] = completed[-1000:]
    book["daily"] = daily
    ORD.parent.mkdir(parents=True, exist_ok=True)
    ORD.write_text(json.dumps(book, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "opened_now": opened_now,
        "closed_now": closed_now,
        "active_total": len(active),
        "daily_trades": daily.get("trades", 0),
        "max_trades_day": MAX_TRADES_DAY,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
