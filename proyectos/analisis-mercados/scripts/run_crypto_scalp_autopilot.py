#!/usr/bin/env python3
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

SNAP = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")
RISK_CFG = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/config/risk.yaml")
UNIVERSE_STATUS = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/universe_status.json")

TARGET_PCT = 0.9
STOP_PCT = 0.55
TIMEOUT_MIN = 12
MAX_TRADES_DAY = 120
MAX_TRADES_HOUR = 30
CRYPTO_CAPITAL_INITIAL_USD = 300.0
MAX_ACTIVE_POSITIONS = 10
ALLOC_PER_TRADE_USD = 30.0


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(ts: str):
    return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def parse_scalar(raw: str):
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    lower = value.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except Exception:
        return value


def load_risk_config():
    cfg = {
        "capital_base_usd": CRYPTO_CAPITAL_INITIAL_USD,
        "max_daily_loss_pct": 5.0,
        "defensive_after_consecutive_losses": 2,
        "pause_after_consecutive_losses": 3,
        "pause_hours": 24,
        "target_pct": TARGET_PCT,
        "stop_pct": STOP_PCT,
        "timeout_min": TIMEOUT_MIN,
        "max_trades_day": MAX_TRADES_DAY,
        "max_trades_hour": MAX_TRADES_HOUR,
        "max_active_positions": MAX_ACTIVE_POSITIONS,
        "alloc_per_trade_usd": ALLOC_PER_TRADE_USD,
        "min_notional_usd": 20.0,
        "defensive_scale": 0.5,
        "defensive_min_score": 82,
        "defensive_min_confluence": 2,
        "allowed_symbols": [],
        "excluded_symbols": [],
        "allowed_hours_utc": {"start": "00:00", "end": "23:59"},
        "execution_mode": "sim_only",
    }
    if not RISK_CFG.exists():
        return cfg

    section = None
    for line in RISK_CFG.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped.startswith("- ") and section in {"allowed_symbols", "excluded_symbols"}:
            cfg[section].append(str(parse_scalar(stripped[2:])).upper())
            continue
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if indent == 0:
            section = key if not raw_value else None
            if key in {"allowed_symbols", "excluded_symbols"}:
                cfg[key] = []
                continue
            if key == "allowed_hours_utc":
                section = key
                continue
            if raw_value:
                cfg[key] = parse_scalar(raw_value)
        elif section == "allowed_hours_utc" and key in {"start", "end"}:
            cfg["allowed_hours_utc"][key] = str(parse_scalar(raw_value))
    return cfg


def load_universe_status():
    data = load_json(UNIVERSE_STATUS, {})
    return {
        "core": {str(x).upper() for x in (data.get("core") or [])},
        "watch": {str(x).upper() for x in (data.get("watch") or [])},
        "excluded": {str(x).upper() for x in (data.get("excluded") or [])},
    }


def allowed_now(cfg: dict, now: datetime) -> bool:
    hours = cfg.get("allowed_hours_utc") or {}
    start = str(hours.get("start") or "00:00")
    end = str(hours.get("end") or "23:59")
    current = now.strftime("%H:%M")
    return start <= current <= end


def compute_mode(daily: dict, daily_pnl: float, cfg: dict, capital_base_usd: float):
    loss_streak = int(daily.get("loss_streak", 0) or 0)
    pause_after = int(cfg.get("pause_after_consecutive_losses", 3) or 3)
    defensive_after = int(cfg.get("defensive_after_consecutive_losses", max(1, pause_after - 1)) or max(1, pause_after - 1))
    max_daily_loss_pct = float(cfg.get("max_daily_loss_pct", 5.0) or 5.0)
    daily_loss_limit_usd = round(capital_base_usd * max_daily_loss_pct / 100.0, 4)
    risk_blocked = daily_pnl <= (-daily_loss_limit_usd)

    mode = "normal"
    mode_reason = "operativa normal"
    paused = False
    pause_reason = ""

    if risk_blocked:
        mode = "paused"
        mode_reason = "limite de perdida diaria"
        paused = True
        pause_reason = mode_reason
    elif loss_streak >= pause_after:
        mode = "paused"
        mode_reason = f"{pause_after} perdidas seguidas"
        paused = True
        pause_reason = mode_reason
    elif loss_streak >= defensive_after or daily_pnl < 0:
        mode = "defensive"
        mode_reason = "racha negativa o pnl diario en deterioro"

    return {
        "mode": mode,
        "mode_reason": mode_reason,
        "paused": paused,
        "pause_reason": pause_reason,
        "risk_blocked": risk_blocked,
        "daily_loss_limit_usd": daily_loss_limit_usd,
    }


def main():
    cfg = load_risk_config()
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

    capital_base_usd = float(cfg.get("capital_base_usd", CRYPTO_CAPITAL_INITIAL_USD) or CRYPTO_CAPITAL_INITIAL_USD)
    if not portfolio:
        portfolio = {
            "capital_initial_usd": capital_base_usd,
            "cash_usd": capital_base_usd,
        }
    elif not portfolio.get("capital_initial_usd"):
        portfolio["capital_initial_usd"] = capital_base_usd

    today = datetime.now(UTC).date().isoformat()
    if daily.get("date") != today:
        daily = {
            "date": today,
            "trades": 0,
            "loss_streak": 0,
            "paused": False,
            "pause_reason": "",
            "mode": "normal",
            "mode_reason": "operativa normal",
        }
    daily.setdefault("loss_streak", 0)
    daily.setdefault("paused", False)
    daily.setdefault("pause_reason", "")
    daily.setdefault("mode", "normal")
    daily.setdefault("mode_reason", "operativa normal")

    target_pct = float(cfg.get("target_pct", TARGET_PCT) or TARGET_PCT)
    stop_pct = float(cfg.get("stop_pct", STOP_PCT) or STOP_PCT)
    timeout_min = int(cfg.get("timeout_min", TIMEOUT_MIN) or TIMEOUT_MIN)
    max_trades_day = int(cfg.get("max_trades_day", MAX_TRADES_DAY) or MAX_TRADES_DAY)
    max_trades_hour = int(cfg.get("max_trades_hour", MAX_TRADES_HOUR) or MAX_TRADES_HOUR)
    max_active_positions = int(cfg.get("max_active_positions", MAX_ACTIVE_POSITIONS) or MAX_ACTIVE_POSITIONS)
    alloc_per_trade_usd = float(cfg.get("alloc_per_trade_usd", ALLOC_PER_TRADE_USD) or ALLOC_PER_TRADE_USD)
    min_notional_usd = float(cfg.get("min_notional_usd", 20.0) or 20.0)
    defensive_scale = float(cfg.get("defensive_scale", 0.5) or 0.5)
    defensive_min_score = int(cfg.get("defensive_min_score", 82) or 82)
    defensive_min_confluence = int(cfg.get("defensive_min_confluence", 2) or 2)
    allowed_symbols = {str(s).upper() for s in (cfg.get("allowed_symbols") or []) if str(s).strip()}
    excluded_symbols = {str(s).upper() for s in (cfg.get("excluded_symbols") or []) if str(s).strip()}
    universe = load_universe_status()
    universe_core = universe.get("core") or set()
    universe_excluded = universe.get("excluded") or set()

    closed_now = 0
    still_active = []
    for order in active:
        ticker = order.get("ticker")
        cur = px.get(ticker)
        if cur is None:
            still_active.append(order)
            continue
        order["current_price"] = round(cur, 6)
        try:
            entry = float(order.get("entry_price") or 0)
            qty_live = float(order.get("qty") or 0)
            if entry > 0:
                order["pct_move"] = round(((cur - entry) / entry) * 100, 3)
            order["pnl_usd_est"] = round((cur - entry) * qty_live, 6)
        except Exception:
            order["pct_move"] = None
            order["pnl_usd_est"] = None

        result = None
        if cur >= float(order.get("target_price", 0)):
            result = "ganada"
        elif cur <= float(order.get("stop_price", 0)):
            result = "perdida"
        else:
            try:
                age = datetime.now(UTC) - parse_iso(order.get("opened_at"))
                if age >= timedelta(minutes=timeout_min):
                    result = "timeout"
            except Exception:
                pass

        if not result:
            still_active.append(order)
            continue

        order["closed_at"] = now_iso()
        order["close_price"] = round(cur, 6)
        order["result"] = result
        try:
            qty = float(order.get("qty") or 0)
            entry = float(order.get("entry_price") or 0)
            pnl = (cur - entry) * qty
        except Exception:
            pnl = 0.0
        order["pnl_usd"] = round(pnl, 6)
        order["state"] = "CLOSED"
        portfolio["cash_usd"] = float(portfolio.get("cash_usd", 0)) + float(order.get("notional_usd", 0)) + pnl
        if result == "perdida" or pnl < 0:
            daily["loss_streak"] = int(daily.get("loss_streak", 0)) + 1
        else:
            daily["loss_streak"] = 0
        completed.append(order)
        closed_now += 1

    active = still_active
    opened_now = 0
    active_tickers = {o.get("ticker") for o in active}

    now = datetime.now(UTC)
    one_hour_ago = now - timedelta(hours=1)

    def to_dt(value):
        try:
            return parse_iso(value)
        except Exception:
            return None

    hour_trades = 0
    for order in active:
        dt_value = to_dt(order.get("opened_at"))
        if dt_value and dt_value >= one_hour_ago:
            hour_trades += 1
    for order in completed:
        dt_value = to_dt(order.get("closed_at"))
        if dt_value and dt_value >= one_hour_ago:
            hour_trades += 1

    daily_pnl = 0.0
    for order in completed:
        dt_value = to_dt(order.get("closed_at"))
        if dt_value and dt_value.date().isoformat() == today:
            try:
                daily_pnl += float(order.get("pnl_usd") or 0)
            except Exception:
                pass

    mode_state = compute_mode(daily, daily_pnl, cfg, capital_base_usd)
    daily["mode"] = mode_state["mode"]
    daily["mode_reason"] = mode_state["mode_reason"]
    daily["paused"] = mode_state["paused"]
    daily["pause_reason"] = mode_state["pause_reason"]
    risk_blocked = mode_state["risk_blocked"]

    mode = daily.get("mode", "normal")
    entry_scale = defensive_scale if mode == "defensive" else 1.0
    effective_max_trades_day = max(1, int(round(max_trades_day * entry_scale))) if mode == "defensive" else max_trades_day
    effective_max_trades_hour = max(1, int(round(max_trades_hour * entry_scale))) if mode == "defensive" else max_trades_hour
    effective_max_active_positions = max(1, int(round(max_active_positions * entry_scale))) if mode == "defensive" else max_active_positions

    for candidate in top:
        if daily.get("trades", 0) >= effective_max_trades_day:
            break
        if hour_trades >= effective_max_trades_hour:
            break
        if risk_blocked or bool(daily.get("paused")):
            break
        if len(active) >= effective_max_active_positions:
            break
        if not allowed_now(cfg, now):
            break

        ticker = candidate.get("ticker")
        ticker_upper = str(ticker or "").upper()
        if ticker_upper in excluded_symbols or ticker_upper in universe_excluded:
            continue
        if allowed_symbols and ticker_upper not in allowed_symbols:
            continue
        if universe_core and ticker_upper not in universe_core:
            continue
        if ticker in active_tickers:
            continue
        if candidate.get("decision_final") != "BUY":
            continue
        if candidate.get("state") not in {"READY", "TRIGGERED"}:
            continue

        confluence = int(candidate.get("spy_confluence") or 0)
        breakout = int(candidate.get("spy_breakout") or 0)
        chart = int(candidate.get("spy_chart") or 0)
        min_confluence = defensive_min_confluence if mode == "defensive" else 1
        if confluence < min_confluence:
            continue

        score = int(candidate.get("score") or 0)
        if mode == "defensive" and score < defensive_min_score:
            continue
        if max(breakout, chart) <= 0 and score < 78:
            continue

        price = px.get(ticker)
        if price is None:
            continue

        cash = float(portfolio.get("cash_usd", 0))
        notional = min(alloc_per_trade_usd * entry_scale, cash)
        if notional < min_notional_usd:
            continue
        qty = notional / price

        order = {
            "id": f"crp_{ticker.lower()}_{int(datetime.now().timestamp())}",
            "ticker": ticker,
            "opened_at": now_iso(),
            "entry_price": round(price, 6),
            "qty": round(qty, 8),
            "notional_usd": round(notional, 2),
            "target_price": round(price * (1 + target_pct / 100), 6),
            "stop_price": round(price * (1 - stop_pct / 100), 6),
            "state": "ACTIVE",
            "mode": "scalp_intradia",
            "risk_mode": mode,
            "confidence": candidate.get("confidence_pct"),
            "score": candidate.get("score"),
            "spy_confluence": confluence,
            "spy_breakdown": {
                "news": candidate.get("spy_news"),
                "euphoria": candidate.get("spy_euphoria"),
                "flow": candidate.get("spy_flow"),
                "whale": candidate.get("spy_whale"),
            },
        }
        active.append(order)
        portfolio["cash_usd"] = round(float(portfolio.get("cash_usd", 0)) - notional, 2)
        active_tickers.add(ticker)
        opened_now += 1
        hour_trades += 1
        daily["trades"] = int(daily.get("trades", 0)) + 1

    active_value = 0.0
    for order in active:
        ticker = order.get("ticker")
        cur = px.get(ticker)
        if cur is None:
            continue
        order["current_price"] = round(float(cur), 6)
        try:
            entry = float(order.get("entry_price") or 0)
            qty_live = float(order.get("qty") or 0)
            if entry > 0:
                order["pct_move"] = round(((float(cur) - entry) / entry) * 100, 3)
                order["pnl_usd_est"] = round((float(cur) - entry) * qty_live, 6)
            else:
                order["pct_move"] = None
                order["pnl_usd_est"] = None
            active_value += qty_live * float(cur)
        except Exception:
            order["pct_move"] = None
            order["pnl_usd_est"] = None

    portfolio["market_value_usd"] = round(active_value, 2)
    portfolio["equity_usd"] = round(float(portfolio.get("cash_usd", 0)) + active_value, 2)

    book["active"] = active
    book["completed"] = completed[-1000:]
    book["daily"] = daily
    book["portfolio"] = portfolio
    ORD.parent.mkdir(parents=True, exist_ok=True)
    ORD.write_text(json.dumps(book, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "opened_now": opened_now,
                "closed_now": closed_now,
                "active_total": len(active),
                "daily_trades": daily.get("trades", 0),
                "max_trades_day": effective_max_trades_day,
                "hour_trades": hour_trades,
                "max_trades_hour": effective_max_trades_hour,
                "daily_pnl_usd": round(daily_pnl, 4),
                "daily_loss_limit_usd": mode_state["daily_loss_limit_usd"],
                "risk_blocked": risk_blocked,
                "mode": daily.get("mode", "normal"),
                "mode_reason": daily.get("mode_reason", "operativa normal"),
                "paused": bool(daily.get("paused")),
                "pause_reason": daily.get("pause_reason", ""),
                "loss_streak": int(daily.get("loss_streak", 0)),
                "cash_usd": portfolio.get("cash_usd", 0),
                "equity_usd": portfolio.get("equity_usd", 0),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
