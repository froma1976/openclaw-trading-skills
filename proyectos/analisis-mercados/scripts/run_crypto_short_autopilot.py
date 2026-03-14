#!/usr/bin/env python3
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import run_crypto_scalp_autopilot as longmod
import source_ingest_crypto_short

from runtime_utils import atomic_write_json, file_lock, round_price


SNAP = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_short.json")
ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_short_orders_sim.json")
LEARN = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/learning_status_short.json")
RISK_CFG = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/config/risk_short.yaml")
LOCK = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/locks/crypto_short_runtime.lock")


def read_simple_yaml(path: Path):
    def parse_scalar(raw_value: str):
        value = str(raw_value or "").strip().strip('"').strip("'")
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        try:
            return float(value) if "." in value else int(value)
        except Exception:
            return value

    data = {}
    parent = None
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.rstrip()
        if not raw or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  ") and parent and ":" in raw:
            k, v = raw.strip().split(":", 1)
            data.setdefault(parent, {})[k.strip()] = parse_scalar(v)
            continue
        if ":" in raw:
            k, v = raw.split(":", 1)
            k = k.strip()
            v = v.strip()
            if not v:
                parent = k
                data[k] = {}
            else:
                parent = None
                if v.lower() in {"true", "false"}:
                    data[k] = v.lower() == "true"
                else:
                    data[k] = parse_scalar(v)
    return data


def load_short_risk():
    cfg = {
        "capital_base_usd": 300.0,
        "slippage_bps": 5,
        "fee_bps": 10,
        "target_pct": 1.0,
        "stop_pct": 0.65,
        "min_target_net_pct": 0.5,
        "min_expected_net_profit_usd": 0.25,
        "timeout_min": 15,
        "timeout_force_close_min": 40,
        "max_trades_day": 120,
        "max_trades_hour": 30,
        "max_active_positions": 8,
        "alloc_per_trade_usd": 30.0,
        "max_alloc_per_trade_usd": 60.0,
        "min_notional_usd": 10.0,
        "normal_min_score": 72,
        "defensive_min_score": 78,
        "defensive_min_confluence": 2,
        "allowed_hours_utc": {"start": "00:00", "end": "23:59"},
    }
    if RISK_CFG.exists():
        cfg.update(read_simple_yaml(RISK_CFG))
    return cfg


def breakeven_buyback(entry_price: float, qty: float, fee_open_usd: float, fee_bps: float) -> float:
    entry = float(entry_price or 0)
    units = float(qty or 0)
    if entry <= 0 or units <= 0:
        return entry
    return ((entry * units) - max(0.0, float(fee_open_usd or 0))) / (units * (1.0 + float(fee_bps or 0) / 10000.0))


def estimate_short_economics(entry_price: float, target_price: float, notional: float, fee_bps: float, slippage_bps: float):
    entry = float(entry_price or 0)
    target = float(target_price or 0)
    cash = float(notional or 0)
    if entry <= 0 or target >= entry or cash <= 0:
        return {"net_profit_usd": 0.0, "net_return_pct": 0.0}
    qty = cash / entry
    cover_px = target * (1 + float(slippage_bps or 0) / 10000.0)
    gross_profit = max(0.0, (entry - cover_px) * qty)
    fee_open = cash * float(fee_bps or 0) / 10000.0
    fee_close = max(0.0, cover_px * qty * float(fee_bps or 0) / 10000.0)
    net_profit = gross_profit - fee_open - fee_close
    return {"net_profit_usd": round(net_profit, 6), "net_return_pct": round((net_profit / cash) * 100.0, 4)}


def compute_learning(completed: list[dict]):
    now = datetime.now(UTC)
    d7 = now - timedelta(days=7)
    rows = []
    for row in completed:
        try:
            if longmod.parse_iso(row.get("closed_at")) >= d7:
                rows.append(row)
        except Exception:
            continue
    wins = sum(1 for row in rows if float(row.get("pnl_usd") or 0) > 0)
    losses = sum(1 for row in rows if float(row.get("pnl_usd") or 0) < 0)
    pnl = round(sum(float(row.get("pnl_usd") or 0) for row in rows), 6)
    n = len(rows)
    profit_sum = sum(max(0.0, float(row.get("pnl_usd") or 0)) for row in rows)
    loss_sum = abs(sum(min(0.0, float(row.get("pnl_usd") or 0)) for row in rows))
    return {
        "as_of": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "trades_7d": n,
        "wins_7d": wins,
        "losses_7d": losses,
        "win_rate": round((wins / n) * 100.0, 2) if n else 0.0,
        "expectancy_usd": round(pnl / n, 4) if n else 0.0,
        "profit_factor": round(profit_sum / loss_sum, 3) if loss_sum else 0.0,
        "pnl_7d_usd": pnl,
        "semaforo": "VERDE" if n >= 10 and pnl > 0 else "ROJO",
        "reason": "Edge short en observacion" if n else "Sin datos todavia",
    }


def main():
    try:
        with file_lock(LOCK, stale_seconds=900, wait_seconds=0):
            _main_locked()
    except RuntimeError:
        print("LOCK_BUSY crypto_short_runtime")


def _main_locked():
    cfg = load_short_risk()
    source_ingest_crypto_short.main()
    snap = longmod.load_json(SNAP, {})
    top = list((snap.get("top_opportunities") or [])[:25])
    book = longmod.load_json(ORD, {"active": [], "completed": [], "daily": {}, "portfolio": {}})
    active = book.get("active", []) or []
    completed = book.get("completed", []) or []
    daily = book.get("daily", {}) or {}
    portfolio = book.get("portfolio", {}) or {}
    capital_base = float(cfg.get("capital_base_usd", 300.0) or 300.0)
    if not portfolio:
        portfolio = {"capital_initial_usd": capital_base, "cash_usd": capital_base, "market_value_usd": 0.0, "equity_usd": capital_base}

    slippage_bps = float(cfg.get("slippage_bps", 5) or 5)
    fee_bps = float(cfg.get("fee_bps", 10) or 10)
    target_pct = float(cfg.get("target_pct", 1.0) or 1.0)
    stop_pct = float(cfg.get("stop_pct", 0.65) or 0.65)
    min_target_net_pct = float(cfg.get("min_target_net_pct", 0.5) or 0.5)
    min_expected_net_profit_usd = float(cfg.get("min_expected_net_profit_usd", 0.25) or 0.25)
    timeout_min = int(cfg.get("timeout_min", 15) or 15)
    timeout_force_close_min = int(cfg.get("timeout_force_close_min", 40) or 40)
    normal_min_score = int(cfg.get("normal_min_score", 72) or 72)
    defensive_min_score = int(cfg.get("defensive_min_score", 78) or 78)
    min_confluence_def = int(cfg.get("defensive_min_confluence", 2) or 2)
    alloc_per_trade = float(cfg.get("alloc_per_trade_usd", 30.0) or 30.0)
    max_alloc = float(cfg.get("max_alloc_per_trade_usd", 60.0) or 60.0)
    min_notional = float(cfg.get("min_notional_usd", 10.0) or 10.0)
    max_active = int(cfg.get("max_active_positions", 8) or 8)

    today = datetime.now(UTC).date().isoformat()
    daily.setdefault("date", today)
    daily.setdefault("trades", 0)
    daily.setdefault("loss_streak", 0)

    # manage active shorts
    still = []
    for order in active:
        cur = None
        for row in snap.get("assets", []) or []:
            if str(row.get("ticker") or "") == str(order.get("ticker") or ""):
                cur = float(row.get("price_usd") or 0)
                break
        if not cur or cur <= 0:
            still.append(order)
            continue
        qty = float(order.get("qty") or 0)
        entry = float(order.get("entry_price") or 0)
        fee_open = float(order.get("fee_open_usd") or 0)
        exit_fee_est = cur * qty * fee_bps / 10000.0
        order["current_price"] = round(cur, 8)
        order["pnl_usd_est"] = round(((entry - cur) * qty) - fee_open - exit_fee_est, 6)
        be = breakeven_buyback(entry, qty, fee_open, fee_bps)
        order["breakeven_price"] = round_price(be)
        if cur <= be < float(order.get("stop_price") or 999999):
            order["stop_price"] = round_price(be)

        result = None
        if cur <= float(order.get("target_price") or 0):
            result = "ganada"
        elif cur >= float(order.get("stop_price") or 0):
            result = "perdida"
        else:
            age = datetime.now(UTC) - longmod.parse_iso(order.get("opened_at"))
            if age >= timedelta(minutes=timeout_force_close_min) or (age >= timedelta(minutes=timeout_min) and float(order.get("pnl_usd_est") or 0) <= 0):
                result = "timeout"

        if not result:
            still.append(order)
            continue

        cover_px = cur * (1 + slippage_bps / 10000.0)
        gross = (entry - cover_px) * qty
        fee_close = cover_px * qty * fee_bps / 10000.0
        pnl = gross - fee_open - fee_close
        order["closed_at"] = longmod.now_iso()
        order["close_price"] = round_price(cover_px)
        order["exit_price"] = order["close_price"]
        order["gross_pnl_usd"] = round(gross, 6)
        order["fee_usd"] = round(fee_open + fee_close, 6)
        order["pnl_usd"] = round(pnl, 6)
        order["result"] = result
        order["state"] = "CLOSED"
        portfolio["cash_usd"] = round(float(portfolio.get("cash_usd", 0)) + float(order.get("notional_usd") or 0) + pnl, 6)
        daily["loss_streak"] = int(daily.get("loss_streak", 0)) + 1 if pnl < 0 else 0
        completed.append(order)

    active = still
    daily_pnl = sum(float(o.get("pnl_usd") or 0) for o in completed if str(o.get("closed_at") or "")[:10] == today)
    mode_state = longmod.compute_mode(daily, daily_pnl, cfg, capital_base)
    mode = mode_state.get("mode", "normal")
    risk_blocked = bool(mode_state.get("risk_blocked")) or bool(mode_state.get("paused"))
    daily.update({"mode": mode_state.get("mode"), "mode_reason": mode_state.get("mode_reason"), "paused": mode_state.get("paused"), "pause_reason": mode_state.get("pause_reason"), "paused_at": daily.get("paused_at") or (longmod.now_iso() if mode_state.get("paused") else "")})

    for candidate in top:
        if risk_blocked or len(active) >= max_active:
            break
        if candidate.get("decision_short") != "SELL_SHORT":
            continue
        if candidate.get("state_short") not in {"READY", "TRIGGERED"}:
            continue
        ticker = str(candidate.get("ticker") or "")
        if not ticker or any(str(o.get("ticker") or "") == ticker for o in active):
            continue
        score = int(candidate.get("score_short") or 0)
        confluence = int(candidate.get("spy_confluence") or 0)
        if score < normal_min_score:
            continue
        if mode == "defensive" and (score < defensive_min_score or confluence < min_confluence_def):
            continue
        price = float(candidate.get("price_usd") or 0)
        if price <= 0:
            continue
        cash = float(portfolio.get("cash_usd") or 0)
        notional = min(alloc_per_trade, cash, max_alloc)
        if notional < min_notional:
            continue
        entry_px = price * (1 - slippage_bps / 10000.0)
        target_px = round_price(entry_px * (1 - target_pct / 100.0))
        stop_px = round_price(entry_px * (1 + stop_pct / 100.0))
        economics = estimate_short_economics(entry_px, target_px, notional, fee_bps, slippage_bps)
        if economics["net_return_pct"] < min_target_net_pct:
            continue
        required_notional = max(min_notional, min_expected_net_profit_usd / max(economics["net_return_pct"] / 100.0, 1e-9))
        if required_notional > notional:
            notional = min(required_notional, cash, max_alloc)
            if notional < required_notional:
                continue
            economics = estimate_short_economics(entry_px, target_px, notional, fee_bps, slippage_bps)
            if economics["net_profit_usd"] < min_expected_net_profit_usd:
                continue
        qty = notional / entry_px
        fee_open = notional * fee_bps / 10000.0
        active.append({
            "id": f"crs_{ticker.lower()}_{int(datetime.now().timestamp())}",
            "ticker": ticker,
            "opened_at": longmod.now_iso(),
            "entry_price": round_price(entry_px),
            "qty": round(qty, 8),
            "notional_usd": round(notional, 2),
            "target_price": target_px,
            "stop_price": stop_px,
            "state": "ACTIVE",
            "mode": "short_intradia",
            "risk_mode": mode,
            "confidence": score,
            "score": score,
            "side": "SHORT",
            "spy_confluence": confluence,
            "setup_tag": candidate.get("setup_tag") or "short_base",
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
            "fee_open_usd": round(fee_open, 6),
            "expected_target_net_profit_usd": economics["net_profit_usd"],
            "expected_target_net_pct": economics["net_return_pct"],
        })
        portfolio["cash_usd"] = round(float(portfolio.get("cash_usd", 0)) - notional - fee_open, 6)
        daily["trades"] = int(daily.get("trades", 0)) + 1

    market_value = sum(float(o.get("notional_usd") or 0) for o in active)
    portfolio["market_value_usd"] = round(market_value, 6)
    portfolio["realized_pnl_usd"] = round(sum(float(o.get("pnl_usd") or 0) for o in completed), 6)
    portfolio["equity_usd"] = round(float(portfolio.get("cash_usd", 0)) + market_value, 6)

    book = {"active": active, "completed": completed[-1000:], "daily": daily, "portfolio": portfolio}
    atomic_write_json(ORD, book)
    learn = compute_learning(completed)
    atomic_write_json(LEARN, learn)
    source_ingest_crypto_short.main()
    print(json.dumps({"opened_now": max(0, len(active)), "closed_total": len(completed), "mode": mode, "cash_usd": portfolio.get("cash_usd"), "equity_usd": portfolio.get("equity_usd")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
