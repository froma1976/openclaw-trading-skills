#!/usr/bin/env python3
"""
Monitor de correlacion entre posiciones activas.
Detecta concentracion de riesgo cuando multiples posiciones estan altamente correlacionadas.

Uso:
  py -3 scripts/correlation_monitor.py

Como modulo:
  from correlation_monitor import check_portfolio_correlation
"""

import csv
import json
from pathlib import Path

import numpy as np

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"
ORD = BASE / "data" / "crypto_orders_sim.json"
OUT = BASE / "data" / "correlation_analysis.json"


def load_close_series(symbol: str, interval: str = "15m", bars: int = 200) -> np.ndarray | None:
    """Carga ultimos N closes de historico local."""
    p = HIST / f"{symbol}_{interval}.csv"
    if not p.exists():
        return None
    closes = []
    with p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                closes.append(float(row["close"]))
            except (ValueError, KeyError):
                continue
    if len(closes) < 50:
        return None
    return np.array(closes[-bars:], dtype=np.float64)


def compute_returns(close: np.ndarray) -> np.ndarray:
    """Calcula retornos logaritmicos."""
    return np.diff(np.log(close))


def correlation_matrix(tickers: list[str], interval: str = "15m") -> tuple[np.ndarray, list[str]]:
    """
    Calcula matriz de correlacion entre tickers usando retornos.
    Retorna (matrix, valid_tickers) -- tickers para los que hay datos.
    """
    series = {}
    for t in tickers:
        close = load_close_series(t, interval)
        if close is not None:
            series[t] = compute_returns(close)

    valid = list(series.keys())
    if len(valid) < 2:
        return np.eye(len(valid)), valid

    # Alinear longitudes (todas al minimo)
    min_len = min(len(v) for v in series.values())
    aligned = np.array([series[t][-min_len:] for t in valid])

    corr = np.corrcoef(aligned)
    return corr, valid


def check_portfolio_correlation(
    active_tickers: list[str],
    interval: str = "15m",
    high_corr_threshold: float = 0.75,
) -> dict:
    """
    Analiza correlacion entre posiciones activas.

    Retorna:
        dict con: n_positions, pairs, max_corr, avg_corr, concentrated_risk, warnings
    """
    if len(active_tickers) < 2:
        return {
            "n_positions": len(active_tickers),
            "pairs": [],
            "max_corr": 0.0,
            "avg_corr": 0.0,
            "concentrated_risk": False,
            "warnings": [],
        }

    corr_matrix, valid = correlation_matrix(active_tickers, interval)
    n = len(valid)

    pairs = []
    all_corrs = []
    warnings = []
    high_corr_count = 0

    for i in range(n):
        for j in range(i + 1, n):
            c = round(float(corr_matrix[i, j]), 4)
            all_corrs.append(c)
            pairs.append({
                "ticker_a": valid[i],
                "ticker_b": valid[j],
                "correlation": c,
                "high": abs(c) > high_corr_threshold,
            })
            if abs(c) > high_corr_threshold:
                high_corr_count += 1
                warnings.append(
                    f"Alta correlacion ({c:.2f}) entre {valid[i]} y {valid[j]}: "
                    f"riesgo concentrado"
                )

    max_corr = round(max(all_corrs), 4) if all_corrs else 0.0
    avg_corr = round(float(np.mean(all_corrs)), 4) if all_corrs else 0.0
    concentrated = high_corr_count > n // 2  # mas de la mitad de pares altamente correlacionados

    if concentrated:
        warnings.append(
            f"RIESGO CONCENTRADO: {high_corr_count}/{len(pairs)} pares con corr > {high_corr_threshold}"
        )

    return {
        "n_positions": len(active_tickers),
        "n_with_data": n,
        "pairs": sorted(pairs, key=lambda x: -abs(x["correlation"])),
        "max_corr": max_corr,
        "avg_corr": avg_corr,
        "concentrated_risk": concentrated,
        "high_corr_pairs": high_corr_count,
        "warnings": warnings,
    }


def main():
    # Cargar posiciones activas
    if not ORD.exists():
        print(json.dumps({"ok": False, "error": "no hay libro de ordenes"}, ensure_ascii=False))
        return

    data = json.loads(ORD.read_text(encoding="utf-8"))
    active = data.get("active", []) or []
    tickers = list({str(o.get("ticker", "")).upper() for o in active if o.get("ticker")})

    if not tickers:
        print(json.dumps({"ok": True, "n_positions": 0, "msg": "sin posiciones activas"}, ensure_ascii=False))
        return

    result = check_portfolio_correlation(tickers)

    from datetime import datetime, UTC
    result["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Posiciones activas: {tickers}")
    print(f"Pares analizados:   {len(result['pairs'])}")
    print(f"Correlacion max:    {result['max_corr']}")
    print(f"Correlacion avg:    {result['avg_corr']}")
    print(f"Riesgo concentrado: {'SI' if result['concentrated_risk'] else 'NO'}")
    if result["warnings"]:
        for w in result["warnings"]:
            print(f"  WARN: {w}")
    print(json.dumps({"ok": True, "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
