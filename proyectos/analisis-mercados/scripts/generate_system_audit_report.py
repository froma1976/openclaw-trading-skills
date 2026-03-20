#!/usr/bin/env python3
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
DATA = BASE / "data"
REPORTS = BASE / "reports"
LEARNING = DATA / "learning_status.json"
RISK = REPORTS / "risk_metrics.json"
ORDERS = DATA / "crypto_orders_sim.json"
TXT_OUT = DATA / "system_audit_latest.txt"
MD_OUT = REPORTS / "system_audit_latest.md"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def scheduler_health():
    script = BASE / "scripts" / "check_scheduler_health.ps1"
    if not script.exists():
        return {}
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            text=True,
            timeout=30,
            errors="ignore",
        )
        return json.loads(out)
    except Exception:
        return {}


def task_display(task: dict) -> str:
    name = task.get("task")
    state = task.get("state")
    result = task.get("last_result")
    status = task.get("status") or "unknown"
    detail = task.get("status_detail") or "na"
    return f"- {name}: state={state} last_result={result} status={status} detail={detail}"


def main():
    learning = load_json(LEARNING, {})
    risk = load_json(RISK, {})
    orders = load_json(ORDERS, {"active": [], "completed": [], "daily": {}, "portfolio": {}})
    health = scheduler_health()

    active = orders.get("active", []) or []
    completed = orders.get("completed", []) or []
    portfolio = orders.get("portfolio", {}) or {}
    daily = orders.get("daily", {}) or {}

    task_lines = []
    bad_tasks = []
    for task in health.get("tasks", []) or []:
        name = task.get("task")
        state = task.get("state")
        task_lines.append(task_display(task))
        if str(state).lower() not in {"ready", "running", "queued", "3", "4"}:
            bad_tasks.append(name)
        if task.get("is_bad"):
            bad_tasks.append(name)

    top_winners = sorted(
        ((k, v.get("pnl", 0.0)) for k, v in (learning.get("by_ticker") or {}).items()),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    top_losers = sorted(
        ((k, v.get("pnl", 0.0)) for k, v in (learning.get("by_ticker") or {}).items()),
        key=lambda item: item[1],
    )[:5]

    semaforo = learning.get("semaforo", "DESCONOCIDO")
    pf = learning.get("profit_factor", risk.get("profit_factor", 0))
    expectancy = learning.get("expectancy_usd", risk.get("avg_pnl_usd", 0))
    pnl_7d = learning.get("pnl_7d_usd", 0)
    trades_7d = learning.get("trades_7d", 0)
    wins = learning.get("wins_7d", 0)
    losses = learning.get("losses_7d", 0)
    cash = portfolio.get("cash_usd", 0)
    equity = portfolio.get("equity_usd", portfolio.get("cash_usd", 0))

    verdict = "OPERATIVO CON CAUTELA"
    if semaforo == "ROJO" or pf < 1 or expectancy <= 0:
        verdict = "NO LISTO PARA CAPITAL REAL"
    if bad_tasks:
        verdict = "RIESGO OPERATIVO: REVISAR TAREAS"

    recommendations = []
    if semaforo == "ROJO":
        recommendations.append("Mantener sim_only y no desplegar capital real.")
    if pf < 1:
        recommendations.append("Seguir priorizando calidad sobre cantidad de trades.")
    if expectancy <= 0:
        recommendations.append("No ampliar universo hasta ver expectancy positiva sostenida.")
    if bad_tasks:
        recommendations.append("Revisar tareas con ultimo resultado no cero.")
    if not recommendations:
        recommendations.append("Mantener disciplina actual y seguir validando.")

    ts = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    text_lines = [
        f"OpenClaw audit {ts}",
        f"Veredicto: {verdict}",
        f"Semaforo: {semaforo} | PF: {pf} | Expectancy: {expectancy} | PnL 7d: {pnl_7d}",
        f"Trades 7d: {trades_7d} | Wins: {wins} | Losses: {losses}",
        f"Cash: {cash} | Equity: {equity} | Activas: {len(active)} | Cerradas: {len(completed)} | Trades hoy: {daily.get('trades', 0)}",
        f"Dashboard: {health.get('dashboard_health', 'down')} | Gateway: {health.get('gateway_18789', False)}",
        f"Node host: {health.get('node_host_running', False)} | LSTM 6h lock: {(health.get('lstm_6h_lock') or {}).get('exists', False)}",
        "Mejores tickers recientes: " + (", ".join(f"{k} {v:.3f}" for k, v in top_winners) if top_winners else "sin datos"),
        "Peores tickers recientes: " + (", ".join(f"{k} {v:.3f}" for k, v in top_losers) if top_losers else "sin datos"),
        "Recomendaciones:",
    ]
    text_lines.extend(f"- {item}" for item in recommendations)

    md_lines = [
        "# OpenClaw system audit",
        "",
        f"- Generated at: {ts}",
        f"- Verdict: {verdict}",
        "",
        "## Estado del edge",
        f"- Semaforo: {semaforo}",
        f"- Profit factor: {pf}",
        f"- Expectancy USD: {expectancy}",
        f"- PnL 7d USD: {pnl_7d}",
        f"- Trades 7d: {trades_7d} (wins {wins}, losses {losses})",
        "",
        "## Estado operativo",
        f"- Dashboard health: {health.get('dashboard_health', 'down')}",
        f"- Gateway 18789: {health.get('gateway_18789', False)}",
        f"- Node host running: {health.get('node_host_running', False)}",
        f"- LSTM 6h lock: {(health.get('lstm_6h_lock') or {}).get('exists', False)} age_min={(health.get('lstm_6h_lock') or {}).get('age_minutes', 'na')} active_processes={(health.get('lstm_6h_lock') or {}).get('active_processes', 'na')}",
        f"- Cash USD: {cash}",
        f"- Equity USD: {equity}",
        f"- Active orders: {len(active)}",
        f"- Completed orders: {len(completed)}",
        "",
        "## Tareas programadas",
    ]
    md_lines.extend(task_lines or ["- Sin datos de scheduler"])
    md_lines.extend([
        "",
        "## Recomendaciones",
    ])
    md_lines.extend(f"- {item}" for item in recommendations)

    TXT_OUT.write_text("\n".join(text_lines), encoding="utf-8")
    MD_OUT.write_text("\n".join(md_lines), encoding="utf-8")
    print(json.dumps({"ok": True, "txt": str(TXT_OUT), "md": str(MD_OUT), "verdict": verdict}, ensure_ascii=False))


if __name__ == "__main__":
    main()
