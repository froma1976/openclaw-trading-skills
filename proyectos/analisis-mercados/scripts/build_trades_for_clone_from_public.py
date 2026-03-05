#!/usr/bin/env python3
import csv
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data")
SRC = BASE / "public_trader_histories_mql5_bulk_ok.csv"
OUT = BASE / "trades_for_clone.csv"


def asset_from_name(name: str) -> str:
    n = (name or "").upper()
    if "SOL" in n or "SOLANA" in n:
        return "SOLUSD"
    if "BTC" in n or "BITCOIN" in n:
        return "BTCUSD"
    return "CRYPTO"


def side_from_hint(name: str) -> str:
    n = (name or "").upper()
    if "SCALP" in n or "BREAKOUT" in n:
        return "mixed"
    return "mixed"


def market_condition_from_growth(g: str) -> str:
    s = (g or "").replace("%", "").replace(" ", "")
    try:
        v = float(s)
    except Exception:
        return "desconocida"
    if v >= 0:
        return "tendencia"
    return "rango"


def main():
    if not SRC.exists():
        raise SystemExit(f"No existe fuente: {SRC}")

    rows_out = []
    with SRC.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            signal = row.get("signal_name", "")
            rows_out.append(
                {
                    # esquema clone-friendly (trade-level), usando agregado público por señal
                    "fecha_entrada": row.get("started", ""),
                    "fecha_salida": "",
                    "activo": asset_from_name(signal),
                    "lado": side_from_hint(signal),
                    "precio_entrada": "",
                    "precio_salida": "",
                    "tamano_posicion": "",
                    "pnl_usd": row.get("profit", ""),
                    "pnl_pct": row.get("growth", ""),
                    "temporalidad": "intradia",
                    "condicion_mercado": market_condition_from_growth(row.get("growth", "")),
                    "fuente": "mql5-public",
                    "trader_id": row.get("url", ""),
                    # columnas de control calidad
                    "granularidad": "signal_aggregate",
                    "confidence": "media",
                    "notas": "Dato agregado de señal pública (no trade-by-trade).",
                    "trades_total": row.get("trades_total", ""),
                    "profit_factor": row.get("profit_factor", ""),
                    "expected_payoff": row.get("expected_payoff", ""),
                    "btc_deals": row.get("btc_deals", ""),
                    "sol_deals": row.get("sol_deals", ""),
                    "url": row.get("url", ""),
                }
            )

    fields = [
        "fecha_entrada",
        "fecha_salida",
        "activo",
        "lado",
        "precio_entrada",
        "precio_salida",
        "tamano_posicion",
        "pnl_usd",
        "pnl_pct",
        "temporalidad",
        "condicion_mercado",
        "fuente",
        "trader_id",
        "granularidad",
        "confidence",
        "notas",
        "trades_total",
        "profit_factor",
        "expected_payoff",
        "btc_deals",
        "sol_deals",
        "url",
    ]

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows_out)

    print(f"OK -> {OUT} rows={len(rows_out)}")


if __name__ == "__main__":
    main()
