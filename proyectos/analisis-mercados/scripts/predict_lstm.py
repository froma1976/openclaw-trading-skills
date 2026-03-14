#!/usr/bin/env python3
"""
Inferencia LSTM (confirmador): devuelve score de confirmación para BUY/AVOID.
No ejecuta órdenes; solo añade una señal de confianza.

Uso:
  py -3 scripts/predict_lstm.py --ticker BTCUSDT
"""

import argparse
import json
from pathlib import Path
from urllib import request
import numpy as np

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
MODELS = BASE / "models"


# TinyLSTM importado desde modulo compartido para evitar drift arquitectural
import sys
sys.path.insert(0, str(BASE / "models"))
from architecture import TinyLSTM  # noqa: E402


def get_json(url: str):
    req = request.Request(url, headers={"User-Agent": "lstm-predict/1.0"})
    with request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def load_close_series(symbol: str, interval: str = "5m", limit: int = 80):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = get_json(url)
    closes = [float(k[4]) for k in data if len(k) > 5]
    return np.array(closes, dtype=np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="BTCUSDT")
    args = parser.parse_args()

    if torch is None:
        print(json.dumps({"ok": False, "error": "torch no instalado"}, ensure_ascii=False))
        return

    meta_p = MODELS / f"lstm_{args.ticker}_meta.json"
    model_p = MODELS / f"lstm_{args.ticker}.pt"
    if not (meta_p.exists() and model_p.exists()):
        print(json.dumps({"ok": False, "error": "modelo no entrenado"}, ensure_ascii=False))
        return

    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    lookback = int(meta.get("lookback", 32))
    interval = meta.get("interval", "5m")

    series = load_close_series(args.ticker, interval, max(lookback + 40, 80))
    if len(series) < lookback + 2:
        print(json.dumps({"ok": False, "error": "datos insuficientes"}, ensure_ascii=False))
        return

    x = series[-lookback:]
    mu, sd = x.mean(), x.std() + 1e-8
    x = ((x - mu) / sd).astype(np.float32)

    model = TinyLSTM(hidden=32)
    model.load_state_dict(torch.load(model_p, map_location="cpu", weights_only=True))
    model.eval()

    with torch.no_grad():
        pred = model(torch.tensor(x).unsqueeze(0).unsqueeze(-1)).item()

    # pred es retorno esperado próximo; lo convertimos a score simple
    score = 50
    if pred > 0.0015:
        score = 80
    elif pred > 0.0005:
        score = 65
    elif pred < -0.0015:
        score = 20
    elif pred < -0.0005:
        score = 35

    out = {
        "ok": True,
        "ticker": args.ticker,
        "pred_return": round(float(pred), 6),
        "lstm_score": int(score),
        "lstm_vote": "BUY" if score >= 65 else "AVOID",
        "note": "Confirmador LSTM; no decide solo.",
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
