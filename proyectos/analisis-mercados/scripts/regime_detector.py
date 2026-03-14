#!/usr/bin/env python3
"""
Deteccion de regimen de mercado: trending, ranging, volatile.

Clasifica el estado actual del mercado usando:
- ADX (Average Directional Index) para tendencia
- ATR ratio para volatilidad relativa
- Hurst exponent estimado para mean-reversion vs momentum

Uso:
  py -3 scripts/regime_detector.py --symbol BTCUSDT --interval 15m
  
Como modulo:
  from regime_detector import detect_regime, RegimeResult
  result = detect_regime("BTCUSDT", "15m")
"""

import argparse
import csv
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path

import numpy as np

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"
OUT = BASE / "data" / "market_regime.json"


@dataclass
class RegimeResult:
    symbol: str
    interval: str
    regime: str  # "trending_up", "trending_down", "ranging", "volatile", "unknown"
    confidence: float  # 0-1
    adx: float
    atr_ratio: float  # ATR/price -- volatilidad relativa
    hurst: float  # <0.5 = mean-reverting, 0.5 = random, >0.5 = trending
    trend_direction: str  # "up", "down", "neutral"
    recommended_mode: str  # "aggressive", "normal", "defensive", "pause"
    param_adjustments: dict  # sugerencias de ajuste de parametros


def load_ohlcv(symbol: str, interval: str) -> dict:
    """Carga datos OHLCV desde historico local."""
    p = HIST / f"{symbol}_{interval}.csv"
    if not p.exists():
        return {}
    o, h, l, c, v = [], [], [], [], []
    with p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                o.append(float(row["open"]))
                h.append(float(row["high"]))
                l.append(float(row["low"]))
                c.append(float(row["close"]))
                v.append(float(row.get("volume", 0)))
            except (ValueError, KeyError):
                continue
    return {
        "open": np.array(o, dtype=np.float64),
        "high": np.array(h, dtype=np.float64),
        "low": np.array(l, dtype=np.float64),
        "close": np.array(c, dtype=np.float64),
        "volume": np.array(v, dtype=np.float64),
    }


def compute_adx(high, low, close, period=14):
    """Average Directional Index -- mide fuerza de tendencia (0-100)."""
    n = len(close)
    if n < period * 3:
        return 0.0

    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    tr = np.zeros(n)

    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # Wilders smoothing
    alpha = 1.0 / period
    atr_s = np.mean(tr[1:period + 1])
    plus_s = np.mean(plus_dm[1:period + 1])
    minus_s = np.mean(minus_dm[1:period + 1])

    dx_values = []
    for i in range(period + 1, n):
        atr_s = atr_s * (1 - alpha) + tr[i] * alpha
        plus_s = plus_s * (1 - alpha) + plus_dm[i] * alpha
        minus_s = minus_s * (1 - alpha) + minus_dm[i] * alpha

        if atr_s > 0:
            plus_di = 100 * plus_s / atr_s
            minus_di = 100 * minus_s / atr_s
        else:
            plus_di = 0.0
            minus_di = 0.0

        di_sum = plus_di + minus_di
        if di_sum > 0:
            dx = abs(plus_di - minus_di) / di_sum * 100
        else:
            dx = 0.0
        dx_values.append(dx)

    if not dx_values:
        return 0.0

    # ADX = media movil del DX
    adx = np.mean(dx_values[-period:])
    return round(float(adx), 2)


def compute_atr_ratio(high, low, close, period=14):
    """ATR / precio actual -- volatilidad relativa."""
    n = len(close)
    if n < period + 2:
        return 0.0

    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    atr = np.mean(tr[-period:])
    current_price = close[-1]
    if current_price <= 0:
        return 0.0
    return round(float(atr / current_price), 6)


def estimate_hurst(close, max_lags=20):
    """
    Estimacion del exponente de Hurst via R/S analysis.
    H < 0.5: mean-reverting (ranging)
    H ~ 0.5: random walk
    H > 0.5: trending/momentum
    """
    n = len(close)
    if n < 100:
        return 0.5

    log_returns = np.diff(np.log(close))
    lags = range(2, min(max_lags + 1, n // 4))
    rs_values = []

    for lag in lags:
        rs_list = []
        for start in range(0, len(log_returns) - lag, lag):
            segment = log_returns[start:start + lag]
            if len(segment) < 2:
                continue
            mean_seg = np.mean(segment)
            deviations = np.cumsum(segment - mean_seg)
            r = np.max(deviations) - np.min(deviations)
            s = np.std(segment, ddof=1)
            if s > 0:
                rs_list.append(r / s)
        if rs_list:
            rs_values.append((math.log(lag), math.log(np.mean(rs_list))))

    if len(rs_values) < 3:
        return 0.5

    # Linear regression: log(R/S) = H * log(n) + c
    x = np.array([v[0] for v in rs_values])
    y = np.array([v[1] for v in rs_values])
    n_pts = len(x)
    slope = (n_pts * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n_pts * np.sum(x ** 2) - np.sum(x) ** 2)
    return round(float(np.clip(slope, 0.0, 1.0)), 4)


def detect_trend_direction(close, short_window=10, long_window=40):
    """Detecta direccion de tendencia via EMAs."""
    n = len(close)
    if n < long_window + 5:
        return "neutral"

    ema_short = close[-short_window:].mean()
    ema_long = close[-long_window:].mean()
    pct_diff = (ema_short - ema_long) / ema_long * 100

    if pct_diff > 0.5:
        return "up"
    elif pct_diff < -0.5:
        return "down"
    return "neutral"


def detect_regime(symbol: str, interval: str = "15m") -> RegimeResult:
    """
    Detecta el regimen de mercado actual para un simbolo.
    """
    data = load_ohlcv(symbol, interval)
    if not data or len(data.get("close", [])) < 100:
        return RegimeResult(
            symbol=symbol, interval=interval, regime="unknown", confidence=0.0,
            adx=0.0, atr_ratio=0.0, hurst=0.5, trend_direction="neutral",
            recommended_mode="defensive", param_adjustments={},
        )

    high, low, close = data["high"], data["low"], data["close"]
    adx = compute_adx(high, low, close)
    atr_ratio = compute_atr_ratio(high, low, close)
    hurst = estimate_hurst(close)
    direction = detect_trend_direction(close)

    # Clasificacion de regimen
    regime = "unknown"
    confidence = 0.0
    recommended_mode = "normal"
    adjustments = {}

    # Volatile: ATR ratio alto
    atr_threshold_high = 0.025  # 2.5% de volatilidad relativa
    atr_threshold_normal = 0.012

    if atr_ratio > atr_threshold_high:
        regime = "volatile"
        confidence = min(1.0, atr_ratio / 0.04)
        recommended_mode = "defensive"
        adjustments = {
            "target_pct_multiplier": 1.3,  # targets mas amplios
            "stop_pct_multiplier": 1.2,  # stops mas amplios
            "alloc_multiplier": 0.6,  # menos capital por trade
            "max_positions_multiplier": 0.5,
            "reason": "Alta volatilidad -- reducir exposicion, ampliar stops y targets",
        }
    elif adx > 25 and hurst > 0.55:
        # Trending fuerte
        regime = f"trending_{direction}" if direction != "neutral" else "trending_up"
        confidence = min(1.0, (adx - 25) / 30 + (hurst - 0.5) * 2)
        recommended_mode = "aggressive" if direction == "up" else "defensive"
        adjustments = {
            "target_pct_multiplier": 1.2 if direction == "up" else 0.8,
            "stop_pct_multiplier": 0.9,  # trailing stops mas ceñidos
            "alloc_multiplier": 1.15 if direction == "up" else 0.7,
            "max_positions_multiplier": 1.0,
            "reason": f"Tendencia {direction} con ADX={adx:.0f}, Hurst={hurst:.2f}",
        }
    elif adx < 20 and hurst < 0.45:
        # Ranging / mean-reverting
        regime = "ranging"
        confidence = min(1.0, (20 - adx) / 15 + (0.5 - hurst) * 2)
        recommended_mode = "normal"
        adjustments = {
            "target_pct_multiplier": 0.8,  # targets mas conservadores
            "stop_pct_multiplier": 0.8,  # stops mas ceñidos
            "alloc_multiplier": 0.85,
            "max_positions_multiplier": 0.8,
            "reason": f"Mercado lateral (ADX={adx:.0f}, Hurst={hurst:.2f}) -- targets/stops ajustados",
        }
    else:
        # Transicion o indeterminado
        regime = "transitional"
        confidence = 0.3
        recommended_mode = "normal"
        adjustments = {
            "target_pct_multiplier": 1.0,
            "stop_pct_multiplier": 1.0,
            "alloc_multiplier": 0.9,
            "max_positions_multiplier": 1.0,
            "reason": "Regimen en transicion -- mantener parametros neutros",
        }

    confidence = round(min(1.0, max(0.0, confidence)), 3)

    return RegimeResult(
        symbol=symbol,
        interval=interval,
        regime=regime,
        confidence=confidence,
        adx=adx,
        atr_ratio=atr_ratio,
        hurst=hurst,
        trend_direction=direction,
        recommended_mode=recommended_mode,
        param_adjustments=adjustments,
    )


def main():
    parser = argparse.ArgumentParser(description="Market regime detector")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--all", action="store_true", help="Evaluar BTC, ETH, SOL")
    args = parser.parse_args()

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"] if args.all else [args.symbol]
    results = {}

    for sym in symbols:
        result = detect_regime(sym, args.interval)
        results[sym] = asdict(result)
        print(f"\n{'='*50}")
        print(f"REGIME: {sym} ({args.interval})")
        print(f"{'='*50}")
        print(f"Regimen:       {result.regime}")
        print(f"Confianza:     {result.confidence:.1%}")
        print(f"ADX:           {result.adx}")
        print(f"ATR ratio:     {result.atr_ratio:.4%}")
        print(f"Hurst:         {result.hurst}")
        print(f"Tendencia:     {result.trend_direction}")
        print(f"Modo sugerido: {result.recommended_mode}")
        if result.param_adjustments:
            print(f"Razon:         {result.param_adjustments.get('reason', '-')}")

    # Guardar resultado global
    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "regimes": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado en: {OUT}")
    print(json.dumps({"ok": True, "results": len(results)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
