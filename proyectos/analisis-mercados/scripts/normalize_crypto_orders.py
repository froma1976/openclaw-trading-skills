#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ORD = BASE / "data" / "crypto_orders_sim.json"
BACKUP_DIR = BASE / "data" / "order_backups"


def now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def main():
    if not ORD.exists():
        print(json.dumps({"ok": False, "error": "orders file not found", "path": str(ORD)}, ensure_ascii=False))
        return

    raw = ORD.read_text(encoding="utf-8")
    data = json.loads(raw)
    completed = data.get("completed", []) or []
    changes = {
        "completed_state_fixed": 0,
        "exit_price_filled": 0,
        "close_price_filled": 0,
        "side_defaulted": 0,
    }

    for order in completed:
        if str(order.get("state") or "").upper() == "ACTIVE":
            order["state"] = "CLOSED"
            changes["completed_state_fixed"] += 1
        if order.get("exit_price") in (None, "") and order.get("close_price") not in (None, ""):
            order["exit_price"] = order.get("close_price")
            changes["exit_price_filled"] += 1
        if order.get("close_price") in (None, "") and order.get("exit_price") not in (None, ""):
            order["close_price"] = order.get("exit_price")
            changes["close_price_filled"] += 1
        if order.get("side") in (None, ""):
            order["side"] = "BUY"
            changes["side_defaulted"] += 1
        if order.get("qty") in (None, ""):
            try:
                entry = float(order.get("entry_price") or 0)
                notional = float(order.get("notional_usd") or 0)
                if entry > 0 and notional > 0:
                    order["qty"] = round(notional / entry, 8)
                else:
                    order["qty"] = 0.0
            except Exception:
                order["qty"] = 0.0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"crypto_orders_sim_{now_stamp()}.json"
    backup_path.write_text(raw, encoding="utf-8")

    ORD.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "backup": str(backup_path), "changes": changes, "completed": len(completed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
