#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ORD = BASE / "data" / "crypto_orders_sim.json"
OUT = BASE / "data" / "orders_schema_audit.json"


def read_orders():
    data = {"active": [], "completed": [], "daily": {}, "portfolio": {}}
    if ORD.exists():
        data = json.loads(ORD.read_text(encoding="utf-8"))
    return data


def main():
    data = read_orders()
    active = data.get("active", []) or []
    completed = data.get("completed", []) or []
    issues = {
        "completed_state_active": 0,
        "missing_close_price": 0,
        "missing_entry_price": 0,
        "missing_qty": 0,
        "missing_closed_at": 0,
        "stablecoin_symbols": 0,
        "missing_result": 0,
    }
    by_ticker = {}
    examples = []
    stablecoin_prefixes = ("USDC", "USDT", "BUSD", "FDUSD", "TUSD")

    for order in completed:
        ticker = str(order.get("ticker") or "?").upper()
        by_ticker.setdefault(ticker, {"count": 0, "pnl_usd": 0.0, "issues": 0})
        by_ticker[ticker]["count"] += 1
        by_ticker[ticker]["pnl_usd"] += float(order.get("pnl_usd") or 0)

        local_issues = []
        if str(order.get("state") or "").upper() == "ACTIVE":
            issues["completed_state_active"] += 1
            local_issues.append("state_active")
        if order.get("close_price") in (None, "") and order.get("exit_price") in (None, ""):
            issues["missing_close_price"] += 1
            local_issues.append("missing_close_price")
        if order.get("entry_price") in (None, ""):
            issues["missing_entry_price"] += 1
            local_issues.append("missing_entry_price")
        if order.get("qty") in (None, ""):
            issues["missing_qty"] += 1
            local_issues.append("missing_qty")
        if order.get("closed_at") in (None, ""):
            issues["missing_closed_at"] += 1
            local_issues.append("missing_closed_at")
        if ticker.startswith(stablecoin_prefixes):
            issues["stablecoin_symbols"] += 1
            local_issues.append("stablecoin_symbol")
        if order.get("result") in (None, ""):
            issues["missing_result"] += 1
            local_issues.append("missing_result")

        by_ticker[ticker]["issues"] += len(local_issues)
        if local_issues and len(examples) < 15:
            examples.append({
                "id": order.get("id"),
                "ticker": ticker,
                "issues": local_issues,
            })

    out = {
        "as_of": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "path": str(ORD),
        "active_count": len(active),
        "completed_count": len(completed),
        "issues": issues,
        "top_issue_tickers": sorted(
            [{"ticker": k, **v} for k, v in by_ticker.items()],
            key=lambda x: (-x["issues"], -abs(x["pnl_usd"]), x["ticker"]),
        )[:20],
        "examples": examples,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
