#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

from runtime_utils import atomic_write_json, make_exit_levels, round_price

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ORD = BASE / "data" / "crypto_orders_sim.json"
BACKUP_DIR = BASE / "data" / "order_backups"


def now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def infer_setup_tag(order: dict) -> str:
    breakout = int(order.get("spy_breakout") or 0)
    chart = int(order.get("spy_chart") or 0)
    breakdown = order.get("spy_breakdown") or {}
    flow = int(breakdown.get("flow") or 0)
    news = int(breakdown.get("news") or 0)
    whale = int(breakdown.get("whale") or 0)
    euphoria = int(breakdown.get("euphoria") or 0)
    if breakout > 0 and chart > 0:
        return "breakout_trend"
    if breakout > 0:
        return "breakout"
    if chart > 0 and flow > 0:
        return "trend_flow"
    if whale > 0 and flow > 0:
        return "whale_flow"
    if news > 0 and euphoria <= 0:
        return "news_reversal"
    if flow > 0:
        return "flow_momentum"
    return "base"


def main():
    if not ORD.exists():
        print(json.dumps({"ok": False, "error": "orders file not found", "path": str(ORD)}, ensure_ascii=False))
        return

    raw = ORD.read_text(encoding="utf-8")
    data = json.loads(raw)
    completed = data.get("completed", []) or []
    active = data.get("active", []) or []
    portfolio = data.get("portfolio", {}) or {}
    changes = {
        "completed_state_fixed": 0,
        "exit_price_filled": 0,
        "close_price_filled": 0,
        "side_defaulted": 0,
        "target_stop_rebuilt": 0,
        "fees_backfilled": 0,
        "portfolio_reconciled": 0,
    }

    for order in completed + active:
        if str(order.get("state") or "").upper() == "ACTIVE":
            if order in completed:
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
        if order.get("opened_hour_utc") in (None, ""):
            opened_at = str(order.get("opened_at") or "")
            if len(opened_at) >= 13:
                order["opened_hour_utc"] = opened_at[11:13]
        if order.get("setup_tag") in (None, ""):
            order["setup_tag"] = infer_setup_tag(order)
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
        try:
            entry = float(order.get("entry_price") or 0)
            target = float(order.get("target_price") or 0)
            stop = float(order.get("stop_price") or 0)
            if entry > 0 and (target <= stop or target <= entry or stop >= entry):
                new_target, new_stop = make_exit_levels(entry, order.get("target_pct") or 0.9, order.get("stop_pct") or 0.55)
                order["target_price"] = new_target
                order["stop_price"] = new_stop
                changes["target_stop_rebuilt"] += 1
        except Exception:
            pass
        try:
            entry = float(order.get("entry_price") or 0)
            close_price = float(order.get("close_price") or order.get("exit_price") or 0)
            qty = float(order.get("qty") or 0)
            if qty > 0 and order in completed:
                fee_open = float(order.get("fee_open_usd") or 0)
                fee_total = order.get("fee_usd")
                if fee_total in (None, ""):
                    fee_close = abs(close_price * qty) * float(order.get("fee_bps") or 10) / 10000.0
                    fee_total = fee_open + fee_close
                    order["fee_usd"] = round(fee_total, 6)
                    changes["fees_backfilled"] += 1
                order["entry_price"] = round_price(entry)
                if close_price > 0:
                    order["close_price"] = round_price(close_price)
                    order["exit_price"] = order["close_price"]
                order.setdefault("gross_pnl_usd", round((close_price - entry) * qty, 6))
                order["pnl_usd"] = round(float(order.get("gross_pnl_usd") or 0) - float(order.get("fee_usd") or 0), 6)
        except Exception:
            pass

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"crypto_orders_sim_{now_stamp()}.json"
    backup_path.write_text(raw, encoding="utf-8")

    capital_initial = float(portfolio.get("capital_initial_usd") or portfolio.get("capital_base_usd") or 300.0)
    realized = round(sum(float(o.get("pnl_usd") or 0) for o in completed), 6)
    active_notional = round(sum(float(o.get("notional_usd") or 0) for o in active), 6)
    active_value = 0.0
    for order in active:
        px = float(order.get("current_price") or order.get("entry_price") or 0)
        qty = float(order.get("qty") or 0)
        active_value += px * qty
    cash = round(capital_initial + realized - active_notional, 6)
    equity = round(cash + active_value, 6)
    portfolio["capital_initial_usd"] = capital_initial
    portfolio["realized_pnl_usd"] = realized
    portfolio["cash_usd"] = cash
    portfolio["market_value_usd"] = round(active_value, 6)
    portfolio["equity_usd"] = equity
    portfolio["equity_reconciled_usd"] = equity
    portfolio["active_notional_usd"] = active_notional
    portfolio["fees_paid_usd"] = round(sum(float(o.get("fee_usd") or o.get("fee_open_usd") or 0) for o in completed + active), 6)
    data["portfolio"] = portfolio
    changes["portfolio_reconciled"] = 1

    atomic_write_json(ORD, data)
    print(json.dumps({"ok": True, "backup": str(backup_path), "changes": changes, "completed": len(completed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
