#!/usr/bin/env python3
import json
import csv
from datetime import datetime, UTC, timedelta
from pathlib import Path

from runtime_utils import atomic_write_json, atomic_write_text

ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")
TRADES = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/trades_clean.csv")
OUT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/learning_status.json")
REP = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/reports")
STABLECOIN_TICKERS = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE"}
EXCLUDED_TICKERS = {"PEPE"}


def parse_iso(ts: str):
    return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))


def semaforo(metrics: dict):
    n = metrics.get("trades_7d", 0)
    exp = metrics.get("expectancy_usd", 0.0)
    pf = metrics.get("profit_factor", 0.0)
    wr = metrics.get("win_rate", 0.0)

    # Criterio simple y honesto
    if n < 20 or exp <= 0 or pf < 1.0:
        return "ROJO", "Sin edge consistente todavia"
    if n < 60 or pf < 1.2 or wr < 45:
        return "AMARILLO", "Edge preliminar, seguir validando"
    return "VERDE", "Edge consistente en ventana reciente"


def main():
    now = datetime.now(UTC)
    d7 = now - timedelta(days=7)

    rows = []
    if TRADES.exists():
        with TRADES.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    dt = parse_iso(row.get("timestamp_exit") or row.get("closed_at") or "")
                    if dt >= d7:
                        rows.append(row)
                except Exception:
                    continue
    elif ORD.exists():
        data = json.loads(ORD.read_text(encoding="utf-8"))
        for order in data.get("completed", []) or []:
            try:
                dt = parse_iso(order.get("closed_at"))
                if dt >= d7:
                    rows.append(order)
            except Exception:
                continue

    rows.sort(key=lambda row: row.get("timestamp_exit") or row.get("closed_at") or "")

    pnl = []
    wins = 0
    losses = 0
    gross_win = 0.0
    gross_loss = 0.0
    by_ticker = {}

    for o in rows:
        t = str(o.get("ticker") or o.get("symbol") or "?")
        if t.upper() in STABLECOIN_TICKERS or t.upper() in EXCLUDED_TICKERS:
            continue
        p = float(o.get("pnl_usd") or 0)
        pnl.append(p)
        by_ticker.setdefault(t, {"count": 0, "pnl": 0.0})
        by_ticker[t]["count"] += 1
        by_ticker[t]["pnl"] += p

        if p > 0:
            wins += 1
            gross_win += p
        elif p < 0:
            losses += 1
            gross_loss += abs(p)

    n = len(pnl)
    expectancy = (sum(pnl) / n) if n else 0.0
    win_rate = (wins / n * 100.0) if n else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0)

    # drawdown simple sobre pnl acumulado
    peak = 0.0
    cur = 0.0
    max_dd = 0.0
    for x in pnl:
        cur += x
        peak = max(peak, cur)
        dd = peak - cur
        max_dd = max(max_dd, dd)

    m = {
        "as_of": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "trades_7d": n,
        "wins_7d": wins,
        "losses_7d": losses,
        "win_rate": round(win_rate, 2),
        "expectancy_usd": round(expectancy, 4),
        "profit_factor": round(profit_factor, 3),
        "pnl_7d_usd": round(sum(pnl), 4),
        "max_drawdown_usd": round(max_dd, 4),
    }
    color, reason = semaforo(m)
    m["semaforo"] = color
    m["reason"] = reason
    m["by_ticker"] = by_ticker

    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUT, m)

    REP.mkdir(parents=True, exist_ok=True)
    rp = REP / f"daily_learning_{now.date().isoformat()}.md"
    atomic_write_text(
        rp,
        "\n".join([
            f"# Aprendizaje Diario ({now.date().isoformat()})",
            f"- Semáforo: **{color}** ({reason})",
            f"- Trades 7d: {m['trades_7d']} (win-rate {m['win_rate']}%)",
            f"- Expectancy: {m['expectancy_usd']} USD/trade",
            f"- Profit factor: {m['profit_factor']}",
            f"- PnL 7d: {m['pnl_7d_usd']} USD",
            f"- Max drawdown: {m['max_drawdown_usd']} USD",
            "- Fuente prioritaria: trades_clean.csv (métricas depuradas)",
        ]),
    )

    print(json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    main()
