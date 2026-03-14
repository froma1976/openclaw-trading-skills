#!/usr/bin/env python3
"""
Feature engineering avanzado para el LSTM.
Genera features multi-dimension a partir de datos OHLCV:
- Close z-scored (feature original)
- Volumen z-scored
- ATR normalizado (volatilidad)
- RSI (momentum)
- Retorno logaritmico

Uso:
    from lstm_features import make_enhanced_dataset, FEATURE_COUNT
"""

import csv
import math
from pathlib import Path
import numpy as np

FEATURE_COUNT = 5  # close_z, volume_z, atr_norm, rsi_norm, log_return


def load_ohlcv(path: Path) -> dict:
    """Carga datos OHLCV desde CSV. Retorna dict con arrays numpy."""
    o, h, l, c, v = [], [], [], [], []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                o.append(float(row["open"]))
                h.append(float(row["high"]))
                l.append(float(row["low"]))
                c.append(float(row["close"]))
                v.append(float(row.get("volume", 0)))
            except (ValueError, KeyError):
                continue
    return {
        "open": np.array(o, dtype=np.float32),
        "high": np.array(h, dtype=np.float32),
        "low": np.array(l, dtype=np.float32),
        "close": np.array(c, dtype=np.float32),
        "volume": np.array(v, dtype=np.float32),
    }


def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range. Retorna array del mismo largo (primeros 'period' = NaN-like)."""
    n = len(close)
    atr = np.zeros(n, dtype=np.float32)
    if n < period + 1:
        return atr

    # True Range
    tr = np.zeros(n, dtype=np.float32)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # ATR = EMA del TR
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha

    return atr


def compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI clasico (Wilder). Retorna array 0-100."""
    n = len(close)
    rsi = np.full(n, 50.0, dtype=np.float32)
    if n < period + 2:
        return rsi

    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def compute_log_returns(close: np.ndarray) -> np.ndarray:
    """Retorno logaritmico. Primer valor = 0."""
    lr = np.zeros(len(close), dtype=np.float32)
    for i in range(1, len(close)):
        if close[i - 1] > 0:
            lr[i] = math.log(close[i] / close[i - 1])
    return lr


def make_enhanced_dataset(
    ohlcv: dict,
    lookback: int = 32,
    atr_period: int = 14,
    rsi_period: int = 14,
):
    """
    Construye dataset multi-feature para el LSTM.

    Retorna:
        X: (samples, lookback, FEATURE_COUNT) z-scored por ventana
        y: (samples,) retorno proximo paso
    """
    close = ohlcv["close"]
    volume = ohlcv["volume"]
    high = ohlcv["high"]
    low = ohlcv["low"]
    n = len(close)

    if n < lookback + max(atr_period, rsi_period) + 2:
        return np.array([]), np.array([])

    atr = compute_atr(high, low, close, atr_period)
    rsi = compute_rsi(close, rsi_period)
    log_ret = compute_log_returns(close)

    # Normalizar RSI a [-1, 1]
    rsi_norm = (rsi - 50.0) / 50.0
    # Normalizar ATR por precio
    atr_norm = np.zeros(n, dtype=np.float32)
    for i in range(n):
        atr_norm[i] = (atr[i] / close[i]) if close[i] > 0 else 0.0

    X_list = []
    y_list = []

    # Empezar despues de que todos los indicadores esten calientes
    start = max(lookback, atr_period + 1, rsi_period + 1)
    for i in range(start, n - 1):
        # Ventana de features
        win_close = close[i - lookback:i]
        win_vol = volume[i - lookback:i]
        win_atr = atr_norm[i - lookback:i]
        win_rsi = rsi_norm[i - lookback:i]
        win_lr = log_ret[i - lookback:i]

        # Z-score close y volume por ventana
        mu_c, sd_c = win_close.mean(), win_close.std() + 1e-8
        close_z = (win_close - mu_c) / sd_c

        mu_v, sd_v = win_vol.mean(), win_vol.std() + 1e-8
        vol_z = (win_vol - mu_v) / sd_v

        # Stack features: (lookback, 5)
        features = np.stack([close_z, vol_z, win_atr, win_rsi, win_lr], axis=-1)
        X_list.append(features)

        # Target: retorno proximo
        ret = (close[i + 1] / max(close[i], 1e-9)) - 1.0
        y_list.append(ret)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    return X, y


def make_single_prediction_input(ohlcv: dict, lookback: int = 32) -> np.ndarray | None:
    """
    Prepara un solo input de prediccion (la ventana mas reciente).
    Retorna: (1, lookback, FEATURE_COUNT) o None si datos insuficientes.
    """
    close = ohlcv["close"]
    n = len(close)
    if n < lookback + 16:
        return None

    atr = compute_atr(ohlcv["high"], ohlcv["low"], close)
    rsi = compute_rsi(close)
    log_ret = compute_log_returns(close)

    rsi_norm = (rsi - 50.0) / 50.0
    atr_norm = np.zeros(n, dtype=np.float32)
    for i in range(n):
        atr_norm[i] = (atr[i] / close[i]) if close[i] > 0 else 0.0
    volume = ohlcv["volume"]

    win_close = close[-lookback:]
    win_vol = volume[-lookback:]
    win_atr = atr_norm[-lookback:]
    win_rsi = rsi_norm[-lookback:]
    win_lr = log_ret[-lookback:]

    mu_c, sd_c = win_close.mean(), win_close.std() + 1e-8
    close_z = (win_close - mu_c) / sd_c
    mu_v, sd_v = win_vol.mean(), win_vol.std() + 1e-8
    vol_z = (win_vol - mu_v) / sd_v

    features = np.stack([close_z, vol_z, win_atr, win_rsi, win_lr], axis=-1)
    return features.reshape(1, lookback, FEATURE_COUNT)
