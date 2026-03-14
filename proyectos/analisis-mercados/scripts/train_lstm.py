#!/usr/bin/env python3
"""
Entrenamiento LSTM básico (fase inicial, confirmador de señal).
Lee velas desde Binance, entrena un modelo simple por ticker y guarda:
- models/lstm_<TICKER>.pt
- models/lstm_<TICKER>_meta.json

Uso:
  py -3 scripts/train_lstm.py --ticker BTCUSDT
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, UTC

import numpy as np
from urllib import request
import csv

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
MODELS = BASE / "models"


def get_json(url: str):
    req = request.Request(url, headers={"User-Agent": "lstm-trainer/1.0"})
    with request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _load_close_from_csv(path: Path):
    if not path.exists():
        return None
    closes = []
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                closes.append(float(row.get("close")))
            except Exception:
                continue
    if not closes:
        return None
    return np.array(closes, dtype=np.float32)


def load_close_series(symbol: str, interval: str = "5m", limit: int = 600):
    # 1) Preferir histórico local incremental (más estable y reproducible)
    local_hist = BASE / "data" / "history" / f"{symbol}_{interval}.csv"
    arr = _load_close_from_csv(local_hist)
    if arr is not None and len(arr) >= 100:
        return arr

    # 2) Fallback público (CryptoDataDownload diario)
    public_hist = BASE / "data" / "history" / "public_ohlcv" / f"{symbol}_d.csv"
    arr = _load_close_from_csv(public_hist)
    if arr is not None and len(arr) >= 100:
        return arr

    # 3) Último fallback: API Binance live
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = get_json(url)
    closes = [float(k[4]) for k in data if len(k) > 5]
    return np.array(closes, dtype=np.float32)


def make_dataset(series: np.ndarray, lookback: int = 32):
    X, y = [], []
    if len(series) <= lookback + 2:
        return np.array(X), np.array(y)
    # objetivo: retorno próximo (1 paso)
    for i in range(lookback, len(series) - 1):
        win = series[i - lookback:i]
        ret = (series[i + 1] / max(series[i], 1e-9)) - 1.0
        X.append(win)
        y.append(ret)
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    return X, y


# TinyLSTM importado desde modulo compartido para evitar drift arquitectural
import sys
sys.path.insert(0, str(BASE / "models"))
from architecture import TinyLSTM  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="BTCUSDT")
    parser.add_argument("--interval", default="5m")
    parser.add_argument("--lookback", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()

    if torch is None:
        print("ERROR: torch no está instalado. Instala pytorch para entrenar LSTM.")
        return

    series = load_close_series(args.ticker, args.interval, 800)
    X, y = make_dataset(series, args.lookback)
    if len(X) < 50:
        print("ERROR: datos insuficientes para entrenar")
        return

    # normalización simple por ventana (z-score)
    mu = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, keepdims=True) + 1e-8
    Xn = (X - mu) / sd

    # split con gap/purge para evitar contaminacion por ventanas solapadas
    n = len(Xn)
    cut = int(n * 0.8)
    gap = args.lookback  # saltar 'lookback' muestras entre train y val
    Xtr, ytr = Xn[:cut], y[:cut]
    val_start = min(cut + gap, n)
    Xva, yva = Xn[val_start:], y[val_start:]
    if len(Xva) < 20:
        # Si el gap deja muy pocas muestras, reducir gap
        Xva, yva = Xn[cut:], y[cut:]

    Xtr_t = torch.tensor(Xtr).unsqueeze(-1)
    ytr_t = torch.tensor(ytr).unsqueeze(-1)
    Xva_t = torch.tensor(Xva).unsqueeze(-1)
    yva_t = torch.tensor(yva).unsqueeze(-1)

    model = TinyLSTM(hidden=32)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    for _ in range(args.epochs):
        model.train()
        pred = model(Xtr_t)
        loss = loss_fn(pred, ytr_t)
        opt.zero_grad()
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        va_pred = model(Xva_t)
        va_loss = loss_fn(va_pred, yva_t).item()

    MODELS.mkdir(parents=True, exist_ok=True)
    mp = MODELS / f"lstm_{args.ticker}.pt"

    # --- CHAMPION GATING: solo reemplazar modelo si val_mse mejora ---
    reg_path = MODELS / "registry.json"
    reg = {"version": 1, "symbols": {}}
    if reg_path.exists():
        try:
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    current_best = float(reg.get("symbols", {}).get(args.ticker, {}).get("best_val_mse", 999))
    is_champion = va_loss <= current_best

    if is_champion:
        torch.save(model.state_dict(), mp)
        champion_action = "PROMOTED"
    else:
        tmp_path = MODELS / f"lstm_{args.ticker}_candidate.pt"
        torch.save(model.state_dict(), tmp_path)
        champion_action = "REJECTED"

    meta = {
        "ticker": args.ticker,
        "interval": args.interval,
        "lookback": args.lookback,
        "epochs": args.epochs,
        "val_mse": round(float(va_loss), 8),
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "champion_action": champion_action,
        "previous_best_mse": round(current_best, 8) if current_best < 999 else None,
        "note": "Modelo confirmador de research. No usar para justificar dinero real sin validacion adicional.",
    }
    (MODELS / f"lstm_{args.ticker}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "model": str(mp), "val_mse": meta["val_mse"], "champion_action": champion_action}, ensure_ascii=False))


if __name__ == "__main__":
    main()
