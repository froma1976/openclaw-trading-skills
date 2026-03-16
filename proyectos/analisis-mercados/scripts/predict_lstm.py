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
import csv

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
from architecture import TinyLSTM, EnhancedLSTM  # noqa: E402
sys.path.insert(0, str(BASE / "scripts"))
from lstm_features import load_ohlcv, make_single_prediction_input  # noqa: E402


def get_json(url: str):
    req = request.Request(url, headers={"User-Agent": "lstm-predict/1.0"})
    with request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def load_close_series(symbol: str, interval: str = "5m", limit: int = 80):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = get_json(url)
    closes = [float(k[4]) for k in data if len(k) > 5]
    return np.array(closes, dtype=np.float32)


def load_history_csv(symbol: str, interval: str) -> Path | None:
    hist = BASE / "data" / "history" / f"{symbol}_{interval}.csv"
    return hist if hist.exists() else None


def load_model(meta: dict, model_p: Path):
    state_dict = torch.load(model_p, map_location="cpu", weights_only=True)
    ih0 = state_dict.get("lstm.weight_ih_l0")
    hh0 = state_dict.get("lstm.weight_hh_l0")
    input_size = int(ih0.shape[1]) if ih0 is not None else int(meta.get("features", 1) or 1)
    hidden = int(hh0.shape[1]) if hh0 is not None else 32
    if input_size > 1 or meta.get("model_type") == "EnhancedLSTM" or "lstm.weight_ih_l1" in state_dict:
        model = EnhancedLSTM(input_size=input_size, hidden=hidden, dropout=0.15)
    else:
        model = TinyLSTM(hidden=hidden)
    model.load_state_dict(state_dict)
    model.eval()
    return model


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

    try:
        model = load_model(meta, model_p)
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": f"modelo incompatible: {exc}"}, ensure_ascii=False))
        return

    features = int(meta.get("features", 1) or 1)
    if features > 1:
        hist_csv = load_history_csv(args.ticker, interval)
        if hist_csv is None:
            print(json.dumps({"ok": False, "error": "historico local no disponible para features"}, ensure_ascii=False))
            return
        x = make_single_prediction_input(load_ohlcv(hist_csv), lookback)
        if x is None:
            print(json.dumps({"ok": False, "error": "datos insuficientes"}, ensure_ascii=False))
            return
        x_t = torch.tensor(x, dtype=torch.float32)
    else:
        series = load_close_series(args.ticker, interval, max(lookback + 40, 80))
        if len(series) < lookback + 2:
            print(json.dumps({"ok": False, "error": "datos insuficientes"}, ensure_ascii=False))
            return
        x = series[-lookback:]
        mu, sd = x.mean(), x.std() + 1e-8
        x = ((x - mu) / sd).astype(np.float32)
        x_t = torch.tensor(x).unsqueeze(0).unsqueeze(-1)

    with torch.no_grad():
        pred = model(x_t).item()

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
