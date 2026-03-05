#!/usr/bin/env python3
import csv, json
from pathlib import Path
from datetime import datetime, UTC

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
SRC = BASE / "data" / "crypto_orders_sim.json"
OUT = BASE / "data" / "trades_clean.csv"
REP = BASE / "data" / "data_quality_report.json"


def main():
    data = {"completed": []}
    if SRC.exists():
        data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = data.get("completed", []) or []

    clean = []
    seen = set()
    nulls = 0
    for r in rows:
        oid = str(r.get("id") or r.get("order_id") or "")
        sym = str(r.get("ticker") or "").upper()
        if not oid:
            oid = f"{sym}-{r.get('closed_at','')}-{r.get('entry_price','')}"
        if oid in seen:
            continue
        seen.add(oid)

        entry = r.get("entry_price")
        exitp = r.get("exit_price")
        qty = r.get("qty")
        fee = r.get("fee_usd", 0)
        side = str(r.get("side") or "BUY").upper()
        t_in = r.get("opened_at") or r.get("opened") or ""
        t_out = r.get("closed_at") or ""
        try:
            float(entry); float(exitp)
        except Exception:
            nulls += 1
            continue

        clean.append({
            "order_id": oid,
            "symbol": sym,
            "side": side,
            "timestamp_entry": t_in,
            "timestamp_exit": t_out,
            "entry_price": float(entry),
            "exit_price": float(exitp),
            "qty": float(qty or 0),
            "fee_usd": float(fee or 0),
            "pnl_usd": float(r.get("pnl_usd") or 0),
            "source": "sim_orders"
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(clean[0].keys()) if clean else ["order_id"])
        w.writeheader()
        if clean:
            w.writerows(clean)

    rep = {
        "as_of": datetime.now(UTC).isoformat(),
        "source": str(SRC),
        "rows_raw": len(rows),
        "rows_clean": len(clean),
        "duplicates_removed": len(rows) - len(seen),
        "rows_dropped_nulls": nulls,
        "output": str(OUT)
    }
    REP.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
