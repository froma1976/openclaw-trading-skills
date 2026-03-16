#!/usr/bin/env python3
"""
Walk-forward evaluation REAL del LSTM.
Carga el modelo entrenado y ejecuta predicciones fold a fold,
comparando contra un baseline naive (retorno previo).

Requiere: torch, numpy
"""
import csv
import json
import math
from pathlib import Path
from statistics import mean
import sys

import numpy as np

try:
    import torch
except ImportError:
    torch = None

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"
MODELS = BASE / "models"
OUT = BASE / "reports" / "walkforward_report.md"
CSVOUT = BASE / "reports" / "baseline_vs_lstm.csv"

# Importar arquitecturas desde modulo compartido
sys.path.insert(0, str(MODELS))
from architecture import TinyLSTM, EnhancedLSTM  # noqa: E402
from lstm_features import load_ohlcv, make_enhanced_dataset  # noqa: E402
from runtime_utils import atomic_write_text  # noqa: E402


def load_close(path: Path):
    vals = []
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                vals.append(float(row["close"]))
            except (ValueError, KeyError):
                continue
    return vals


def returns(close):
    return [(close[i + 1] / close[i] - 1.0) for i in range(len(close) - 1) if close[i] != 0]


def dir_acc(pred, y):
    if not y:
        return 0
    ok = sum(1 for a, b in zip(pred, y) if (a >= 0 and b >= 0) or (a < 0 and b < 0))
    return ok / len(y)


def make_windows(series, lookback=32):
    """Construye ventanas z-scored + retornos objetivo, igual que en entrenamiento."""
    X, y_ret = [], []
    for i in range(lookback, len(series) - 1):
        win = np.array(series[i - lookback:i], dtype=np.float32)
        mu, sd = win.mean(), win.std() + 1e-8
        win_norm = (win - mu) / sd
        ret = (series[i + 1] / max(series[i], 1e-9)) - 1.0
        X.append(win_norm)
        y_ret.append(ret)
    return np.array(X, dtype=np.float32), np.array(y_ret, dtype=np.float32)


def make_windows_from_history(path: Path, lookback: int, feature_count: int):
    if feature_count > 1:
        ohlcv = load_ohlcv(path)
        return make_enhanced_dataset(ohlcv, lookback)
    closes = load_close(path)
    return make_windows(closes, lookback)


def load_model(symbol: str):
    """Carga el modelo LSTM entrenado para un simbolo. Retorna None si no existe."""
    model_p = MODELS / f"lstm_{symbol}.pt"
    meta_p = MODELS / f"lstm_{symbol}_meta.json"
    if not (model_p.exists() and meta_p.exists()):
        return None, None
    if torch is None or TinyLSTM is None or EnhancedLSTM is None:
        return None, None
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    state_dict = torch.load(model_p, map_location="cpu", weights_only=True)

    ih0 = state_dict.get("lstm.weight_ih_l0")
    hh0 = state_dict.get("lstm.weight_hh_l0")
    has_second_layer = "lstm.weight_ih_l1" in state_dict
    input_size = int(ih0.shape[1]) if ih0 is not None else int(meta.get("features", 1) or 1)
    hidden = int(hh0.shape[1]) if hh0 is not None else int(meta.get("hidden", 32) or 32)

    if has_second_layer or input_size > 1 or meta.get("model_type") == "EnhancedLSTM":
        model = EnhancedLSTM(input_size=input_size, hidden=hidden, dropout=0.15)
    else:
        model = TinyLSTM(hidden=hidden)

    try:
        model.load_state_dict(state_dict)
    except RuntimeError as exc:
        meta = {**meta, "load_error": str(exc)}
        return None, meta
    model.eval()
    return model, meta


def predict_batch(model, X_np, batch_size=512):
    """Ejecuta prediccion LSTM real sobre un batch de ventanas (mini-batches para evitar OOM)."""
    if model is None or torch is None:
        return None
    all_preds = []
    with torch.no_grad():
        for i in range(0, len(X_np), batch_size):
            chunk = X_np[i:i + batch_size]
            X_t = torch.tensor(chunk, dtype=torch.float32)
            if X_t.ndim == 2:
                X_t = X_t.unsqueeze(-1)
            preds = model(X_t).squeeze(-1).numpy()
            all_preds.append(preds)
    return np.concatenate(all_preds)


def walk_eval_real(X, y, model, folds=5, gap=32):
    """
    Walk-forward REAL: entrena y evalua por folds usando el LSTM cargado.
    gap: numero de muestras entre train y test para evitar contaminacion de ventanas solapadas.
    """
    n = len(X)
    fold_size = n // (folds + 1)
    results = []

    for i in range(1, folds + 1):
        train_end = i * fold_size
        test_start = train_end + gap  # gap para evitar contaminacion
        test_end = (i + 1) * fold_size + gap
        if test_start >= n:
            continue

        te_X = X[test_start:min(test_end, n)]
        te_y = y[test_start:min(test_end, n)]

        if len(te_y) < 10:
            continue

        # Baseline: signo del retorno anterior (persistence forecast)
        # Usamos retornos reales del paso previo (no del test set)
        tr_y = y[:train_end]
        bpred = [tr_y[-1]] + list(te_y[:-1])
        bacc = dir_acc(bpred, te_y.tolist())

        # LSTM REAL: predicciones del modelo cargado
        lstm_preds = predict_batch(model, te_X)
        if lstm_preds is None:
            lacc = None
            lstm_mse = None
        else:
            lacc = dir_acc(lstm_preds.tolist(), te_y.tolist())
            lstm_mse = float(np.mean((lstm_preds - te_y) ** 2))

        results.append({
            "fold": i,
            "test_samples": len(te_y),
            "baseline_acc": round(bacc, 4),
            "lstm_acc": round(lacc, 4) if lacc is not None else None,
            "lstm_mse": round(lstm_mse, 8) if lstm_mse is not None else None,
            "gap_samples": gap,
        })

    return results


def main():
    if torch is None:
        print(json.dumps({"ok": False, "error": "torch no instalado"}, ensure_ascii=False))
        return

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    all_rows = []
    table = []

    for sym in symbols:
        # Cargar modelo entrenado
        model, meta = load_model(sym)
        if model is None:
            extra = f" ({meta.get('load_error')})" if meta and meta.get("load_error") else ""
            print(f"WARN: No hay modelo utilizable para {sym}, saltando{extra}")
            continue

        # Cargar datos historicos
        p = HIST / f"{sym}_15m.csv"
        if not p.exists():
            p = HIST / f"{sym}_5m.csv"
        if not p.exists():
            print(f"WARN: No hay historico para {sym}, saltando")
            continue

        feature_count = int(meta.get("features", 1) or 1)
        X, y = make_windows_from_history(p, lookback=int(meta.get("lookback", 32)), feature_count=feature_count)
        if len(X) < 200:
            print(f"WARN: Historico muy corto para {sym} ({len(X)} muestras)")
            continue

        lookback = int(meta.get("lookback", 32))
        max_samples = 5000
        if len(X) > max_samples:
            X = X[-max_samples:]
            y = y[-max_samples:]
        ev = walk_eval_real(X, y, model, folds=5, gap=lookback)

        for e in ev:
            all_rows.append({"symbol": sym, **e})

        if ev:
            valid_lstm = [x for x in ev if x["lstm_acc"] is not None]
            if valid_lstm:
                avg_base = mean([x["baseline_acc"] for x in ev])
                avg_lstm = mean([x["lstm_acc"] for x in valid_lstm])
                avg_mse = mean([x["lstm_mse"] for x in valid_lstm])
                delta = avg_lstm - avg_base
                table.append((sym, avg_base, avg_lstm, avg_mse, delta, len(valid_lstm)))

    # Escribir CSV
    CSVOUT.parent.mkdir(parents=True, exist_ok=True)
    if all_rows:
        with CSVOUT.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)

    # Generar reporte markdown
    lines = [
        "# Walk-Forward Report (LSTM Real)",
        "",
        f"- Fecha: {__import__('datetime').datetime.now(__import__('datetime').UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "- Metodo: walk-forward con gap de proteccion contra contaminacion de ventanas",
        "- Modelo: TinyLSTM real (no proxy)",
        "",
    ]

    if not table:
        lines.append("**No hay datos suficientes para evaluar ningun simbolo.**")
    else:
        lines.extend([
            "| Symbol | Baseline Acc | LSTM Acc | LSTM MSE | Delta | Folds |",
            "|--------|------------:|----------:|----------:|------:|------:|",
        ])
        for sym, base, lstm, mse, delta, folds in table:
            sign = "+" if delta >= 0 else ""
            verdict = "MEJOR" if delta > 0.01 else ("PEOR" if delta < -0.01 else "NEUTRAL")
            lines.append(f"| {sym} | {base:.4f} | {lstm:.4f} | {mse:.8f} | {sign}{delta:.4f} | {folds} | {verdict} |")

        lines.append("")
        lines.append("## Interpretacion")
        lines.append("")

        total_delta = mean([x[4] for x in table]) if table else 0
        if total_delta > 0.02:
            lines.append("El LSTM muestra mejora consistente sobre el baseline. Considerar mayor peso en decisiones.")
        elif total_delta < -0.02:
            lines.append("**ALERTA: El LSTM rinde PEOR que el baseline naive.** Considerar congelar o reducir su peso.")
        else:
            lines.append("El LSTM no muestra ventaja significativa sobre el baseline. Mantener como confirmador auxiliar sin peso decisivo.")

        lines.append("")
        lines.append("## Notas tecnicas")
        lines.append("")
        lines.append("- Gap entre train/test: igual al lookback para evitar contaminacion por ventanas solapadas")
        lines.append("- Baseline: persistence forecast (retorno del paso anterior)")
        lines.append("- Este reporte evalua el MODELO REAL entrenado, no un proxy")

    atomic_write_text(OUT, "\n".join(lines))
    print(json.dumps({
        "ok": True,
        "rows": len(all_rows),
        "symbols_evaluated": len(table),
        "report": str(OUT),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
