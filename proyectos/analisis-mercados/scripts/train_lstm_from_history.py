#!/usr/bin/env python3
"""
Entrena modelos LSTM desde historico local con:
- EnhancedLSTM multi-feature (close, volume, ATR, RSI, log_return)
- Early stopping (patience-based)
- Gap/purge entre train/val
- Champion gating (solo reemplaza si mejora)
"""
import argparse
import csv
import json
from datetime import datetime, UTC
from pathlib import Path

import numpy as np

try:
    import torch
    import torch.nn as nn
except ImportError:
    torch = None
    nn = None

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"
MODELS = BASE / "models"

import sys
sys.path.insert(0, str(BASE / "models"))
sys.path.insert(0, str(BASE / "scripts"))
from architecture import TinyLSTM, EnhancedLSTM  # noqa: E402

# Importar feature engineering mejorado (graceful fallback)
try:
    from lstm_features import load_ohlcv, make_enhanced_dataset, FEATURE_COUNT
    HAS_ENHANCED = True
except ImportError:
    HAS_ENHANCED = False
    FEATURE_COUNT = 1


def load_close_series(symbol: str, interval: str):
    p = HIST / f"{symbol}_{interval}.csv"
    vals = []
    with p.open("r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            try:
                vals.append(float(r["close"]))
            except (ValueError, KeyError):
                continue
    return np.array(vals, dtype=np.float32)


def make_dataset_legacy(series: np.ndarray, lookback: int = 32):
    """Dataset legacy: solo close z-scored."""
    X, y = [], []
    if len(series) <= lookback + 2:
        return np.array(X), np.array(y)
    for i in range(lookback, len(series) - 1):
        win = series[i - lookback:i]
        ret = (series[i + 1] / max(series[i], 1e-9)) - 1.0
        X.append(win)
        y.append(ret)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def train_one(symbol: str, interval: str, lookback: int, epochs: int,
              batch_size: int = 512, max_samples: int = 120000, patience: int = 5):
    if torch is None:
        return {"symbol": symbol, "ok": False, "error": "torch no instalado"}

    # Intentar features mejoradas, fallback a legacy
    use_enhanced = False
    if HAS_ENHANCED:
        ohlcv_path = HIST / f"{symbol}_{interval}.csv"
        if ohlcv_path.exists():
            try:
                ohlcv = load_ohlcv(ohlcv_path)
                X, y = make_enhanced_dataset(ohlcv, lookback)
                if len(X) > 300:
                    use_enhanced = True
            except Exception:
                pass

    if not use_enhanced:
        series = load_close_series(symbol, interval)
        X, y = make_dataset_legacy(series, lookback)
        if len(X) < 300:
            return {"symbol": symbol, "ok": False, "error": "datos insuficientes"}
        # Z-score por ventana
        mu = X.mean(axis=1, keepdims=True)
        sd = X.std(axis=1, keepdims=True) + 1e-8
        X = (X - mu) / sd

    n = len(X)
    cut = int(n * 0.8)
    gap = lookback  # gap para evitar contaminacion
    Xtr, ytr = X[:cut], y[:cut]
    val_start = min(cut + gap, n)
    Xva, yva = X[val_start:], y[val_start:]
    if len(Xva) < 20:
        Xva, yva = X[cut:], y[cut:]

    # Limitar tamaño
    if len(Xtr) > max_samples:
        Xtr = Xtr[-max_samples:]
        ytr = ytr[-max_samples:]
    if len(Xva) > max(20000, max_samples // 5):
        keep = max(20000, max_samples // 5)
        Xva = Xva[-keep:]
        yva = yva[-keep:]

    # Preparar tensores
    if use_enhanced:
        # X shape: (samples, lookback, FEATURE_COUNT) -- ya tiene dimension features
        Xtr_t = torch.tensor(Xtr, dtype=torch.float32)
        ytr_t = torch.tensor(ytr, dtype=torch.float32).unsqueeze(-1)
        Xva_t = torch.tensor(Xva, dtype=torch.float32)
        yva_t = torch.tensor(yva, dtype=torch.float32).unsqueeze(-1)
        model = EnhancedLSTM(input_size=FEATURE_COUNT, hidden=48, dropout=0.15)
        model_type = "EnhancedLSTM"
    else:
        Xtr_t = torch.tensor(Xtr, dtype=torch.float32).unsqueeze(-1)
        ytr_t = torch.tensor(ytr, dtype=torch.float32).unsqueeze(-1)
        Xva_t = torch.tensor(Xva, dtype=torch.float32).unsqueeze(-1)
        yva_t = torch.tensor(yva, dtype=torch.float32).unsqueeze(-1)
        model = TinyLSTM(hidden=32)
        model_type = "TinyLSTM"

    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    tr_ds = torch.utils.data.TensorDataset(Xtr_t, ytr_t)
    tr_loader = torch.utils.data.DataLoader(tr_ds, batch_size=batch_size, shuffle=True)

    # --- EARLY STOPPING ---
    best_val_loss = float("inf")
    best_state = None
    patience_counter = 0

    for epoch in range(epochs):
        model.train()
        for xb, yb in tr_loader:
            pred = model(xb)
            loss = loss_fn(pred, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()

        # Eval
        model.eval()
        with torch.no_grad():
            va_pred = model(Xva_t)
            va_loss = loss_fn(va_pred, yva_t).item()

        if va_loss < best_val_loss:
            best_val_loss = va_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break  # early stop

    # Restaurar mejor modelo
    if best_state is not None:
        model.load_state_dict(best_state)
    va_loss = best_val_loss

    # --- CHAMPION GATING ---
    MODELS.mkdir(parents=True, exist_ok=True)
    mp = MODELS / f"lstm_{symbol}.pt"
    reg_path = MODELS / "registry.json"
    reg = {"version": 1, "symbols": {}}
    if reg_path.exists():
        try:
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
        except Exception:
            reg = {"version": 1, "symbols": {}}
    current_best = float(reg.get("symbols", {}).get(symbol, {}).get("best_val_mse", 999))
    is_champion = va_loss <= current_best

    if is_champion:
        torch.save(model.state_dict(), mp)
        champion_action = "PROMOTED"
    else:
        tmp_path = MODELS / f"lstm_{symbol}_candidate.pt"
        torch.save(model.state_dict(), tmp_path)
        champion_action = "REJECTED"

    stopped_early = patience_counter >= patience
    meta = {
        "ticker": symbol,
        "interval": interval,
        "lookback": lookback,
        "epochs_run": epoch + 1 if 'epoch' in dir() else epochs,
        "epochs_max": epochs,
        "early_stopped": stopped_early,
        "model_type": model_type,
        "features": FEATURE_COUNT if use_enhanced else 1,
        "dataset_points": int(n),
        "samples_train": int(len(Xtr)),
        "samples_val": int(len(Xva)),
        "val_mse": round(float(va_loss), 8),
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": f"history/{symbol}_{interval}.csv",
        "champion_action": champion_action,
        "previous_best_mse": round(current_best, 8) if current_best < 999 else None,
        "note": "Modelo confirmador (no decide solo).",
    }
    (MODELS / f"lstm_{symbol}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Actualizar registry
    sym_reg = reg.get("symbols", {}).get(symbol, {"history": []})
    sym_reg.setdefault("history", []).append({
        "at": meta["trained_at"],
        "val_mse": meta["val_mse"],
        "champion_action": champion_action,
        "model_type": model_type,
        "early_stopped": stopped_early,
        "model": str(mp if is_champion else MODELS / f"lstm_{symbol}_candidate.pt"),
        "meta": str(MODELS / f"lstm_{symbol}_meta.json"),
    })
    if is_champion:
        sym_reg["best_val_mse"] = meta["val_mse"]
        sym_reg["champion_model"] = str(mp)
    sym_reg["history"] = sym_reg["history"][-30:]
    reg.setdefault("symbols", {})[symbol] = sym_reg
    reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "symbol": symbol, "ok": True, "val_mse": meta["val_mse"],
        "points": n, "champion_action": champion_action,
        "model_type": model_type, "early_stopped": stopped_early,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--interval", default="5m")
    ap.add_argument("--lookback", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--patience", type=int, default=5)
    args = ap.parse_args()

    if torch is None:
        print(json.dumps({"ok": False, "error": "torch no instalado"}, ensure_ascii=False))
        return

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    out = {"ok": True, "results": []}
    for s in symbols:
        r = train_one(s, args.interval, args.lookback, args.epochs, patience=args.patience)
        out["results"].append(r)
        if not r.get("ok"):
            out["ok"] = False
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
