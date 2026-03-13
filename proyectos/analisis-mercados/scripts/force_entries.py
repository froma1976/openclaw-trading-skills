import json
from datetime import datetime, timezone
from pathlib import Path

base = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data")
snap_p = base / "latest_snapshot_free.json"
orders_p = base / "orders_sim.json"

snap = json.loads(snap_p.read_text(encoding="utf-8"))
market = {m.get("ticker"): m for m in snap.get("market", []) if isinstance(m, dict) and m.get("ticker")}

if orders_p.exists():
    orders = json.loads(orders_p.read_text(encoding="utf-8"))
else:
    orders = {"pending": [], "completed": []}

pending = orders.get("pending", [])
existing = {o.get("ticker") for o in pending if o.get("status") == "pending"}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

created = []
for tkr in ["XLE", "XLI"]:
    if tkr in existing:
        continue
    m = market.get(tkr, {})
    try:
        entry = float(m.get("regularMarketPrice") or m.get("lastCloseSeries"))
    except Exception:
        entry = None
    order = {
        "id": f"ord_force_{tkr.lower()}_{int(datetime.now().timestamp())}",
        "ticker": tkr,
        "score": int(m.get("score_final") or m.get("score") or 0),
        "state": "TRIGGERED",
        "status": "pending",
        "created_at": now_iso(),
        "entry_price": entry,
        "target_price": round(entry * 1.06, 4) if entry else None,
        "stop_price": round(entry * 0.97, 4) if entry else None,
        "forced": True,
        "reason": "entrada_forzada_manual"
    }
    pending.append(order)
    created.append(order)

orders["pending"] = pending
orders_p.write_text(json.dumps(orders, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"created": [c["ticker"] for c in created], "count": len(created)}, ensure_ascii=False))
