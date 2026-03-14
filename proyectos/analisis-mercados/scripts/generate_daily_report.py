#!/usr/bin/env python3
import json
from datetime import datetime, UTC
from pathlib import Path

BASE = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
SNAP = BASE / "data" / "latest_snapshot_free.json"
ORD = BASE / "data" / "orders_sim.json"
OUT = BASE / "data" / "daily_report_latest.txt"


def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:
        return default


def main():
    snap = load_json(SNAP, {})
    orders = load_json(ORD, {"pending": [], "completed": []})

    top = snap.get("top_opportunities", [])[:3]
    macro = snap.get("macro_regime", {})
    pending = orders.get("pending", [])
    completed = orders.get("completed", [])

    wins = sum(1 for o in completed if str(o.get("result", "")).lower() == "ganada")
    losses = sum(1 for o in completed if str(o.get("result", "")).lower() == "perdida")
    total = len(completed)
    wr = round((wins / total) * 100, 1) if total else 0.0

    vix = macro.get("vix")
    label = "🟡 NEUTRO"
    reason = "señales mixtas"
    try:
        if vix is not None and float(vix) < 18:
            label = "🟢 RISK-ON"; reason = "volatilidad baja"
        elif vix is not None and float(vix) > 22:
            label = "🔴 RISK-OFF"; reason = "volatilidad alta"
    except Exception:
        pass

    lines = []
    lines.append("📊 Reporte diario Alpha Scout (simulado)")
    lines.append(f"Hora: {datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00','Z')}")
    lines.append(f"Mercado hoy: {label} ({reason})")
    lines.append("")
    lines.append("Top 3 oportunidades:")
    if top:
        for t in top:
            st = t.get("state", "WATCH")
            st_es = "Vigilar" if st == "WATCH" else ("Casi lista" if st == "READY" else ("Lista para ejecutar" if st == "TRIGGERED" else st))
            lines.append(f"- {t.get('ticker')}: {st_es} · score {t.get('score_final', t.get('score', '-'))}")
    else:
        lines.append("- Sin oportunidades claras ahora.")

    lines.append("")
    lines.append(f"Órdenes pendientes: {len(pending)}")
    lines.append(f"Órdenes cerradas: {total} (ganadas: {wins}, perdidas: {losses}, win rate: {wr}%)")

    # --- RISK METRICS INTEGRADOS ---
    risk_path = BASE / "reports" / "risk_metrics.json"
    risk = load_json(risk_path, {})
    if risk.get("total_trades", 0) > 0:
        lines.append("")
        lines.append("📈 Risk Metrics (crypto sim):")
        lines.append(f"- Sharpe: {risk.get('sharpe_ratio', 'N/A')} | Sortino: {risk.get('sortino_ratio', 'N/A')}")
        lines.append(f"- PF: {risk.get('profit_factor', 'N/A')} | Max DD: ${risk.get('max_drawdown_usd', 'N/A')}")
        lines.append(f"- Kelly: {risk.get('kelly_pct', 'N/A')}%")

    # --- REGIME ---
    regime_path = BASE / "data" / "market_regime.json"
    regime = load_json(regime_path, {})
    btc_r = (regime.get("regimes") or {}).get("BTCUSDT", {})
    if btc_r.get("regime"):
        lines.append(f"- BTC Regime: {btc_r['regime']} (ADX={btc_r.get('adx', '?')}, Hurst={btc_r.get('hurst', '?')})")

    txt = "\n".join(lines)
    OUT.write_text(txt, encoding="utf-8")
    print(f"OK -> {OUT}")


if __name__ == "__main__":
    main()
