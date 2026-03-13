#!/usr/bin/env python3
import json
from datetime import datetime, UTC, timedelta
from pathlib import Path

ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")
OUT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/learning_status.json")
REP = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/reports")


def parse_iso(ts: str):
    return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))


def semaforo(metrics: dict):
    n = metrics.get("trades_7d", 0)
    exp = metrics.get("expectancy_usd", 0.0)
    pf = metrics.get("profit_factor", 0.0)
    wr = metrics.get("win_rate", 0.0)

    # Criterio simple y honesto
    if n < 20 or exp <= 0 or pf < 1.0:
        return "ROJO", "Sin edge consistente todavía"
    if n < 60 or pf < 1.2 or wr < 45:
        return "AMARILLO", "Edge preliminar, seguir validando"
    return "VERDE", "Edge consistente en ventana reciente"


def main():
    data = {"completed": [], "active": [], "daily": {}, "portfolio": {}}
    if ORD.exists():
        data = json.loads(ORD.read_text(encoding="utf-8"))

    completed = data.get("completed", []) or []
    now = datetime.now(UTC)
    d7 = now - timedelta(days=7)

    rows = []
    for o in completed:
        try:
            dt = parse_iso(o.get("closed_at"))
            if dt >= d7:
                rows.append(o)
        except Exception:
            continue

    pnl = []
    wins = 0
    losses = 0
    gross_win = 0.0
    gross_loss = 0.0
    by_ticker = {}

    for o in rows:
        p = float(o.get("pnl_usd") or 0)
        pnl.append(p)
        t = str(o.get("ticker") or "?")
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
    OUT.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    REP.mkdir(parents=True, exist_ok=True)
    rp = REP / f"daily_learning_{now.date().isoformat()}.md"
    rp.write_text(
        "\n".join([
            f"# Aprendizaje Diario ({now.date().isoformat()})",
            f"- Semáforo: **{color}** ({reason})",
            f"- Trades 7d: {m['trades_7d']} (win-rate {m['win_rate']}%)",
            f"- Expectancy: {m['expectancy_usd']} USD/trade",
            f"- Profit factor: {m['profit_factor']}",
            f"- PnL 7d: {m['pnl_7d_usd']} USD",
            f"- Max drawdown: {m['max_drawdown_usd']} USD",
        ]),
        encoding="utf-8",
    )

    print(json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    main()
