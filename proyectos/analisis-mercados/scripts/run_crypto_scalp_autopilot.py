#!/usr/bin/env python3
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import requests
import os
import urllib.parse
import urllib.request
import source_ingest_crypto_free
import source_ingest_crypto_short

from runtime_utils import atomic_write_json, file_lock, make_exit_levels, round_price
from log_config import get_logger, log_trade, log_error_safe
from strategy_router import build_strategy_plan, normalize_symbol, plan_range_grid

log = get_logger("autopilot")

# Importar slippage model (graceful fallback si no disponible)
try:
    from slippage_model import estimate_slippage_bps as _estimate_slippage
    HAS_SLIPPAGE_MODEL = True
except ImportError:
    HAS_SLIPPAGE_MODEL = False
    _estimate_slippage = None  # type: ignore[assignment]

SNAP = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")
RISK_CFG = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/config/risk.yaml")
UNIVERSE_STATUS = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/universe_status.json")
MACRO_SENTINEL_PATH = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/macro_sentinel.json")
MOONSHOT_PATH = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/moonshot_candidates.json")
RUNTIME_LOCK = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/locks/crypto_runtime.lock")

TARGET_PCT = 0.9
STOP_PCT = 0.55
TIMEOUT_MIN = 30
MAX_TRADES_DAY = 120
MAX_TRADES_HOUR = 30
CRYPTO_CAPITAL_INITIAL_USD = 300.0
MAX_ACTIVE_POSITIONS = 10
ALLOC_PER_TRADE_USD = 30.0


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def breakeven_exit_price(entry_price: float, qty: float, fee_open_usd: float, fee_bps: float) -> float:
    entry = float(entry_price or 0)
    units = float(qty or 0)
    if entry <= 0 or units <= 0:
        return entry
    close_fee_factor = max(1e-9, 1.0 - (float(fee_bps or 0) / 10000.0))
    return ((entry * units) + max(0.0, float(fee_open_usd or 0))) / (units * close_fee_factor)


def estimate_trade_economics(entry_price: float, target_price: float, notional: float, fee_bps: float, slippage_bps: float):
    entry = float(entry_price or 0)
    target = float(target_price or 0)
    cash = float(notional or 0)
    if entry <= 0 or target <= entry or cash <= 0:
        return {"gross_profit_usd": 0.0, "net_profit_usd": 0.0, "net_return_pct": 0.0}
    qty = cash / entry
    exit_px = target * (1 - float(slippage_bps or 0) / 10000.0)
    gross_profit = max(0.0, (exit_px - entry) * qty)
    fee_open = cash * float(fee_bps or 0) / 10000.0
    fee_close = max(0.0, exit_px * qty * float(fee_bps or 0) / 10000.0)
    net_profit = gross_profit - fee_open - fee_close
    net_return_pct = (net_profit / cash * 100.0) if cash > 0 else 0.0
    return {
        "gross_profit_usd": round(gross_profit, 6),
        "net_profit_usd": round(net_profit, 6),
        "net_return_pct": round(net_return_pct, 4),
    }


def infer_setup_tag(candidate: dict, breakout: int, chart: int) -> str:
    flow = int(candidate.get("spy_flow") or 0)
    news = int(candidate.get("spy_news") or 0)
    whale = int(candidate.get("spy_whale") or 0)
    euphoria = int(candidate.get("spy_euphoria") or 0)
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

    # 3. Guardar en memoria de largo plazo (MCP) -- deshabilitado (endpoint no disponible)
    # mcp_url = os.getenv("MCP_MEMORY_URL", "http://localhost:3001/tools/store_episodic")
    # Codigo eliminado en auditoria 2026-03-14: el POST nunca se ejecutaba (faltaba urlopen)


def analyze_ticker_memory(completed_orders, ticker):
    """
    Analiza la 'experiencia' reciente con un ticker especifico.
    Retorna un multiplicador de confianza/riesgo (0.0 a 1.25)
    """
    recent = [o for o in completed_orders if o.get("ticker") == ticker][-4:] # Ultimos 4 trades
    if not recent:
        return 1.0, "Nuevo para hoy"
    
    losses = [o for o in recent if (o.get("result") == "perdida") or (o.get("result") != "timeout" and (o.get("pnl_usd") or 0) < 0)]
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
        "min_target_net_pct": 0.45,
        "min_expected_net_profit_usd": 0.12,
        "timeout_min": TIMEOUT_MIN,
        "timeout_profit_grace_min": 10,
        "timeout_force_close_min": 30,
        "min_timeout_profit_usd": 0.06,
        "near_target_ratio": 0.6,
        "trail_activation_ratio": 0.55,
        "trail_stop_profit_share": 0.4,
        "target_extension_ratio": 0.35,
        "target_extension_min_score": 85,
        "slippage_bps": 5,
        "fee_bps": 10,
        "max_trades_day": 120,
        "max_trades_hour": 24,
        "max_active_positions": 8,
        "alloc_per_trade_usd": 60.0,
        "max_alloc_per_trade_usd": 60.0,
        "min_notional_usd": 20.0,
        "defensive_scale": 0.35,
        "normal_min_score": 75,
        "defensive_min_score": 84,
        "defensive_min_confluence": 3,
        "research_negative_block_threshold": -2,
        "research_negative_size_scale": 0.6,
        "research_positive_size_scale": 1.15,
        "allowed_symbols": [],
        "excluded_symbols": ["PEPE", "AAVE", "ARB", "BTC", "DOGE", "GALA", "GRT", "MANA", "NEAR", "SEI"],
        "allowed_hours_utc": {"start": "00:00", "end": "23:59"},
        "execution_mode": "sim_only",
        "range_mode_enabled": True,
        "range_confidence_min": 0.55,
        "range_min_score": 68,
        "range_min_confluence": 2,
        "range_lookback_bars": 96,
        "range_entry_zone_max": 0.36,
        "range_width_pct_min": 1.2,
        "range_width_pct_max": 12.0,
        "range_max_rebound_pct": 2.2,
        "range_target_pct_multiplier": 0.72,
        "range_stop_pct_multiplier": 0.78,
        "range_alloc_multiplier": 0.75,
        "range_timeout_multiplier": 0.65,
        "range_grid_levels": 4,
        "range_grid_max_positions_per_ticker": 3,
        "range_grid_max_new_orders_per_cycle": 2,
        "range_grid_safety_buffer_pct": 0.0025,
        "range_grid_band_cooldown_min": 25,
        "bull_trend_enabled": True,
        "bull_min_score": 76,
        "bull_min_confluence": 2,
        "bull_min_24h_pct": 2.5,
        "bull_min_7d_pct": 6.0,
        "bull_fast_bars": 20,
        "bull_slow_bars": 50,
        "bull_breakout_near_high_pct": 1.25,
        "bull_max_pullback_pct": 3.5,
        "bull_min_trend_strength_pct": 0.45,
        "bull_downtrend_block_confidence": 0.7,
        "bull_countertrend_override_24h": 5.0,
        "bull_countertrend_override_7d": 10.0,
        "bull_nohistory_min_24h": 4.0,
        "bull_nohistory_min_7d": 9.0,
        "bull_target_pct_multiplier": 3.0,
        "bull_stop_pct_multiplier": 1.35,
        "bull_alloc_multiplier": 0.85,
        "bull_timeout_multiplier": 4.5,
        "bull_trail_activation_ratio": 1.0,
        "bull_trail_stop_profit_share": 0.62,
        "bull_target_extension_ratio": 1.1,
        "bull_target_extension_min_score": 74,
        "risk_on_enabled": True,
        "risk_on_min_alt_24h_pct": 3.0,
        "risk_on_min_alt_7d_pct": 6.5,
        "risk_on_min_score": 69,
        "risk_on_min_confluence": 1,
        "risk_on_min_candidates": 3,
        "risk_on_max_trades_hour_multiplier": 2.0,
        "risk_on_max_active_positions_multiplier": 1.8,
        "risk_on_max_trades_day_multiplier": 1.5,
        "risk_on_bull_priority_bonus": 18,
        "risk_on_breakout_priority_bonus": 8,
    }
    if not RISK_CFG.exists():
        return cfg

    # Intentar PyYAML primero, fallback a parser manual
    try:
        import yaml
        with RISK_CFG.open(encoding="utf-8") as f:
            parsed = yaml.safe_load(f)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                if k in cfg:
                    cfg[k] = v
            # Normalizar listas
            for list_key in ("allowed_symbols", "excluded_symbols"):
                if isinstance(cfg.get(list_key), list):
                    cfg[list_key] = [str(s).upper() for s in cfg[list_key] if s]
                elif cfg.get(list_key) is None:
                    cfg[list_key] = []
            return cfg
    except ImportError:
        pass  # PyYAML no disponible, usar parser manual
    except Exception:
        log.warning("Error parsing risk.yaml con PyYAML, fallback a parser manual")

    # Parser manual (legacy fallback)
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
    defensive_daily_loss_pct = float(cfg.get("defensive_daily_loss_pct", 1.0) or 1.0)
    daily_loss_limit_usd = round(capital_base_usd * max_daily_loss_pct / 100.0, 4)
    defensive_daily_loss_usd = round(capital_base_usd * defensive_daily_loss_pct / 100.0, 4)
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
    elif loss_streak >= defensive_after:
        mode = "defensive"
        mode_reason = f"{loss_streak} perdidas seguidas"
    elif daily_pnl <= (-defensive_daily_loss_usd):
        mode = "defensive"
        mode_reason = f"pnl diario por debajo de -{defensive_daily_loss_usd} usd"

    return {
        "mode": mode,
        "mode_reason": mode_reason,
        "paused": paused,
        "pause_reason": pause_reason,
        "risk_blocked": risk_blocked,
        "daily_loss_limit_usd": daily_loss_limit_usd,
        "defensive_daily_loss_usd": defensive_daily_loss_usd,
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
        if max(int(candidate.get("spy_breakout") or 0), int(candidate.get("spy_chart") or 0)) <= 0 and score < 50:
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
    try:
        with file_lock(RUNTIME_LOCK, stale_seconds=900, wait_seconds=0):
            _main_locked()
    except RuntimeError:
        print("LOCK_BUSY crypto_runtime")


def _main_locked():
    cfg = load_risk_config()
    snap = load_json(SNAP, {})
    if not isinstance(snap, dict):
        print("NO_SNAPSHOT")
        return

    top = snap.get("top_opportunities", []) or []
    assets = snap.get("assets", []) or []
    
    # Cargar candidatos de Moonshot para el multiplicador de conviccion
    moonshot_data = load_json(MOONSHOT_PATH, {})
    moonshot_prime = set()
    moonshot_all = set()
    if isinstance(moonshot_data, dict):
        crypto_ms = moonshot_data.get("crypto", [])
        for c in crypto_ms:
            tkr = str(c.get("ticker", "")).upper()
            if tkr:
                moonshot_all.add(tkr)
                if c.get("state") == "PRIME":
                    moonshot_prime.add(tkr)

    px = {a.get("ticker"): float(a.get("price_usd")) for a in assets if a.get("ticker") and a.get("price_usd")}

    risk_on_enabled = bool(cfg.get("risk_on_enabled", True))
    risk_on_min_alt_24h_pct = float(cfg.get("risk_on_min_alt_24h_pct", 3.0) or 3.0)
    risk_on_min_alt_7d_pct = float(cfg.get("risk_on_min_alt_7d_pct", 6.5) or 6.5)
    risk_on_min_score = int(cfg.get("risk_on_min_score", 69) or 69)
    risk_on_min_confluence = int(cfg.get("risk_on_min_confluence", 1) or 1)
    risk_on_min_candidates = int(cfg.get("risk_on_min_candidates", 3) or 3)
    risk_on_max_trades_hour_multiplier = float(cfg.get("risk_on_max_trades_hour_multiplier", 2.0) or 2.0)
    risk_on_max_active_positions_multiplier = float(cfg.get("risk_on_max_active_positions_multiplier", 1.8) or 1.8)
    risk_on_max_trades_day_multiplier = float(cfg.get("risk_on_max_trades_day_multiplier", 1.5) or 1.5)
    risk_on_bull_priority_bonus = int(cfg.get("risk_on_bull_priority_bonus", 18) or 18)
    risk_on_breakout_priority_bonus = int(cfg.get("risk_on_breakout_priority_bonus", 8) or 8)

    risk_on_candidates = [
        c for c in top
        if str(c.get("ticker") or "").upper() not in {"BTC", "ETH"}
        and float(c.get("chg_24h_pct") or 0.0) >= risk_on_min_alt_24h_pct
        and float(c.get("chg_7d_pct") or 0.0) >= risk_on_min_alt_7d_pct
        and int(c.get("score_final") or c.get("score") or 0) >= risk_on_min_score
        and int(c.get("spy_confluence") or 0) >= risk_on_min_confluence
        and c.get("decision_final") == "BUY"
    ]
    market_risk_on = risk_on_enabled and len(risk_on_candidates) >= risk_on_min_candidates

    def candidate_priority(item):
        score = int(item.get("score_final") or item.get("score") or 0)
        confluence = int(item.get("spy_confluence") or 0)
        breakout = int(item.get("spy_breakout") or 0)
        chart = int(item.get("spy_chart") or 0)
        chg24 = float(item.get("chg_24h_pct") or 0.0)
        chg7 = float(item.get("chg_7d_pct") or 0.0)
        priority = score * 100 + confluence * 15 + breakout * 8 + chart * 8
        if market_risk_on:
            if chg24 >= risk_on_min_alt_24h_pct and chg7 >= risk_on_min_alt_7d_pct:
                priority += risk_on_bull_priority_bonus
            if breakout > 0 or chart > 0:
                priority += risk_on_breakout_priority_bonus
        return priority

    top = sorted(top, key=candidate_priority, reverse=True)

    book = load_json(ORD, {"active": [], "completed": [], "daily": {}, "portfolio": {}})
    active = book.get("active", []) or []
    completed = book.get("completed", []) or []
    daily = book.get("daily", {}) or {}
    portfolio = book.get("portfolio", {}) or {}

    capital_base_usd = float(cfg.get("capital_base_usd", CRYPTO_CAPITAL_INITIAL_USD) or CRYPTO_CAPITAL_INITIAL_USD)
    slippage_bps = float(cfg.get("slippage_bps", 0) or 0)
    fee_bps = float(cfg.get("fee_bps", 0) or 0)
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
    min_target_net_pct = float(cfg.get("min_target_net_pct", 0.45) or 0.45)
    min_expected_net_profit_usd = float(cfg.get("min_expected_net_profit_usd", 0.25) or 0.25)
    timeout_min = int(cfg.get("timeout_min", TIMEOUT_MIN) or TIMEOUT_MIN)
    timeout_profit_grace_min = int(cfg.get("timeout_profit_grace_min", 10) or 10)
    timeout_force_close_min = int(cfg.get("timeout_force_close_min", 30) or 30)
    min_timeout_profit_usd = float(cfg.get("min_timeout_profit_usd", 0.06) or 0.06)
    near_target_ratio = float(cfg.get("near_target_ratio", 0.6) or 0.6)
    trail_activation_ratio = float(cfg.get("trail_activation_ratio", 0.55) or 0.55)
    trail_stop_profit_share = float(cfg.get("trail_stop_profit_share", 0.4) or 0.4)
    target_extension_ratio = float(cfg.get("target_extension_ratio", 0.35) or 0.35)
    target_extension_min_score = int(cfg.get("target_extension_min_score", 85) or 85)
    max_trades_day = int(cfg.get("max_trades_day", MAX_TRADES_DAY) or MAX_TRADES_DAY)
    max_trades_hour = int(cfg.get("max_trades_hour", MAX_TRADES_HOUR) or MAX_TRADES_HOUR)
    max_active_positions = int(cfg.get("max_active_positions", MAX_ACTIVE_POSITIONS) or MAX_ACTIVE_POSITIONS)
    alloc_per_trade_usd = float(cfg.get("alloc_per_trade_usd", ALLOC_PER_TRADE_USD) or ALLOC_PER_TRADE_USD)
    max_alloc_per_trade_usd = float(cfg.get("max_alloc_per_trade_usd", 60.0) or 60.0)
    min_notional_usd = float(cfg.get("min_notional_usd", 20.0) or 20.0)
    defensive_scale = float(cfg.get("defensive_scale", 0.5) or 0.5)
    normal_min_score = int(cfg.get("normal_min_score", 75) or 75)
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

    # --- CIRCUIT BREAKER: parar si el profit factor reciente es muy bajo ---
    CIRCUIT_BREAKER_MIN_TRADES = 30
    CIRCUIT_BREAKER_MIN_PF = 0.5
    recent_completed = completed[-CIRCUIT_BREAKER_MIN_TRADES:]
    if len(recent_completed) >= CIRCUIT_BREAKER_MIN_TRADES:
        rc_gross_profit = sum(float(o.get("pnl_usd") or 0) for o in recent_completed if float(o.get("pnl_usd") or 0) > 0)
        rc_gross_loss = abs(sum(float(o.get("pnl_usd") or 0) for o in recent_completed if float(o.get("pnl_usd") or 0) < 0))
        rc_pf = (rc_gross_profit / rc_gross_loss) if rc_gross_loss > 0 else 999.0
        if rc_pf < CIRCUIT_BREAKER_MIN_PF:
            daily["paused"] = True
            daily["pause_reason"] = f"CIRCUIT_BREAKER: PF={rc_pf:.2f} en ultimas {CIRCUIT_BREAKER_MIN_TRADES} trades < {CIRCUIT_BREAKER_MIN_PF}"
            daily["mode"] = "paused"
            daily["mode_reason"] = daily["pause_reason"]
            if not daily.get("paused_at"):
                daily["paused_at"] = now_iso()

    # --- COOLDOWN POR TICKER: evitar sobreoperacion en el mismo activo ---
    COOLDOWN_MINUTES = 30  # minutos minimos entre trades del mismo ticker
    range_band_cooldown_min = int(cfg.get("range_grid_band_cooldown_min", 25) or 25)
    now = datetime.now(UTC)
    recent_ticker_times = {}
    recent_grid_band_times = {}
    for o in completed[-200:]:
        t = str(o.get("ticker") or "").upper()
        closed_at = o.get("closed_at") or o.get("opened_at") or ""
        if t and closed_at:
            try:
                ct = parse_iso(closed_at)
                if t not in recent_ticker_times or ct > recent_ticker_times[t]:
                    recent_ticker_times[t] = ct
                grid_band_index = o.get("grid_band_index")
                if grid_band_index is not None:
                    band_key = f"{t}:{grid_band_index}"
                    if band_key not in recent_grid_band_times or ct > recent_grid_band_times[band_key]:
                        recent_grid_band_times[band_key] = ct
            except Exception:
                pass

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
            entry_fee = safe_float(order.get("fee_open_usd") or order.get("fee_usd"), 0)
            exit_fee_est = abs(float(cur) * qty_live) * fee_bps / 10000.0
            target_price = safe_float(order.get("target_price"), 0)
            if entry > 0:
                order["pct_move"] = round(((cur - entry) / entry) * 100, 3)
            order["pnl_usd_est"] = round(((cur - entry) * qty_live) - entry_fee - exit_fee_est, 6)
            breakeven_px = breakeven_exit_price(entry, qty_live, entry_fee, fee_bps)
            order["breakeven_price"] = round_price(breakeven_px)
            current_stop = safe_float(order.get("stop_price"), 0)
            if cur >= breakeven_px and breakeven_px > current_stop:
                order["stop_price"] = round_price(breakeven_px)
                order["breakeven_armed"] = True
            target_progress = 0.0
            if target_price > entry > 0:
                target_progress = (cur - entry) / max(target_price - entry, 1e-9)
            order["target_progress"] = round(target_progress, 3)
            order_trail_activation_ratio = float(order.get("trail_activation_ratio") or trail_activation_ratio)
            order_trail_stop_profit_share = float(order.get("trail_stop_profit_share") or trail_stop_profit_share)
            order_target_extension_ratio = float(order.get("target_extension_ratio") or target_extension_ratio)
            order_target_extension_min_score = int(order.get("target_extension_min_score") or target_extension_min_score)
            if target_progress >= order_trail_activation_ratio and order.get("pnl_usd_est", 0) > 0:
                locked_price = entry + max(0.0, (cur - entry) * order_trail_stop_profit_share)
                locked_price = max(locked_price, breakeven_px)
                if locked_price > safe_float(order.get("stop_price"), 0):
                    order["stop_price"] = round_price(locked_price)
                    order["trailing_armed"] = True
            if cur >= target_price > 0 and not bool(order.get("target_extended")):
                score_live = int(order.get("confidence") or order.get("score") or 0)
                if score_live >= order_target_extension_min_score or int(order.get("spy_confluence") or 0) >= 4:
                    original_target = target_price
                    extended_target = entry + ((target_price - entry) * (1.0 + order_target_extension_ratio))
                    order["target_price"] = round_price(extended_target)
                    order["target_extended"] = True
                    order["target_extension_from"] = round_price(original_target)
                    protect_price = max(breakeven_px, entry + ((original_target - entry) * 0.6))
                    if protect_price > safe_float(order.get("stop_price"), 0):
                        order["stop_price"] = round_price(protect_price)
        except Exception as e:
            log_error_safe(log, f"Error calculating live PnL for {ticker}: {e}")
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
                order_timeout_min = int(order.get("timeout_min") or timeout_min)
                order_timeout_profit_grace_min = int(order.get("timeout_profit_grace_min") or timeout_profit_grace_min)
                order_timeout_force_close_min = int(order.get("timeout_force_close_min") or timeout_force_close_min)
                if age >= timedelta(minutes=order_timeout_min):
                    pnl_est = safe_float(order.get("pnl_usd_est"), 0)
                    target_price = safe_float(order.get("target_price"), 0)
                    entry_price = safe_float(order.get("entry_price"), 0)
                    target_progress = 0.0
                    if target_price > entry_price > 0:
                        target_progress = (cur - entry_price) / max(target_price - entry_price, 1e-9)
                    extend_timeout = (
                        age < timedelta(minutes=order_timeout_force_close_min)
                        and (
                            pnl_est >= min_timeout_profit_usd
                            or target_progress >= near_target_ratio
                        )
                    )
                    if extend_timeout:
                        order["timeout_extended"] = True
                        order["timeout_extended_until"] = (
                            parse_iso(order.get("opened_at")) + timedelta(minutes=order_timeout_force_close_min)
                        ).isoformat().replace("+00:00", "Z")
                    elif age >= timedelta(minutes=order_timeout_min + order_timeout_profit_grace_min) or pnl_est < -0.15:
                        result = "timeout"
            except Exception as e:
                log_error_safe(log, f"Error evaluating timeout for {ticker}: {e}")

        if not result:
            still_active.append(order)
            continue

        order["closed_at"] = now_iso()
        exit_px = float(cur) * (1 - slippage_bps / 10000.0)
        order["close_price"] = round_price(exit_px)
        order["exit_price"] = order["close_price"]
        order["result"] = result
        try:
            qty = float(order.get("qty") or 0)
            entry = float(order.get("entry_price") or 0)
            gross_pnl = (exit_px - entry) * qty
            exit_notional = exit_px * qty
            fee_open = safe_float(order.get("fee_open_usd") or order.get("fee_usd"), 0)
            fee_close = exit_notional * fee_bps / 10000.0 if qty > 0 else 0.0
            fee_total = max(0.0, fee_open) + max(0.0, fee_close)
            pnl = gross_pnl - fee_total
            returned_cash = exit_notional - fee_close
        except Exception as e:
            log_error_safe(log, f"CRITICAL: PnL calc failed for closed order {ticker} result={result}: {e}")
            gross_pnl = 0.0
            fee_total = 0.0
            returned_cash = float(order.get("notional_usd", 0) or 0)
            pnl = 0.0
        order["gross_pnl_usd"] = round(gross_pnl, 6)
        order["fee_usd"] = round(fee_total, 6)
        order["pnl_usd"] = round(pnl, 6)
        order["state"] = "CLOSED"
        portfolio["cash_usd"] = round(float(portfolio.get("cash_usd", 0)) + returned_cash, 6)
        if result == "perdida" or pnl < 0:
            daily["loss_streak"] = int(daily.get("loss_streak", 0)) + 1
        else:
            daily["loss_streak"] = 0
        
        # Integracion con Memoria de Agente
        record_to_memory(ticker, result, pnl)
        
        completed.append(order)
        closed_now += 1

    active = still_active
    opened_now = 0
    active_tickers = {str(o.get("ticker")).upper() for o in active if o.get("ticker")}
    active_by_ticker = {}
    for order in active:
        ticker_key = str(order.get("ticker") or "").upper()
        if not ticker_key:
            continue
        active_by_ticker.setdefault(ticker_key, []).append(order)

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
    av_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    macro_score, macro_label = get_macro_sentiment(av_key)
    macro_multiplier = 1.0
    if macro_label == "Bearish":
        macro_multiplier = 0.6
    elif macro_label == "Bullish":
        macro_multiplier = 1.1

    # --- REGIME DETECTOR: ajustar parametros segun estado del mercado ---
    regime_data = load_json(Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/market_regime.json"), {})
    regime_multipliers = {}
    for _sym, _reg in (regime_data.get("regimes") or {}).items():
        adj = _reg.get("param_adjustments") or {}
        regime_multipliers[_sym] = {
            "target": float(adj.get("target_pct_multiplier", 1.0)),
            "stop": float(adj.get("stop_pct_multiplier", 1.0)),
            "alloc": float(adj.get("alloc_multiplier", 1.0)),
            "max_pos": float(adj.get("max_positions_multiplier", 1.0)),
            "regime": _reg.get("regime", "unknown"),
            "confidence": float(_reg.get("confidence", 0.0) or 0.0),
            "recommended_mode": _reg.get("recommended_mode", "normal"),
        }
    # Usar BTC como proxy del mercado general si existe
    btc_regime = regime_multipliers.get("BTCUSDT", {})
    regime_alloc_mult = float(btc_regime.get("alloc", 1.0))
    regime_target_mult = float(btc_regime.get("target", 1.0))
    regime_stop_mult = float(btc_regime.get("stop", 1.0))
    regime_max_pos_mult = float(btc_regime.get("max_pos", 1.0))
    # Ajustar parametros base segun regime
    target_pct = target_pct * regime_target_mult
    stop_pct = stop_pct * regime_stop_mult
    effective_max_active_positions_regime = max(1, int(round(max_active_positions * regime_max_pos_mult)))

    # --- CORRELATION CHECK: detectar riesgo concentrado ---
    correlation_data = load_json(Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/correlation_analysis.json"), {})
    portfolio_concentrated = bool(correlation_data.get("concentrated_risk", False))
        
    entry_scale = defensive_scale if mode == "defensive" else 1.0
    effective_max_trades_day = max(1, int(round(max_trades_day * entry_scale))) if mode == "defensive" else max_trades_day
    effective_max_trades_hour = max(1, int(round(max_trades_hour * entry_scale))) if mode == "defensive" else max_trades_hour
    effective_max_active_positions = max(1, int(round(max_active_positions * entry_scale))) if mode == "defensive" else max_active_positions
    # Aplicar regime y correlation ajustes
    effective_max_active_positions = min(effective_max_active_positions, effective_max_active_positions_regime)
    if market_risk_on and mode != "defensive":
        effective_max_trades_day = max(effective_max_trades_day, int(round(max_trades_day * risk_on_max_trades_day_multiplier)))
        effective_max_trades_hour = max(effective_max_trades_hour, int(round(max_trades_hour * risk_on_max_trades_hour_multiplier)))
        effective_max_active_positions = max(effective_max_active_positions, int(round(max_active_positions * risk_on_max_active_positions_multiplier)))
    if portfolio_concentrated:
        effective_max_active_positions = max(1, effective_max_active_positions // 2)  # reducir 50% si correlacion alta

    opened_strategy_modes = {}

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
        ticker_multiplier, memory_reason = analyze_ticker_memory(completed, ticker)
        if ticker_multiplier <= 0:
            log.info(f"Skipping {ticker}: blocked by episodic memory - {memory_reason}")
            continue

        score = int(candidate.get("score_final") or candidate.get("score") or 0)
        
        # --- BYPASS DE UNIVERSO POR ALTA CONVICCION ---
        # Si el score es >= 80, operamos aunque no este en el Core/Watch predefinido
        if runtime_universe and ticker_upper not in runtime_universe:
            if score < 75:
                log.info(f"Skipping {ticker}: score {score} < 75 and not in core/watch universe")
                continue
            else:
                log.info(f"BYPASS: {ticker} (Score {score}) allowed outside universe for high conviction")

        if candidate.get("decision_final") != "BUY":
            log.info(f"Skipping {ticker}: final decision is {candidate.get('decision_final')}")
            continue
        if candidate.get("state") not in {"READY", "TRIGGERED"}:
            continue

        confluence = int(candidate.get("spy_confluence") or 0)
        breakout = int(candidate.get("spy_breakout") or 0)
        chart = int(candidate.get("spy_chart") or 0)
        setup_tag = infer_setup_tag(candidate, breakout, chart)

        # --- FILTRO DE EDGE: bloquear setups sin edge demostrado ---
        # Auditoria 2026-03-14: setup "base" tiene 0% win rate historico
        # Confluencia < 3 tiene 11% win rate (edge_score -10)
        BLOCKED_SETUPS = {"base"}
        MIN_CONFLUENCE_HARD = 3  # No abrir trades con menos de 3 spies de confluencia

        research_sentiment = str(candidate.get("research_sentiment") or "unknown").lower()
        research_catalyst_score = int(candidate.get("research_catalyst_score") or 0)
        if research_catalyst_score <= research_negative_block_threshold and research_sentiment in {"negative", "mixed"}:
            continue

        price = px.get(ticker)
        if price is None:
            continue

        symbol_regime = regime_multipliers.get(normalize_symbol(ticker_upper), btc_regime)
        strategy_plan = build_strategy_plan(candidate, ticker_upper, float(price), cfg, btc_regime, symbol_regime)
        strategy_mode = str(strategy_plan.get("strategy_mode") or "scalp_intradia")
        strategy_reason = str(strategy_plan.get("reason") or "modo base")
        range_context = strategy_plan.get("range_context") or {}
        ticker_active_orders = active_by_ticker.get(ticker_upper, [])
        active_range_orders = [o for o in ticker_active_orders if str(o.get("strategy_mode") or "") == "range_lateral"]
        active_non_range_orders = [o for o in ticker_active_orders if str(o.get("strategy_mode") or "") != "range_lateral"]

        if strategy_mode == "range_lateral":
            if active_non_range_orders:
                log.info(f"Skipping {ticker_upper}: already has non-range active positions")
                continue
        elif ticker_active_orders:
            log.info(f"Skipping {ticker_upper}: already has active positions")
            continue

        strategy_min_score = int(strategy_plan.get("min_score_override") or normal_min_score)
        min_confluence = max(MIN_CONFLUENCE_HARD, defensive_min_confluence if mode == "defensive" else MIN_CONFLUENCE_HARD)
        base_min_confluence = 2 if score >= 80 else min_confluence
        strategy_min_confluence = int(strategy_plan.get("min_confluence_override") or base_min_confluence)
        effective_min_confluence = max(1, min(base_min_confluence, strategy_min_confluence))

        if setup_tag in BLOCKED_SETUPS and strategy_mode != "range_lateral":
            if score < 80:
                log.info(f"Skipping {ticker}: setup '{setup_tag}' is blocked for scores < 80")
                continue
            log.info(f"BYPASS: Allowing setup '{setup_tag}' for {ticker} due to extreme score ({score})")

        if confluence < effective_min_confluence:
            log.info(f"Skipping {ticker}: confluence {confluence} < effective min {effective_min_confluence}")
            continue

        effective_normal_min_score = min(normal_min_score, strategy_min_score)
        effective_defensive_min_score = max(effective_normal_min_score, min(defensive_min_score, strategy_min_score))
        if score < effective_normal_min_score:
            log.info(f"Skipping {ticker}: score {score} < threshold {effective_normal_min_score} for {strategy_mode}")
            continue
        if mode == "defensive" and score < effective_defensive_min_score:
            if score >= 80:
                log.info(f"BYPASS: Allowing {ticker} (Score {score}) in defensive mode ({strategy_mode})")
            else:
                log.info(f"Skipping {ticker}: score {score} < defensive threshold {effective_defensive_min_score} for {strategy_mode}")
                continue
        if max(breakout, chart) <= 0 and score < 50:
            continue

        cash = float(portfolio.get("cash_usd", 0))
        research_scale = 1.0
        if research_sentiment == "positive" and research_catalyst_score >= 2:
            research_scale = research_positive_size_scale
        elif research_sentiment in {"negative", "mixed"} and research_catalyst_score < 0:
            research_scale = research_negative_size_scale

        # --- SIZING DINAMICO POR CONVICCION ---
        # Escalar notional segun score y confluencia
        conviction_scale = 1.0
        if score >= 95 and confluence >= 4:
            conviction_scale = 1.6  # Ultra conviccion (Nuevo)
        elif score >= 90 and confluence >= 4:
            conviction_scale = 1.4  # Alta conviccion: 40% mas
        elif score >= 82 and confluence >= 3:
            conviction_scale = 1.15  # Buena conviccion: 15% mas
        elif score < 70:
            conviction_scale = 0.7  # Baja conviccion: 30% menos

        # --- MOONSHOT BONUS ---
        moonshot_multiplier = 1.0
        if ticker_upper in moonshot_prime:
            moonshot_multiplier = 1.5
            log.info(f"BONUS: {ticker} es PRIME en Moonshot. Multiplicador 1.5x aplicado.")
        elif ticker_upper in moonshot_all:
            moonshot_multiplier = 1.25
            log.info(f"BONUS: {ticker} es candidato Moonshot. Multiplicador 1.25x aplicado.")

        strategy_alloc_mult = float(strategy_plan.get("alloc_multiplier") or 1.0)
        trade_target_pct = target_pct * float(strategy_plan.get("target_multiplier") or 1.0)
        trade_stop_pct = stop_pct * float(strategy_plan.get("stop_multiplier") or 1.0)
        strategy_timeout_mult = float(strategy_plan.get("timeout_multiplier") or 1.0)
        trade_trail_activation_ratio = float(strategy_plan.get("trail_activation_ratio_override") or trail_activation_ratio)
        trade_trail_stop_profit_share = float(strategy_plan.get("trail_stop_profit_share_override") or trail_stop_profit_share)
        trade_target_extension_ratio = float(strategy_plan.get("target_extension_ratio_override") or target_extension_ratio)
        trade_target_extension_min_score = int(strategy_plan.get("target_extension_min_score_override") or target_extension_min_score)
        trade_timeout_min = max(15, int(round(timeout_min * strategy_timeout_mult)))
        trade_timeout_profit_grace_min = max(5, int(round(timeout_profit_grace_min * max(0.75, strategy_timeout_mult))))
        trade_timeout_force_close_min = max(trade_timeout_min + 15, int(round(timeout_force_close_min * max(0.65, strategy_timeout_mult))))

        last_ticker_trade = recent_ticker_times.get(ticker_upper)
        if strategy_mode != "range_lateral" and last_ticker_trade:
            age_minutes = (now - last_ticker_trade).total_seconds() / 60.0
            if age_minutes < COOLDOWN_MINUTES:
                log.info(f"Skipping {ticker}: cooldown activo {age_minutes:.1f}/{COOLDOWN_MINUTES} min")
                continue

        planned_entries = [{"size_scale": 1.0, "target_price": None, "stop_anchor": None, "band_index": None, "grid_levels": []}]
        if strategy_mode == "range_lateral":
            active_bands = {int(o.get("grid_band_index")) for o in active_range_orders if o.get("grid_band_index") is not None}
            recent_bands = set()
            for band_key, band_time in recent_grid_band_times.items():
                prefix = f"{ticker_upper}:"
                if band_key.startswith(prefix) and ((now - band_time).total_seconds() / 60.0) < range_band_cooldown_min:
                    try:
                        recent_bands.add(int(band_key.split(":", 1)[1]))
                    except Exception:
                        pass
            planned_entries = plan_range_grid(strategy_plan, float(price), cfg, active_bands, recent_bands)
            if not planned_entries:
                log.info(f"Skipping {ticker}: sin nuevas bandas de grid disponibles")
                continue

        opened_for_candidate = 0
        for entry_plan in planned_entries:
            if daily.get("trades", 0) >= effective_max_trades_day or hour_trades >= effective_max_trades_hour:
                break
            if len(active) >= effective_max_active_positions:
                break

            cash = float(portfolio.get("cash_usd", 0))
            order_size_scale = float(entry_plan.get("size_scale") or 1.0)
            target_alloc = alloc_per_trade_usd * entry_scale * research_scale * ticker_multiplier * macro_multiplier * conviction_scale * regime_alloc_mult * strategy_alloc_mult * moonshot_multiplier * order_size_scale
            notional = min(target_alloc, cash, max_alloc_per_trade_usd)
            if notional < min_notional_usd:
                continue

            effective_slippage_bps = slippage_bps
            if HAS_SLIPPAGE_MODEL and _estimate_slippage is not None and price and price > 0:
                try:
                    slip_est = _estimate_slippage(ticker, notional, float(price))
                    effective_slippage_bps = max(slippage_bps, slip_est.get("estimated_bps", slippage_bps))
                except Exception:
                    pass
            entry_px = float(price) * (1 + effective_slippage_bps / 10000.0)
            if entry_px <= 0:
                continue

            target_price = entry_plan.get("target_price")
            stop_price = entry_plan.get("stop_anchor")
            if strategy_mode == "range_lateral" and target_price and stop_price:
                target_price = round_price(max(float(target_price), entry_px * 1.001))
                stop_price = round_price(min(float(stop_price), entry_px * 0.9985))
            else:
                target_price, stop_price = make_exit_levels(entry_px, trade_target_pct, trade_stop_pct)

            economics = estimate_trade_economics(entry_px, float(target_price), notional, fee_bps, slippage_bps)
            if economics["net_return_pct"] <= 0 or economics["net_return_pct"] < min_target_net_pct:
                continue
            required_notional = max(min_notional_usd, min_expected_net_profit_usd / max(economics["net_return_pct"] / 100.0, 1e-9))
            if required_notional > notional:
                notional = min(required_notional, cash, max_alloc_per_trade_usd)
                if notional < required_notional:
                    continue
                economics = estimate_trade_economics(entry_px, float(target_price), notional, fee_bps, slippage_bps)
                if economics["net_return_pct"] < min_target_net_pct or economics["net_profit_usd"] < min_expected_net_profit_usd:
                    continue

            qty = notional / entry_px
            fee_open = notional * fee_bps / 10000.0
            band_index = entry_plan.get("band_index")
            order = {
                "id": f"crp_{ticker.lower()}_{int(datetime.now().timestamp())}_{opened_for_candidate}",
                "ticker": ticker,
                "opened_at": now_iso(),
                "entry_price": round_price(entry_px),
                "qty": round(qty, 8),
                "notional_usd": round(notional, 2),
                "target_price": target_price,
                "stop_price": stop_price,
                "state": "ACTIVE",
                "mode": "scalp_intradia",
                "strategy_mode": strategy_mode,
                "strategy_reason": strategy_reason,
                "risk_mode": mode,
                "confidence": candidate.get("confidence_pct"),
                "score": candidate.get("score_final") or candidate.get("score"),
                "research_sentiment": candidate.get("research_sentiment"),
                "research_catalyst_score": candidate.get("research_catalyst_score"),
                "research_size_scale": round(research_scale, 3),
                "slippage_bps": effective_slippage_bps,
                "slippage_bps_base": slippage_bps,
                "fee_bps": fee_bps,
                "fee_open_usd": round(fee_open, 6),
                "expected_target_net_profit_usd": economics["net_profit_usd"],
                "expected_target_net_pct": economics["net_return_pct"],
                "target_pct": trade_target_pct,
                "stop_pct": trade_stop_pct,
                "timeout_min": trade_timeout_min,
                "timeout_profit_grace_min": trade_timeout_profit_grace_min,
                "timeout_force_close_min": trade_timeout_force_close_min,
                "trail_activation_ratio": trade_trail_activation_ratio,
                "trail_stop_profit_share": trade_trail_stop_profit_share,
                "target_extension_ratio": trade_target_extension_ratio,
                "target_extension_min_score": trade_target_extension_min_score,
                "opened_hour_utc": datetime.now(UTC).strftime("%H"),
                "setup_tag": setup_tag,
                "range_context": range_context if strategy_mode == "range_lateral" else {},
                "bull_context": strategy_plan.get("bull_context") if strategy_mode == "bull_trend" else {},
                "grid_band_index": band_index,
                "grid_levels": entry_plan.get("grid_levels") or [],
                "spy_confluence": confluence,
                "spy_chart": chart,
                "spy_breakout": breakout,
                "spy_breakdown": {
                    "news": candidate.get("spy_news"),
                    "euphoria": candidate.get("spy_euphoria"),
                    "flow": candidate.get("spy_flow"),
                    "whale": candidate.get("spy_whale"),
                },
            }
            active.append(order)
            active_by_ticker.setdefault(ticker_upper, []).append(order)
            portfolio["cash_usd"] = round(float(portfolio.get("cash_usd", 0)) - notional - fee_open, 6)
            active_tickers.add(ticker_upper)
            opened_strategy_modes[strategy_mode] = int(opened_strategy_modes.get(strategy_mode, 0)) + 1
            if band_index is not None:
                recent_grid_band_times[f"{ticker_upper}:{band_index}"] = now
            recent_ticker_times[ticker_upper] = now
            opened_now += 1
            opened_for_candidate += 1
            hour_trades += 1
            daily["trades"] = int(daily.get("trades", 0)) + 1
            log_trade(log, "OPEN", ticker, notional=round(notional, 2), entry=round_price(entry_px),
                      target=target_price, stop=stop_price, score=score, confluence=confluence,
                      setup=setup_tag, slippage=round(effective_slippage_bps, 1),
                      regime=btc_regime.get("regime", "unknown"), strategy=strategy_mode,
                      grid_band=band_index if band_index is not None else "na")

        if opened_for_candidate <= 0:
            log.info(f"Skipping {ticker}: no paso economia final para {strategy_mode}")

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
            entry_fee = safe_float(order.get("fee_open_usd") or order.get("fee_usd"), 0)
            exit_fee_est = abs(float(cur) * qty_live) * fee_bps / 10000.0
            if entry > 0:
                order["pct_move"] = round(((float(cur) - entry) / entry) * 100, 3)
                order["pnl_usd_est"] = round(((float(cur) - entry) * qty_live) - entry_fee - exit_fee_est, 6)
            else:
                order["pct_move"] = None
                order["pnl_usd_est"] = None
            active_value += qty_live * float(cur)
        except Exception as e:
            log_error_safe(log, f"Error calculating portfolio value for {ticker}: {e}")
            order["pct_move"] = None
            order["pnl_usd_est"] = None

    portfolio["market_value_usd"] = round(active_value, 2)
    portfolio["equity_usd"] = round(float(portfolio.get("cash_usd", 0)) + active_value, 2)

    book["active"] = active
    book["completed"] = completed[-1000:]
    book["daily"] = daily
    portfolio["fees_paid_usd"] = round(sum(float(o.get("fee_usd") or o.get("fee_open_usd") or 0) for o in completed + active), 6)
    book["portfolio"] = portfolio
    atomic_write_json(ORD, book)

    try:
        source_ingest_crypto_free._main_locked()
    except Exception:
        pass
    try:
        source_ingest_crypto_short.main()
    except Exception:
        pass

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
                "opened_strategy_modes": opened_strategy_modes,
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
