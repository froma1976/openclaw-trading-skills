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


def load_close_series(symbol: str, interval: str = "5m", limit: int = 600):
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


class TinyLSTM(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.lstm = nn.LSTM(input_size=1, hidden_size=hidden, num_layers=1, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        o, _ = self.lstm(x)
        last = o[:, -1, :]
        return self.head(last)


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

    # split
    n = len(Xn)
    cut = int(n * 0.8)
    Xtr, ytr = Xn[:cut], y[:cut]
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
    torch.save(model.state_dict(), mp)

    meta = {
        "ticker": args.ticker,
        "interval": args.interval,
        "lookback": args.lookback,
        "epochs": args.epochs,
        "val_mse": round(float(va_loss), 8),
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "note": "Modelo confirmador (no decide solo).",
    }
    (MODELS / f"lstm_{args.ticker}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "model": str(mp), "val_mse": meta["val_mse"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
