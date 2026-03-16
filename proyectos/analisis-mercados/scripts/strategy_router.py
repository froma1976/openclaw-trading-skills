#!/usr/bin/env python3
"""
Router de estrategia aditivo para OpenClaw.

Objetivo:
- mantener la logica actual como base
- detectar cuando el mercado entra en rango lateral claro
- activar un modo de mean reversion mas conservador sin romper el flujo existente
"""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean, pstdev

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"


def normalize_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    if raw.endswith(("USDT", "USDC", "BUSD", "FDUSD")):
        return raw
    return f"{raw}USDT"


def load_recent_ohlcv(symbol: str, intervals: tuple[str, ...] = ("15m", "5m"), max_rows: int = 220, history_root: Path | None = None) -> list[dict]:
    root = history_root or HIST
    symbol_pair = normalize_symbol(symbol)
    for interval in intervals:
        path = root / f"{symbol_pair}_{interval}.csv"
        if not path.exists():
            continue
        rows = []
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    rows.append(
                        {
                            "open": float(row["open"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "close": float(row["close"]),
                        }
                    )
                except (ValueError, KeyError):
                    continue
        if rows:
            return rows[-max_rows:]
    return []


def compute_range_reversion_context(
    symbol: str,
    current_price: float,
    lookback: int = 96,
    entry_zone_max: float = 0.36,
    range_width_pct_min: float = 1.2,
    range_width_pct_max: float = 12.0,
    max_rebound_pct: float = 2.2,
    history_root: Path | None = None,
) -> dict:
    rows = load_recent_ohlcv(symbol, max_rows=max(lookback + 20, 140), history_root=history_root)
    if len(rows) < max(lookback, 40) or current_price <= 0:
        return {
            "eligible": False,
            "reason": "sin historico suficiente para rango",
            "range_width_pct": 0.0,
            "range_position": 1.0,
            "rebound_pct_from_low": 999.0,
            "range_quality": 0.0,
        }

    window = rows[-lookback:]
    highs = [r["high"] for r in window]
    lows = [r["low"] for r in window]
    closes = [r["close"] for r in window]

    range_high = max(highs)
    range_low = min(lows)
    range_span = max(range_high - range_low, 1e-9)
    mid = (range_high + range_low) / 2.0
    range_width_pct = (range_span / max(mid, 1e-9)) * 100.0
    range_position = min(1.0, max(0.0, (current_price - range_low) / range_span))
    rebound_pct_from_low = ((current_price / max(range_low, 1e-9)) - 1.0) * 100.0

    mean_close = mean(closes)
    stdev_close = pstdev(closes) or 1e-9
    zscore = (current_price - mean_close) / stdev_close
    short_anchor = closes[-8] if len(closes) >= 8 else closes[0]
    short_momentum_pct = ((current_price / max(short_anchor, 1e-9)) - 1.0) * 100.0

    width_ok = range_width_pct_min <= range_width_pct <= range_width_pct_max
    position_ok = range_position <= entry_zone_max
    rebound_ok = rebound_pct_from_low <= max_rebound_pct
    zscore_ok = zscore <= 0.35
    momentum_ok = short_momentum_pct <= 1.5

    quality = max(0.0, 1.0 - range_position) * 0.45
    quality += max(0.0, min(1.0, (range_width_pct - range_width_pct_min) / max(range_width_pct_max - range_width_pct_min, 1e-9))) * 0.2
    quality += max(0.0, 1.0 - min(abs(zscore) / 2.0, 1.0)) * 0.2
    quality += max(0.0, 1.0 - min(rebound_pct_from_low / max(max_rebound_pct, 1e-9), 1.0)) * 0.15
    quality = round(min(1.0, max(0.0, quality)), 3)

    reasons = []
    if not width_ok:
        reasons.append(f"ancho {range_width_pct:.2f}% fuera de banda")
    if not position_ok:
        reasons.append(f"precio demasiado alto dentro del rango ({range_position:.2f})")
    if not rebound_ok:
        reasons.append(f"rebote desde minimo ya avanzado ({rebound_pct_from_low:.2f}%)")
    if not zscore_ok:
        reasons.append(f"precio no esta cerca de la mitad baja (z={zscore:.2f})")
    if not momentum_ok:
        reasons.append(f"impulso corto demasiado fuerte ({short_momentum_pct:.2f}%)")

    return {
        "eligible": width_ok and position_ok and rebound_ok and zscore_ok and momentum_ok,
        "reason": "; ".join(reasons) if reasons else f"rango valido {range_low:.4f}-{range_high:.4f}",
        "range_low": round(range_low, 6),
        "range_high": round(range_high, 6),
        "range_width_pct": round(range_width_pct, 4),
        "range_position": round(range_position, 4),
        "rebound_pct_from_low": round(rebound_pct_from_low, 4),
        "zscore": round(zscore, 4),
        "short_momentum_pct": round(short_momentum_pct, 4),
        "range_quality": quality,
    }


def compute_bull_trend_context(
    symbol: str,
    current_price: float,
    fast_bars: int = 20,
    slow_bars: int = 50,
    breakout_near_high_pct: float = 1.25,
    max_pullback_pct: float = 3.5,
    min_trend_strength_pct: float = 0.45,
    history_root: Path | None = None,
) -> dict:
    rows = load_recent_ohlcv(symbol, intervals=("5m", "15m"), max_rows=max(slow_bars + 40, 120), history_root=history_root)
    if len(rows) < max(slow_bars, 60) or current_price <= 0:
        return {
            "eligible": False,
            "reason": "sin historico suficiente para tendencia",
            "trend_strength_pct": 0.0,
            "pullback_from_high_pct": 999.0,
            "breakout_distance_pct": -999.0,
        }

    closes = [r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    fast_ma = mean(closes[-fast_bars:])
    slow_ma = mean(closes[-slow_bars:])
    trend_strength_pct = ((fast_ma / max(slow_ma, 1e-9)) - 1.0) * 100.0
    recent_high = max(highs[-fast_bars:])
    breakout_distance_pct = ((current_price / max(recent_high, 1e-9)) - 1.0) * 100.0
    pullback_from_high_pct = ((recent_high / max(current_price, 1e-9)) - 1.0) * 100.0
    short_anchor = closes[-12] if len(closes) >= 12 else closes[0]
    momentum_short_pct = ((current_price / max(short_anchor, 1e-9)) - 1.0) * 100.0

    above_fast = current_price >= fast_ma
    fast_above_slow = fast_ma > slow_ma
    near_high = pullback_from_high_pct <= max_pullback_pct and breakout_distance_pct >= -breakout_near_high_pct
    momentum_ok = momentum_short_pct >= 0.4
    trend_ok = trend_strength_pct >= min_trend_strength_pct

    reasons = []
    if not above_fast:
        reasons.append("precio por debajo de media rapida")
    if not fast_above_slow:
        reasons.append("media rapida no supera a media lenta")
    if not trend_ok:
        reasons.append(f"fuerza de tendencia insuficiente ({trend_strength_pct:.2f}%)")
    if not near_high:
        reasons.append(f"demasiado lejos del maximo reciente ({pullback_from_high_pct:.2f}%)")
    if not momentum_ok:
        reasons.append(f"impulso corto debil ({momentum_short_pct:.2f}%)")

    quality = 0.0
    quality += 0.3 if above_fast else 0.0
    quality += 0.2 if fast_above_slow else 0.0
    quality += max(0.0, min(0.25, trend_strength_pct / max(min_trend_strength_pct * 4.0, 1e-9)))
    quality += max(0.0, 0.15 - min(0.15, pullback_from_high_pct / max(max_pullback_pct * 10.0, 1e-9)))
    quality += max(0.0, min(0.1, momentum_short_pct / 10.0))
    quality = round(min(1.0, quality), 3)

    return {
        "eligible": above_fast and fast_above_slow and trend_ok and near_high and momentum_ok,
        "reason": "; ".join(reasons) if reasons else "continuacion alcista valida",
        "fast_ma": round(fast_ma, 6),
        "slow_ma": round(slow_ma, 6),
        "trend_strength_pct": round(trend_strength_pct, 4),
        "recent_high": round(recent_high, 6),
        "pullback_from_high_pct": round(pullback_from_high_pct, 4),
        "breakout_distance_pct": round(breakout_distance_pct, 4),
        "momentum_short_pct": round(momentum_short_pct, 4),
        "trend_quality": quality,
    }


def build_strategy_plan(
    candidate: dict,
    ticker: str,
    current_price: float,
    cfg: dict,
    market_regime: dict,
    symbol_regime: dict,
    history_root: Path | None = None,
) -> dict:
    plan = {
        "strategy_mode": "scalp_intradia",
        "target_multiplier": 1.0,
        "stop_multiplier": 1.0,
        "alloc_multiplier": 1.0,
        "timeout_multiplier": 1.0,
        "trail_activation_ratio_override": None,
        "trail_stop_profit_share_override": None,
        "target_extension_ratio_override": None,
        "target_extension_min_score_override": None,
        "min_score_override": None,
        "min_confluence_override": None,
        "reason": "modo base",
        "range_context": {},
        "bull_context": {},
    }

    score = int(candidate.get("score_final") or candidate.get("score") or 0)
    confluence = int(candidate.get("spy_confluence") or 0)
    breakout = int(candidate.get("spy_breakout") or 0)
    chart = int(candidate.get("spy_chart") or 0)
    chg_24h_pct = float(candidate.get("chg_24h_pct") or 0.0)
    chg_7d_pct = float(candidate.get("chg_7d_pct") or 0.0)
    market_regime_name = str(market_regime.get("regime") or "unknown")
    symbol_regime_name = str(symbol_regime.get("regime") or market_regime_name or "unknown")
    trend_regime_confidence = max(
        float(symbol_regime.get("confidence") or 0.0),
        float(market_regime.get("confidence") or 0.0),
    )
    range_regime_confidence = max(
        float(symbol_regime.get("confidence") or 0.0) if symbol_regime_name == "ranging" else 0.0,
        float(market_regime.get("confidence") or 0.0) if market_regime_name == "ranging" else 0.0,
    )

    bull_context = compute_bull_trend_context(
        ticker,
        current_price,
        fast_bars=int(cfg.get("bull_fast_bars", 20) or 20),
        slow_bars=int(cfg.get("bull_slow_bars", 50) or 50),
        breakout_near_high_pct=float(cfg.get("bull_breakout_near_high_pct", 1.25) or 1.25),
        max_pullback_pct=float(cfg.get("bull_max_pullback_pct", 3.5) or 3.5),
        min_trend_strength_pct=float(cfg.get("bull_min_trend_strength_pct", 0.45) or 0.45),
        history_root=history_root,
    )
    plan["bull_context"] = bull_context
    strong_countertrend_override = (
        chg_24h_pct >= float(cfg.get("bull_countertrend_override_24h", 5.0) or 5.0)
        and chg_7d_pct >= float(cfg.get("bull_countertrend_override_7d", 10.0) or 10.0)
        and (breakout > 0 or chart > 0 or confluence >= 3)
    )

    if bool(cfg.get("bull_trend_enabled", True)):
        bull_min_score = int(cfg.get("bull_min_score", 76) or 76)
        bull_min_confluence = int(cfg.get("bull_min_confluence", 2) or 2)
        bull_min_24h_pct = float(cfg.get("bull_min_24h_pct", 2.5) or 2.5)
        bull_min_7d_pct = float(cfg.get("bull_min_7d_pct", 6.0) or 6.0)
        snapshot_bullish_fallback = (
            str(bull_context.get("reason") or "").startswith("sin historico suficiente")
            and chg_24h_pct >= float(cfg.get("bull_nohistory_min_24h", 4.0) or 4.0)
            and chg_7d_pct >= float(cfg.get("bull_nohistory_min_7d", 9.0) or 9.0)
            and (breakout > 0 or chart > 0 or confluence >= 3)
        )
        severe_downtrend = (
            symbol_regime_name == "trending_down"
            and market_regime_name == "trending_down"
            and trend_regime_confidence >= float(cfg.get("bull_downtrend_block_confidence", 0.7) or 0.7)
        )
        if (
            score >= bull_min_score
            and confluence >= bull_min_confluence
            and chg_24h_pct >= bull_min_24h_pct
            and chg_7d_pct >= bull_min_7d_pct
            and (bull_context.get("eligible") or snapshot_bullish_fallback)
            and ((breakout > 0 or chart > 0 or confluence >= 3) or bull_context.get("trend_quality", 0.0) >= 0.72 or snapshot_bullish_fallback)
            and (not severe_downtrend or strong_countertrend_override)
        ):
            reason = (
                f"bull_trend snapshot: 24h={chg_24h_pct:.2f}%, 7d={chg_7d_pct:.2f}% sin historico local"
                if snapshot_bullish_fallback and not bull_context.get("eligible")
                else (
                    f"bull_trend activo: 24h={chg_24h_pct:.2f}%, 7d={chg_7d_pct:.2f}%, "
                    f"pullback={bull_context.get('pullback_from_high_pct', 0.0):.2f}%"
                )
            )
            plan.update(
                {
                    "strategy_mode": "bull_trend",
                    "target_multiplier": float(cfg.get("bull_target_pct_multiplier", 3.0) or 3.0),
                    "stop_multiplier": float(cfg.get("bull_stop_pct_multiplier", 1.35) or 1.35),
                    "alloc_multiplier": float(cfg.get("bull_alloc_multiplier", 0.85) or 0.85),
                    "timeout_multiplier": float(cfg.get("bull_timeout_multiplier", 4.5) or 4.5),
                    "trail_activation_ratio_override": float(cfg.get("bull_trail_activation_ratio", 1.0) or 1.0),
                    "trail_stop_profit_share_override": float(cfg.get("bull_trail_stop_profit_share", 0.62) or 0.62),
                    "target_extension_ratio_override": float(cfg.get("bull_target_extension_ratio", 1.1) or 1.1),
                    "target_extension_min_score_override": int(cfg.get("bull_target_extension_min_score", 74) or 74),
                    "min_score_override": bull_min_score,
                    "min_confluence_override": bull_min_confluence,
                    "reason": reason,
                }
            )
            return plan

    if not bool(cfg.get("range_mode_enabled", True)):
        plan["reason"] = "range mode desactivado"
        return plan

    if symbol_regime_name != "ranging" and market_regime_name != "ranging":
        plan["reason"] = f"regimen no lateral ({symbol_regime_name}/{market_regime_name})"
        return plan
    if range_regime_confidence < float(cfg.get("range_confidence_min", 0.55) or 0.55):
        plan["reason"] = f"confianza de rango insuficiente ({range_regime_confidence:.2f})"
        return plan
    if breakout > 0 or chart > 0:
        plan["reason"] = "setup parece breakout, no lateral"
        return plan
    if score < int(cfg.get("range_min_score", 68) or 68):
        plan["reason"] = f"score insuficiente para rango ({score})"
        return plan
    if confluence < int(cfg.get("range_min_confluence", 2) or 2):
        plan["reason"] = f"confluencia insuficiente para rango ({confluence})"
        return plan

    range_context = compute_range_reversion_context(
        ticker,
        current_price,
        lookback=int(cfg.get("range_lookback_bars", 96) or 96),
        entry_zone_max=float(cfg.get("range_entry_zone_max", 0.36) or 0.36),
        range_width_pct_min=float(cfg.get("range_width_pct_min", 1.2) or 1.2),
        range_width_pct_max=float(cfg.get("range_width_pct_max", 12.0) or 12.0),
        max_rebound_pct=float(cfg.get("range_max_rebound_pct", 2.2) or 2.2),
        history_root=history_root,
    )
    plan["range_context"] = range_context
    if not range_context.get("eligible"):
        plan["reason"] = f"rango descartado: {range_context.get('reason', 'sin contexto')}"
        return plan

    plan.update(
        {
            "strategy_mode": "range_lateral",
            "target_multiplier": float(cfg.get("range_target_pct_multiplier", 0.72) or 0.72),
            "stop_multiplier": float(cfg.get("range_stop_pct_multiplier", 0.78) or 0.78),
            "alloc_multiplier": float(cfg.get("range_alloc_multiplier", 0.75) or 0.75),
            "timeout_multiplier": float(cfg.get("range_timeout_multiplier", 0.65) or 0.65),
            "min_score_override": int(cfg.get("range_min_score", 68) or 68),
            "min_confluence_override": int(cfg.get("range_min_confluence", 2) or 2),
            "reason": (
                f"range_lateral activo: {symbol_regime_name}, conf={range_regime_confidence:.2f}, "
                f"pos={range_context.get('range_position', 1.0):.2f}, width={range_context.get('range_width_pct', 0.0):.2f}%"
            ),
        }
    )
    return plan


def build_grid_levels(range_low: float, range_high: float, levels: int) -> list[float]:
    steps = max(3, int(levels or 0))
    span = max(range_high - range_low, 1e-9)
    return [range_low + (span * idx / steps) for idx in range(steps + 1)]


def plan_range_grid(
    strategy_plan: dict,
    current_price: float,
    cfg: dict,
    active_grid_bands: set[int] | None = None,
    recent_grid_bands: set[int] | None = None,
) -> list[dict]:
    if str(strategy_plan.get("strategy_mode") or "") != "range_lateral":
        return []

    ctx = strategy_plan.get("range_context") or {}
    range_low = float(ctx.get("range_low") or 0.0)
    range_high = float(ctx.get("range_high") or 0.0)
    if current_price <= 0 or range_high <= range_low:
        return []

    grid_levels = build_grid_levels(range_low, range_high, int(cfg.get("range_grid_levels", 4) or 4))
    active_grid_bands = active_grid_bands or set()
    recent_grid_bands = recent_grid_bands or set()
    max_positions = max(1, int(cfg.get("range_grid_max_positions_per_ticker", 3) or 3))
    max_new_orders = max(1, int(cfg.get("range_grid_max_new_orders_per_cycle", 2) or 2))
    safety_buffer_pct = float(cfg.get("range_grid_safety_buffer_pct", 0.0025) or 0.0025)

    entries = []
    for band_idx in range(len(grid_levels) - 1):
        lower = grid_levels[band_idx]
        upper = grid_levels[band_idx + 1]
        if current_price < lower or current_price > upper:
            continue
        if band_idx >= len(grid_levels) - 2:
            continue
        if band_idx in active_grid_bands or band_idx in recent_grid_bands:
            continue

        target_level = grid_levels[min(len(grid_levels) - 1, band_idx + 1)]
        stop_anchor = max(range_low * (1.0 - safety_buffer_pct), range_low - ((range_high - range_low) * safety_buffer_pct))
        entry_discount = max(0.0, (upper - current_price) / max(upper - lower, 1e-9))
        size_scale = 1.0 + max(0.0, min(0.45, (0.5 - float(ctx.get("range_position") or 0.5))))
        entries.append(
            {
                "band_index": band_idx,
                "entry_floor": lower,
                "entry_ceiling": upper,
                "target_price": target_level,
                "stop_anchor": stop_anchor,
                "size_scale": round(size_scale + entry_discount * 0.15, 4),
                "grid_levels": [round(x, 6) for x in grid_levels],
            }
        )

    entries.sort(key=lambda item: item["band_index"])
    available_slots = max(0, max_positions - len(active_grid_bands))
    limit = min(max_new_orders, available_slots)
    return entries[:limit]
