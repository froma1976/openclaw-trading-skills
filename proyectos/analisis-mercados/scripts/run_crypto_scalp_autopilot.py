#!/usr/bin/env python3
import json
from datetime import datetime, UTC, timedelta
from pathlib import Path

SNAP = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")

TARGET_PCT = 0.9
STOP_PCT = 0.55
TIMEOUT_MIN = 12
MAX_TRADES_DAY = 120
MAX_TRADES_HOUR = 30
DAILY_LOSS_LIMIT_USD = 18.0
CRYPTO_CAPITAL_INITIAL_USD = 300.0
MAX_ACTIVE_POSITIONS = 10
ALLOC_PER_TRADE_USD = 30.0


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

    book = load_json(ORD, {"active": [], "completed": [], "daily": {}, "portfolio": {}})
    active = book.get("active", []) or []
    completed = book.get("completed", []) or []
    daily = book.get("daily", {}) or {}
    portfolio = book.get("portfolio", {}) or {}

    if not portfolio:
        portfolio = {
            "capital_initial_usd": CRYPTO_CAPITAL_INITIAL_USD,
            "cash_usd": CRYPTO_CAPITAL_INITIAL_USD,
        }

    today = datetime.now(UTC).date().isoformat()
    if daily.get("date") != today:
        daily = {"date": today, "trades": 0, "loss_streak": 0, "paused": False, "pause_reason": ""}
    if "loss_streak" not in daily:
        daily["loss_streak"] = 0
    if "paused" not in daily:
        daily["paused"] = False
    if "pause_reason" not in daily:
        daily["pause_reason"] = ""

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
            try:
                qty = float(o.get("qty") or 0)
                entry = float(o.get("entry_price") or 0)
                pnl = (cur - entry) * qty
            except Exception:
                pnl = 0.0
            o["pnl_usd"] = round(pnl, 6)
            portfolio["cash_usd"] = float(portfolio.get("cash_usd", 0)) + float(o.get("notional_usd", 0)) + pnl
            if result == "perdida" or pnl < 0:
                daily["loss_streak"] = int(daily.get("loss_streak", 0)) + 1
            else:
                daily["loss_streak"] = 0
            completed.append(o)
            closed_now += 1
        else:
            still_active.append(o)

    active = still_active

    opened_now = 0
    active_tickers = {o.get("ticker") for o in active}

    now = datetime.now(UTC)
    one_hour_ago = now - timedelta(hours=1)

    def to_dt(v):
        try:
            return parse_iso(v)
        except Exception:
            return None

    hour_trades = 0
    for o in active:
        d = to_dt(o.get("opened_at"))
        if d and d >= one_hour_ago:
            hour_trades += 1
    for o in completed:
        d = to_dt(o.get("closed_at"))
        if d and d >= one_hour_ago:
            hour_trades += 1

    daily_pnl = 0.0
    for o in completed:
        d = to_dt(o.get("closed_at"))
        if d and d.date().isoformat() == today:
            try:
                daily_pnl += float(o.get("pnl_usd") or 0)
            except Exception:
                pass

    risk_blocked = daily_pnl <= (-DAILY_LOSS_LIMIT_USD)
    if int(daily.get("loss_streak", 0)) >= 3:
        daily["paused"] = True
        daily["pause_reason"] = "3 pérdidas seguidas"
    if risk_blocked:
        daily["paused"] = True
        daily["pause_reason"] = "límite de pérdida diaria"

    for c in top:
        if daily.get("trades", 0) >= MAX_TRADES_DAY:
            break
        if hour_trades >= MAX_TRADES_HOUR:
            break
        if risk_blocked or bool(daily.get("paused")):
            break
        if len(active) >= MAX_ACTIVE_POSITIONS:
            break
        t = c.get("ticker")
        if t in active_tickers:
            continue
        if c.get("decision_final") != "BUY":
            continue
        if c.get("state") not in {"READY", "TRIGGERED"}:
            continue

        # Red de espías (modo más activo): confluencia mínima + confirmación chart/breakout
        confluence = int(c.get("spy_confluence") or 0)
        breakout = int(c.get("spy_breakout") or 0)
        chart = int(c.get("spy_chart") or 0)
        if confluence < 1:
            continue
        if max(breakout, chart) <= 0:
            continue

        p = px.get(t)
        if p is None:
            continue

        cash = float(portfolio.get("cash_usd", 0))
        notional = min(ALLOC_PER_TRADE_USD, cash)
        if notional < 20:
            continue
        qty = notional / p

        order = {
            "id": f"crp_{t.lower()}_{int(datetime.now().timestamp())}",
            "ticker": t,
            "opened_at": now_iso(),
            "entry_price": round(p, 6),
            "qty": round(qty, 8),
            "notional_usd": round(notional, 2),
            "target_price": round(p * (1 + TARGET_PCT / 100), 6),
            "stop_price": round(p * (1 - STOP_PCT / 100), 6),
            "state": "ACTIVE",
            "mode": "scalp_intradia",
            "confidence": c.get("confidence_pct"),
            "score": c.get("score"),
            "spy_confluence": confluence,
            "spy_breakdown": {
                "news": c.get("spy_news"),
                "euphoria": c.get("spy_euphoria"),
                "flow": c.get("spy_flow"),
                "whale": c.get("spy_whale"),
            },
        }
        active.append(order)
        portfolio["cash_usd"] = round(float(portfolio.get("cash_usd", 0)) - notional, 2)
        active_tickers.add(t)
        opened_now += 1
        hour_trades += 1
        daily["trades"] = int(daily.get("trades", 0)) + 1

    active_value = 0.0
    for o in active:
        t = o.get("ticker")
        cp = px.get(t)
        if cp is not None:
            try:
                active_value += float(o.get("qty", 0)) * float(cp)
            except Exception:
                pass

    portfolio["market_value_usd"] = round(active_value, 2)
    portfolio["equity_usd"] = round(float(portfolio.get("cash_usd", 0)) + active_value, 2)

    book["active"] = active
    book["completed"] = completed[-1000:]
    book["daily"] = daily
    book["portfolio"] = portfolio
    ORD.parent.mkdir(parents=True, exist_ok=True)
    ORD.write_text(json.dumps(book, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "opened_now": opened_now,
        "closed_now": closed_now,
        "active_total": len(active),
        "daily_trades": daily.get("trades", 0),
        "max_trades_day": MAX_TRADES_DAY,
        "hour_trades": hour_trades,
        "max_trades_hour": MAX_TRADES_HOUR,
        "daily_pnl_usd": round(daily_pnl, 4),
        "daily_loss_limit_usd": DAILY_LOSS_LIMIT_USD,
        "risk_blocked": risk_blocked,
        "paused": bool(daily.get("paused")),
        "pause_reason": daily.get("pause_reason", ""),
        "loss_streak": int(daily.get("loss_streak", 0)),
        "cash_usd": portfolio.get("cash_usd", 0),
        "equity_usd": portfolio.get("equity_usd", 0),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
