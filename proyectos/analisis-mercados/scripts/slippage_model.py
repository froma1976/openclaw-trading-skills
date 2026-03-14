#!/usr/bin/env python3
"""
Modelo de slippage realista basado en liquidez y volatilidad.

En vez de usar slippage fijo (5 bps), estima el slippage real
basado en: volumen del activo, spread tipico, ATR, y tamaño de la orden.

Uso como modulo:
  from slippage_model import estimate_slippage_bps
"""

import csv
from pathlib import Path
import numpy as np

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"


def get_recent_volume(symbol: str, interval: str = "15m", bars: int = 20) -> float:
    """Retorna volumen promedio reciente en unidades de la moneda base."""
    p = HIST / f"{symbol}_{interval}.csv"
    if not p.exists():
        return 0.0
    volumes = []
    with p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                volumes.append(float(row.get("volume", 0)))
            except (ValueError, KeyError):
                continue
    if not volumes:
        return 0.0
    return np.mean(volumes[-bars:])


def get_recent_atr(symbol: str, interval: str = "15m", period: int = 14) -> float:
    """Retorna ATR reciente como porcentaje del precio."""
    p = HIST / f"{symbol}_{interval}.csv"
    if not p.exists():
        return 0.0
    h, l, c = [], [], []
    with p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                h.append(float(row["high"]))
                l.append(float(row["low"]))
                c.append(float(row["close"]))
            except (ValueError, KeyError):
                continue
    if len(c) < period + 2:
        return 0.0

    # True Range de las ultimas N barras
    tr = []
    for i in range(-period, 0):
        tr_val = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        tr.append(tr_val)

    atr = np.mean(tr)
    price = c[-1]
    return (atr / price) if price > 0 else 0.0


def estimate_slippage_bps(
    symbol: str,
    order_notional_usd: float,
    price: float,
    interval: str = "15m",
    base_slippage_bps: float = 3.0,
) -> dict:
    """
    Estima slippage en basis points considerando:
    1. Base slippage (spread minimo tipico): ~3 bps para majors
    2. Liquidez: si el notional es grande relativo al volumen, mas slippage
    3. Volatilidad: ATR alto = mas slippage
    
    Retorna dict con: estimated_bps, components, confidence
    """
    avg_volume = get_recent_volume(symbol, interval)
    atr_pct = get_recent_atr(symbol, interval)

    # Component 1: Base spread
    # BTC/ETH: ~2-3 bps, altcoins: ~5-10 bps
    if symbol in {"BTCUSDT", "ETHUSDT"}:
        spread_bps = 2.0
    elif symbol in {"SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"}:
        spread_bps = 4.0
    else:
        spread_bps = 7.0

    # Component 2: Market impact (orden grande vs volumen)
    impact_bps = 0.0
    if avg_volume > 0 and price > 0:
        order_volume = order_notional_usd / price
        volume_ratio = order_volume / avg_volume
        # Regla empirica: impact ~ sqrt(volume_ratio) * factor
        impact_bps = min(20, max(0, (volume_ratio ** 0.5) * 15))
    
    # Component 3: Volatility premium
    vol_bps = 0.0
    if atr_pct > 0:
        # ATR > 1% = mercado volatile, mas slippage
        if atr_pct > 0.015:
            vol_bps = 5.0
        elif atr_pct > 0.008:
            vol_bps = 2.0
        else:
            vol_bps = 0.0

    total_bps = round(spread_bps + impact_bps + vol_bps, 2)
    
    # Confidence: alta si tenemos datos de volumen y ATR
    confidence = 0.3
    if avg_volume > 0:
        confidence += 0.35
    if atr_pct > 0:
        confidence += 0.35

    return {
        "estimated_bps": total_bps,
        "spread_bps": round(spread_bps, 2),
        "impact_bps": round(impact_bps, 2),
        "volatility_bps": round(vol_bps, 2),
        "confidence": round(confidence, 2),
        "avg_volume": round(avg_volume, 2),
        "atr_pct": round(atr_pct * 100, 4),
        "note": f"Slippage estimado vs fijo ({base_slippage_bps} bps). Usar max(estimado, fijo) para safety.",
    }
