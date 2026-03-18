#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ORD = BASE / "data" / "crypto_orders_sim.json"
SNAP = BASE / "data" / "crypto_snapshot_free.json"
OUT = BASE / "reports" / "lstm_attribution_report.md"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def summarize(rows):
    rows = rows or []
    if not rows:
        return {"count": 0, "pnl": 0.0, "wr": 0.0}
    pnl = sum(float(r.get("pnl_usd") or 0.0) for r in rows)
    wins = sum(1 for r in rows if float(r.get("pnl_usd") or 0.0) > 0)
    return {"count": len(rows), "pnl": round(pnl, 4), "wr": round((wins / len(rows)) * 100.0, 2)}


def main():
    book = load_json(ORD, {"completed": []})
    snap = load_json(SNAP, {"top_opportunities": []})
    completed = book.get("completed", []) or []
    traced = [r for r in completed if "lstm_vote" in r]
    aligned = [r for r in traced if r.get("lstm_alignment") == "aligned_buy"]
    conflicted = [r for r in traced if r.get("lstm_alignment") == "conflict_avoid"]
    unsupported = [r for r in completed if not r.get("lstm_supported")]

    top_lines = []
    for item in (snap.get("top_opportunities") or [])[:10]:
        top_lines.append(
            f"- {item.get('ticker')}: decision={item.get('decision_final')} score={item.get('score_final', item.get('score'))} confluence={item.get('spy_confluence')}"
        )

    lines = [
        "# LSTM attribution report",
        "",
        f"- Generated at: {datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')}",
        f"- Completed orders reviewed: {len(completed)}",
        f"- Orders with LSTM trace: {len(traced)}",
        "",
        "## Resumen de trazabilidad",
        f"- Alineadas con BUY LSTM: {json.dumps(summarize(aligned), ensure_ascii=False)}",
        f"- En conflicto con AVOID LSTM: {json.dumps(summarize(conflicted), ensure_ascii=False)}",
        f"- Sin soporte LSTM: {json.dumps(summarize(unsupported), ensure_ascii=False)}",
        "",
        "## Lectura",
        "- Si hay pocas o ninguna orden con LSTM trace, hasta ahora el sistema no estaba midiendo bien su impacto.",
        "- Este reporte sirve para empezar a separar problema de modelo vs problema de ejecucion.",
        "",
        "## Top oportunidades actuales",
    ]
    lines.extend(top_lines or ["- Sin snapshot disponible"])
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "report": str(OUT), "traced_orders": len(traced)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
