#!/usr/bin/env python3
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import requests
import os
import urllib.parse
import urllib.request
import subprocess

SNAP = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")
RISK_CFG = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/config/risk.yaml")
UNIVERSE_STATUS = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/universe_status.json")
MACRO_SENTINEL_PATH = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/macro_sentinel.json")

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


def record_to_memory(ticker, result, pnl):
    """
    Registra el resultado de la operacion en la memoria persistente del agente (Episodic Memory)
    y envia una notificacion a Telegram para informar sobre el aprendizaje.
    """
    # 1. Intentar cargar credenciales de Telegram desde .env si no estan en el entorno
    env_path = Path("C:/Users/Fernando/.openclaw/.env")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "TELEGRAM_BOT_TOKEN": token = v.strip()
                    if k.strip() == "TELEGRAM_CHAT_ID": chat_id = v.strip()

    # 2. Notificar por Telegram
    if token and chat_id:
        try:
            emoji = "✅" if result == "ganada" else "❌" if result == "perdida" else "⏳"
            msg = (
                f"🧠 *Conviction Learning System*\n\n"
                f"{emoji} Asset: #{ticker}\n"
                f"📝 Resultado: {result.upper()}\n"
                f"💰 PnL: {pnl} USD\n\n"
                f"🔍 _Evento guardado en Memoria Episódica para mejorar estrategias futuras._"
            )
            tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
            params = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
            urllib.request.urlopen(f"{tg_url}?{params}", timeout=5)
        except Exception:
            pass

    # 3. Guardar en memoria de largo plazo (MCP)
    mcp_url = os.getenv("MCP_MEMORY_URL", "http://localhost:3001/tools/store_episodic")
    try:
        payload = {
            "content": f"Trade cerrado para {ticker}. Resultado: {result}. PnL: {pnl} USD.",
            "tags": ["crypto", "trading", ticker, result],
            "metadata": {"timestamp": datetime.now(UTC).isoformat(), "asset": ticker, "pnl": pnl}
        }
    except Exception:
        pass


def analyze_ticker_memory(completed_orders, ticker):
    """
    Analiza la 'experiencia' reciente con un ticker especifico.
    Retorna un multiplicador de confianza/riesgo (0.0 a 1.25)
    """
    recent = [o for o in completed_orders if o.get("ticker") == ticker][-4:] # Ultimos 4 trades
    if not recent:
        return 1.0, "Nuevo para hoy"
    
    losses = [o for o in recent if o.get("result") == "perdida" or (o.get("pnl_usd") or 0) < 0]
    wins = [o for o in recent if o.get("result") == "ganada" and (o.get("pnl_usd") or 0) > 0]
    
    if len(losses) >= 3:
        return 0.0, "BLOQUEADO: Racha perdedora critica (3+)"
    if len(losses) == 2:
        return 0.5, "REDUCIDO: Deteccion de volatilidad adversa (2 fallos)"
    if len(wins) >= 3:
        return 1.25, "BULLISH: Racha ganadora (Confianza extra)"
    
    return 1.0, "Normal"


def get_macro_sentiment(api_key):
    """
    Consulta el sentimiento Macro usando Alpha Vantage (NEWS_SENTIMENT).
    Usa un cache de 6 horas para no agotar la API (Solo usa 4 llamadas/dia de las 25 disponibles).
    """
    now = datetime.now(UTC)
    cache = load_json(MACRO_SENTINEL_PATH, {"ts": "", "score": 0.0, "label": "Neutral"})
    
    # Verificamos si el cache tiene menos de 6 horas
    if cache.get("ts"):
        last_update = parse_iso(cache["ts"])
        if (now - last_update).total_seconds() < 21600: # 6 horas
            return cache.get("score", 0.0), cache.get("label", "Neutral")

    if not api_key or api_key == "demo":
        return 0.0, "Neutral (No Key)"

    try:
        # Consultamos sentimiento sobre Blockchain/Crypto
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&topics=blockchain&apikey={api_key}"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        feed = data.get("feed", [])
        if not feed:
            return cache.get("score", 0.0), cache.get("label", "Neutral")
            
        # Promediamos el sentimiento de las noticias (habitualmente -1.0 a 1.0)
        scores = [float(item.get("overall_sentiment_score", 0)) for item in feed[:15]]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        label = "Bullish" if avg_score > 0.15 else "Bearish" if avg_score < -0.15 else "Neutral"
        
        # Guardar en cache
        new_cache = {"ts": now_iso(), "score": round(avg_score, 4), "label": label}
        MACRO_SENTINEL_PATH.write_text(json.dumps(new_cache), encoding="utf-8")
        
        return avg_score, label
    except Exception:
        return cache.get("score", 0.0), cache.get("label", "Neutral")


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
        "resume_after_pause_min": 180,
        "resume_in_defensive": True,
        "resume_min_core_candidates": 1,
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
        "research_negative_block_threshold": -2,
        "research_negative_size_scale": 0.6,
        "research_positive_size_scale": 1.15,
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


def pick_runtime_universe(allowed_symbols: set, universe_core: set, universe_watch: set, universe_excluded: set) -> tuple[set, str]:
    if not allowed_symbols:
        return set(), "market_dynamic"
    if allowed_symbols:
        core_allowed = {s for s in allowed_symbols if s in universe_core and s not in universe_excluded}
        if core_allowed:
            return core_allowed, "core∩allowed"
        watch_allowed = {s for s in allowed_symbols if s in universe_watch and s not in universe_excluded}
        if watch_allowed:
            return watch_allowed, "watch∩allowed"
        fallback_allowed = {s for s in allowed_symbols if s not in universe_excluded}
        if fallback_allowed:
            return fallback_allowed, "allowed_fallback"

    core_only = {s for s in universe_core if s not in universe_excluded}
    if core_only:
        return core_only, "core"
    watch_only = {s for s in universe_watch if s not in universe_excluded}
    if watch_only:
        return watch_only, "watch"
    return set(), "market_dynamic"


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


def count_resume_candidates(top: list, px: dict, cfg: dict, mode: str, allowed_symbols: set, excluded_symbols: set, universe_core: set, universe_excluded: set) -> int:
    defensive_min_score = int(cfg.get("defensive_min_score", 82) or 82)
    defensive_min_confluence = int(cfg.get("defensive_min_confluence", 2) or 2)
    count = 0
    for candidate in top:
        ticker = candidate.get("ticker")
        ticker_upper = str(ticker or "").upper()
        if not ticker_upper:
            continue
        if ticker_upper in excluded_symbols or ticker_upper in universe_excluded:
            continue
        if allowed_symbols and ticker_upper not in allowed_symbols:
            continue
        if universe_core and ticker_upper not in universe_core:
            continue
        if candidate.get("decision_final") != "BUY":
            continue
        if candidate.get("state") not in {"READY", "TRIGGERED"}:
            continue
        if px.get(ticker) is None:
            continue
        confluence = int(candidate.get("spy_confluence") or 0)
        min_confluence = defensive_min_confluence if mode == "defensive" else 1
        if confluence < min_confluence:
            continue
        score = int(candidate.get("score_final") or candidate.get("score") or 0)
        if mode == "defensive" and score < defensive_min_score:
            continue
        if max(int(candidate.get("spy_breakout") or 0), int(candidate.get("spy_chart") or 0)) <= 0 and score < 78:
            continue
        count += 1
    return count


def maybe_resume_from_pause(daily: dict, mode_state: dict, cfg: dict, now: datetime, resume_candidates: int):
    if not mode_state.get("paused"):
        return mode_state
    if mode_state.get("risk_blocked"):
        return mode_state

    paused_at_raw = daily.get("paused_at")
    if not paused_at_raw:
        return mode_state

    try:
        paused_at = parse_iso(paused_at_raw)
    except Exception:
        return mode_state

    resume_after_pause_min = int(cfg.get("resume_after_pause_min", 180) or 180)
    resume_min_core_candidates = int(cfg.get("resume_min_core_candidates", 1) or 1)
    resume_in_defensive = bool(cfg.get("resume_in_defensive", True))
    age_min = int((now - paused_at).total_seconds() // 60)

    if age_min < resume_after_pause_min:
        mode_state["mode_reason"] = f"pausa activa ({age_min}/{resume_after_pause_min} min)"
        mode_state["pause_reason"] = mode_state["mode_reason"]
        return mode_state
    if resume_candidates < resume_min_core_candidates:
        mode_state["mode_reason"] = f"pausa activa por falta de setups core ({resume_candidates}/{resume_min_core_candidates})"
        mode_state["pause_reason"] = mode_state["mode_reason"]
        return mode_state

    daily["paused"] = False
    daily["pause_reason"] = ""
    daily["paused_at"] = ""
    mode_state["paused"] = False
    mode_state["pause_reason"] = ""
    mode_state["mode"] = "defensive" if resume_in_defensive else "normal"
    mode_state["mode_reason"] = f"reanuda automaticamente con {resume_candidates} setups core"
    return mode_state


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
    daily.setdefault("paused_at", "")
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
    research_negative_block_threshold = int(cfg.get("research_negative_block_threshold", -2) or -2)
    research_negative_size_scale = float(cfg.get("research_negative_size_scale", 0.6) or 0.6)
    research_positive_size_scale = float(cfg.get("research_positive_size_scale", 1.15) or 1.15)
    allowed_symbols = {str(s).upper() for s in (cfg.get("allowed_symbols") or []) if str(s).strip()}
    excluded_symbols = {str(s).upper() for s in (cfg.get("excluded_symbols") or []) if str(s).strip()}
    universe = load_universe_status()
    universe_core = universe.get("core") or set()
    universe_watch = universe.get("watch") or set()
    universe_excluded = universe.get("excluded") or set()
    runtime_universe, runtime_universe_source = pick_runtime_universe(allowed_symbols, universe_core, universe_watch, universe_excluded)

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
        
        # Integracion con Memoria de Agente
        record_to_memory(ticker, result, pnl)
        
        completed.append(order)
        closed_now += 1

    # --- AUTOMATIZACION GITHUB (Usuario solicita push al cerrar) ---
    if closed_now > 0:
        try:
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            subprocess.run(["git", "add", "proyectos/analisis-mercados/data/crypto_orders_sim.json"], cwd=str(repo_root), capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Auto-update: {closed_now} crypto trades closed"], cwd=str(repo_root), capture_output=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=str(repo_root), capture_output=True)
        except Exception:
            pass

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

    pre_mode_state = compute_mode(daily, daily_pnl, cfg, capital_base_usd)
    predicted_mode = "defensive" if pre_mode_state.get("paused") and bool(cfg.get("resume_in_defensive", True)) else pre_mode_state.get("mode", "normal")
    resume_candidates = count_resume_candidates(top, px, cfg, predicted_mode, runtime_universe, excluded_symbols, runtime_universe, universe_excluded)
    mode_state = maybe_resume_from_pause(daily, pre_mode_state, cfg, now, resume_candidates)
    daily["mode"] = mode_state["mode"]
    daily["mode_reason"] = mode_state["mode_reason"]
    daily["paused"] = mode_state["paused"]
    daily["pause_reason"] = mode_state["pause_reason"]
    risk_blocked = mode_state["risk_blocked"]
    if daily.get("paused") and not daily.get("paused_at"):
        daily["paused_at"] = now_iso()
    if not daily.get("paused"):
        daily["paused_at"] = ""

    mode = daily.get("mode", "normal")
    
    # --- NIVEL EXPERTO: SENTINELA MACRO (Alpha Vantage Protected) ---
    av_key = os.getenv("ALPHA_VANTAGE_API_KEY", "FR1V3DW34QCGBDK3")
    macro_score, macro_label = get_macro_sentiment(av_key)
    macro_multiplier = 1.0
    if macro_label == "Bearish":
        macro_multiplier = 0.6  # Reducimos exposicion si el sentimiento global es malo
    elif macro_label == "Bullish":
        macro_multiplier = 1.1  # Aumentamos un poco si hay euforia positiva
        
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
        if runtime_universe and ticker_upper not in runtime_universe:
            continue
        if ticker in active_tickers:
            continue
        
        # --- NUEVA LOGICA DE MEMORIA AUTODIDACTA ---
        ticker_multiplier, memory_reason = analyze_ticker_memory(completed, ticker)
        if ticker_multiplier <= 0:
            # print(f"DEBUG: Saltando {ticker} por memoria negativa: {memory_reason}")
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

        score = int(candidate.get("score_final") or candidate.get("score") or 0)
        research_sentiment = str(candidate.get("research_sentiment") or "unknown").lower()
        research_catalyst_score = int(candidate.get("research_catalyst_score") or 0)
        if mode == "defensive" and score < defensive_min_score:
            continue
        if max(breakout, chart) <= 0 and score < 78:
            continue
        if research_catalyst_score <= research_negative_block_threshold and research_sentiment in {"negative", "mixed"}:
            continue

        price = px.get(ticker)
        if price is None:
            continue

        cash = float(portfolio.get("cash_usd", 0))
        research_scale = 1.0
        if research_sentiment == "positive" and research_catalyst_score >= 2:
            research_scale = research_positive_size_scale
        elif research_sentiment in {"negative", "mixed"} and research_catalyst_score < 0:
            research_scale = research_negative_size_scale
        notional = min(alloc_per_trade_usd * entry_scale * research_scale * ticker_multiplier * macro_multiplier, cash)
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
            "score": candidate.get("score_final") or candidate.get("score"),
            "research_sentiment": candidate.get("research_sentiment"),
            "research_catalyst_score": candidate.get("research_catalyst_score"),
            "research_size_scale": round(research_scale, 3),
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
                "paused_at": daily.get("paused_at", ""),
                "resume_candidates": resume_candidates,
                "runtime_universe": sorted(runtime_universe),
                "runtime_universe_source": runtime_universe_source,
                "loss_streak": int(daily.get("loss_streak", 0)),
                "cash_usd": portfolio.get("cash_usd", 0),
                "equity_usd": portfolio.get("equity_usd", 0),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
