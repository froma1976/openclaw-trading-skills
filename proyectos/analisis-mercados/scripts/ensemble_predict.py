#!/usr/bin/env python3
"""
Ensemble de modelos LSTM: promedia predicciones de los N mejores modelos historicos.

En vez de depender de un solo modelo (que puede ser inestable),
carga los K mejores modelos del registry y promedia sus predicciones.
Esto reduce la varianza de las predicciones.

Uso:
  py -3 scripts/ensemble_predict.py --ticker BTCUSDT --top-k 3

Como modulo:
  from ensemble_predict import ensemble_prediction
"""

import argparse
import json
from pathlib import Path

import numpy as np

try:
    import torch
except ImportError:
    torch = None

import sys

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
MODELS = BASE / "models"
sys.path.insert(0, str(MODELS))
from architecture import TinyLSTM  # noqa: E402


def load_registry() -> dict:
    reg_path = MODELS / "registry.json"
    if not reg_path.exists():
        return {"version": 1, "symbols": {}}
    return json.loads(reg_path.read_text(encoding="utf-8"))


def get_best_models(symbol: str, top_k: int = 3) -> list[dict]:
    """
    Obtiene los top_k mejores modelos del historial del registry.
    Filtra por champion_action=PROMOTED si esta disponible.
    """
    reg = load_registry()
    sym_data = reg.get("symbols", {}).get(symbol, {})
    history = sym_data.get("history", [])

    if not history:
        return []

    # Ordenar por val_mse ascendente (mejor primero)
    sorted_hist = sorted(history, key=lambda x: float(x.get("val_mse", 999)))

    # Filtrar: solo modelos que tienen archivo .pt existente
    # y preferir los que fueron PROMOTED
    promoted = [h for h in sorted_hist if h.get("champion_action") == "PROMOTED"]
    if len(promoted) >= top_k:
        return promoted[:top_k]

    # Si no hay suficientes promoted, usar los mejores por mse
    return sorted_hist[:top_k]


def load_close_series(symbol: str, interval: str = "5m", limit: int = 80):
    """Carga series de close desde Binance API."""
    from urllib import request as req
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    r = req.Request(url, headers={"User-Agent": "ensemble-predict/1.0"})
    with req.urlopen(r, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return np.array([float(k[4]) for k in data if len(k) > 5], dtype=np.float32)


def predict_single_model(model_path: Path, x_tensor, hidden: int = 32) -> float | None:
    """Carga un modelo y hace una prediccion. Retorna None si falla."""
    if torch is None or TinyLSTM is None:
        return None
    if not model_path.exists():
        return None
    try:
        model = TinyLSTM(hidden=hidden)
        model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
        model.eval()
        with torch.no_grad():
            pred = model(x_tensor).item()
        return pred
    except Exception:
        return None


def ensemble_prediction(symbol: str, top_k: int = 3, interval: str = "5m", lookback: int = 32) -> dict:
    """
    Genera prediccion ensemble promediando los top_k mejores modelos.

    Retorna:
        dict con: ok, pred_return, ensemble_score, individual_preds, agreement, n_models
    """
    if torch is None:
        return {"ok": False, "error": "torch no instalado"}

    # Cargar datos recientes
    try:
        series = load_close_series(symbol, interval, max(lookback + 40, 80))
    except Exception as e:
        return {"ok": False, "error": f"no se pudieron cargar datos: {e}"}

    if len(series) < lookback + 2:
        return {"ok": False, "error": "datos insuficientes"}

    # Preparar input
    x = series[-lookback:]
    mu, sd = x.mean(), x.std() + 1e-8
    x_norm = ((x - mu) / sd).astype(np.float32)
    x_tensor = torch.tensor(x_norm).unsqueeze(0).unsqueeze(-1)

    # Obtener mejores modelos
    best = get_best_models(symbol, top_k)
    if not best:
        # Fallback: usar el modelo principal si existe
        main_model = MODELS / f"lstm_{symbol}.pt"
        if main_model.exists():
            best = [{"model": str(main_model), "val_mse": 0}]
        else:
            return {"ok": False, "error": "no hay modelos disponibles"}

    # Predicciones individuales
    predictions = []
    model_info = []
    for entry in best:
        model_path = Path(entry.get("model", ""))
        if not model_path.exists():
            # Intentar el champion model
            model_path = MODELS / f"lstm_{symbol}.pt"
        pred = predict_single_model(model_path, x_tensor)
        if pred is not None:
            predictions.append(pred)
            model_info.append({
                "val_mse": entry.get("val_mse"),
                "pred": round(pred, 8),
                "at": entry.get("at", ""),
            })

    if not predictions:
        return {"ok": False, "error": "ningun modelo produjo prediccion"}

    # Ensemble: media ponderada por 1/val_mse (mejores modelos pesan mas)
    weights = []
    for entry in model_info:
        mse = float(entry.get("val_mse") or 1)
        w = 1.0 / max(mse, 1e-10)
        weights.append(w)

    total_w = sum(weights)
    weighted_pred = sum(p * w for p, w in zip(predictions, weights)) / total_w

    # Agreement: que porcentaje de modelos estan de acuerdo en la direccion
    n_pos = sum(1 for p in predictions if p > 0)
    n_neg = sum(1 for p in predictions if p <= 0)
    agreement = max(n_pos, n_neg) / len(predictions)

    # Score: similar a predict_lstm.py pero con ensemble
    score = 50
    if weighted_pred > 0.0015:
        score = 80
    elif weighted_pred > 0.0005:
        score = 65
    elif weighted_pred < -0.0015:
        score = 20
    elif weighted_pred < -0.0005:
        score = 35

    # Ajustar score por agreement
    if agreement < 0.6:
        # Baja concordancia -> reducir hacia neutral
        score = int(score * 0.7 + 50 * 0.3)

    vote = "BUY" if score >= 65 else "AVOID"

    return {
        "ok": True,
        "ticker": symbol,
        "pred_return": round(float(weighted_pred), 8),
        "ensemble_score": int(score),
        "ensemble_vote": vote,
        "agreement": round(agreement, 3),
        "n_models": len(predictions),
        "individual_preds": model_info,
        "note": "Ensemble LSTM (media ponderada por 1/val_mse).",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="BTCUSDT")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--interval", default="5m")
    args = parser.parse_args()

    result = ensemble_prediction(args.ticker, args.top_k, args.interval)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
