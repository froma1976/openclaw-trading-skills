#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime, UTC
from pathlib import Path

import numpy as np

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"
MODELS = BASE / "models"


def load_close_series(symbol: str, interval: str):
    p = HIST / f"{symbol}_{interval}.csv"
    vals = []
    with p.open("r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            try:
                vals.append(float(r["close"]))
            except Exception:
                continue
    return np.array(vals, dtype=np.float32)


def make_dataset(series: np.ndarray, lookback: int = 32):
    X, y = [], []
    if len(series) <= lookback + 2:
        return np.array(X), np.array(y)
    for i in range(lookback, len(series) - 1):
        win = series[i - lookback:i]
        ret = (series[i + 1] / max(series[i], 1e-9)) - 1.0
        X.append(win)
        y.append(ret)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


class TinyLSTM(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.lstm = nn.LSTM(input_size=1, hidden_size=hidden, num_layers=1, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        o, _ = self.lstm(x)
        return self.head(o[:, -1, :])


def train_one(symbol: str, interval: str, lookback: int, epochs: int, batch_size: int = 512, max_samples: int = 120000):
    series = load_close_series(symbol, interval)
    X, y = make_dataset(series, lookback)
    if len(X) < 300:
        return {"symbol": symbol, "ok": False, "error": "datos insuficientes"}

    mu = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, keepdims=True) + 1e-8
    Xn = (X - mu) / sd

    n = len(Xn)
    cut = int(n * 0.8)
    Xtr, ytr = Xn[:cut], y[:cut]
    Xva, yva = Xn[cut:], y[cut:]

    # Limitar tamaño para no reventar RAM en histórico largo
    if len(Xtr) > max_samples:
        Xtr = Xtr[-max_samples:]
        ytr = ytr[-max_samples:]
    if len(Xva) > max(20000, max_samples // 5):
        keep = max(20000, max_samples // 5)
        Xva = Xva[-keep:]
        yva = yva[-keep:]

    Xtr_t = torch.tensor(Xtr, dtype=torch.float32).unsqueeze(-1)
    ytr_t = torch.tensor(ytr, dtype=torch.float32).unsqueeze(-1)
    Xva_t = torch.tensor(Xva, dtype=torch.float32).unsqueeze(-1)
    yva_t = torch.tensor(yva, dtype=torch.float32).unsqueeze(-1)

    model = TinyLSTM(hidden=32)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    tr_ds = torch.utils.data.TensorDataset(Xtr_t, ytr_t)
    tr_loader = torch.utils.data.DataLoader(tr_ds, batch_size=batch_size, shuffle=True)

    for _ in range(epochs):
        model.train()
        for xb, yb in tr_loader:
            pred = model(xb)
            loss = loss_fn(pred, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()

    model.eval()
    with torch.no_grad():
        va_pred = model(Xva_t)
        va_loss = loss_fn(va_pred, yva_t).item()

    MODELS.mkdir(parents=True, exist_ok=True)
    mp = MODELS / f"lstm_{symbol}.pt"
    torch.save(model.state_dict(), mp)

    meta = {
        "ticker": symbol,
        "interval": interval,
        "lookback": lookback,
        "epochs": epochs,
        "dataset_points": int(len(series)),
        "samples_train": int(len(Xtr)),
        "samples_val": int(len(Xva)),
        "val_mse": round(float(va_loss), 8),
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": f"history/{symbol}_{interval}.csv",
        "note": "Modelo confirmador (no decide solo).",
    }
    (MODELS / f"lstm_{symbol}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"symbol": symbol, "ok": True, "val_mse": meta["val_mse"], "points": len(series)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--interval", default="5m")
    ap.add_argument("--lookback", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=12)
    args = ap.parse_args()

    if torch is None:
        print(json.dumps({"ok": False, "error": "torch no instalado"}, ensure_ascii=False))
        return

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    out = {"ok": True, "results": []}
    for s in symbols:
        r = train_one(s, args.interval, args.lookback, args.epochs)
        out["results"].append(r)
        if not r.get("ok"):
            out["ok"] = False
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
