#!/usr/bin/env python3
"""
Risk-adjusted metrics para el portfolio de trading.
Calcula: Sharpe, Sortino, Calmar, Max Drawdown, Recovery Factor.

Uso:
  py -3 scripts/risk_metrics.py
  
Como modulo:
  from risk_metrics import compute_risk_metrics, RiskReport
"""

import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ORD = BASE / "data" / "crypto_orders_sim.json"
OUT = BASE / "reports" / "risk_metrics.json"
MD_OUT = BASE / "reports" / "risk_metrics.md"


@dataclass
class RiskReport:
    total_trades: int = 0
    total_pnl_usd: float = 0.0
    win_rate: float = 0.0
    avg_pnl_usd: float = 0.0
    std_pnl_usd: float = 0.0
    sharpe_ratio: float = 0.0  # (mean / std) * sqrt(252)
    sortino_ratio: float = 0.0  # (mean / downside_std) * sqrt(252)
    calmar_ratio: float = 0.0  # annualized_return / max_drawdown
    max_drawdown_usd: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: int = 0  # en trades
    recovery_factor: float = 0.0  # total_pnl / max_drawdown
    profit_factor: float = 0.0
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    win_loss_ratio: float = 0.0
    expectancy_r: float = 0.0  # (WR * avg_win - LR * avg_loss) / avg_loss
    kelly_pct: float = 0.0  # Kelly criterion optimal sizing
    consecutive_wins_max: int = 0
    consecutive_losses_max: int = 0
    equity_curve: list = None


def compute_risk_metrics(pnls: list[float], capital: float = 300.0, trades_per_day: float = 20.0) -> RiskReport:
    """
    Calcula metricas de riesgo completas a partir de una lista de PnL por trade.
    
    Args:
        pnls: lista de PnL en USD por trade (orden cronologico)
        capital: capital inicial
        trades_per_day: trades promedio por dia (para anualizacion)
    """
    report = RiskReport()
    n = len(pnls)
    report.total_trades = n

    if n == 0:
        return report

    report.total_pnl_usd = round(sum(pnls), 4)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    report.win_rate = round(len(wins) / n * 100, 2)
    report.avg_pnl_usd = round(sum(pnls) / n, 6)

    # Std
    mean_pnl = report.avg_pnl_usd
    variance = sum((p - mean_pnl) ** 2 for p in pnls) / max(1, n - 1)
    std_pnl = math.sqrt(variance)
    report.std_pnl_usd = round(std_pnl, 6)

    # Sharpe ratio (annualized)
    # annualization = sqrt(trades_per_year)
    trades_per_year = trades_per_day * 365
    if std_pnl > 0:
        report.sharpe_ratio = round((mean_pnl / std_pnl) * math.sqrt(trades_per_year), 4)

    # Sortino ratio (solo downside deviation)
    downside_returns = [min(0, p - 0) for p in pnls]  # target = 0
    downside_variance = sum(d ** 2 for d in downside_returns) / max(1, n - 1)
    downside_std = math.sqrt(downside_variance)
    if downside_std > 0:
        report.sortino_ratio = round((mean_pnl / downside_std) * math.sqrt(trades_per_year), 4)

    # Max Drawdown
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    max_dd_start = 0
    dd_duration = 0
    max_dd_duration = 0
    equity_curve = [0.0]

    for i, p in enumerate(pnls):
        equity += p
        equity_curve.append(round(equity, 4))
        if equity > peak:
            peak = equity
            dd_duration = 0
        else:
            dd_duration += 1
            max_dd_duration = max(max_dd_duration, dd_duration)
        dd = peak - equity
        max_dd = max(max_dd, dd)

    report.max_drawdown_usd = round(max_dd, 4)
    report.max_drawdown_pct = round((max_dd / capital) * 100, 2) if capital > 0 else 0
    report.max_drawdown_duration = max_dd_duration
    report.equity_curve = equity_curve

    # Calmar ratio
    annualized_return = mean_pnl * trades_per_year
    if max_dd > 0:
        report.calmar_ratio = round(annualized_return / max_dd, 4)

    # Recovery factor
    if max_dd > 0:
        report.recovery_factor = round(report.total_pnl_usd / max_dd, 4)

    # Profit Factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    report.profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else 999.0

    # Win/loss ratio
    report.avg_win_usd = round(sum(wins) / len(wins), 6) if wins else 0
    report.avg_loss_usd = round(sum(losses) / len(losses), 6) if losses else 0
    report.win_loss_ratio = round(
        abs(report.avg_win_usd / report.avg_loss_usd), 4
    ) if report.avg_loss_usd != 0 else 999.0

    # Expectancy in R
    if report.avg_loss_usd != 0:
        wr = len(wins) / n
        lr = len(losses) / n
        report.expectancy_r = round(
            (wr * abs(report.avg_win_usd) - lr * abs(report.avg_loss_usd)) / abs(report.avg_loss_usd), 4
        )

    # Kelly criterion
    if report.win_loss_ratio > 0:
        wr = len(wins) / n
        b = report.win_loss_ratio
        kelly = wr - (1 - wr) / b if b > 0 else 0
        report.kelly_pct = round(max(0, kelly) * 100, 2)

    # Consecutive wins/losses
    max_cw = 0
    max_cl = 0
    cw = 0
    cl = 0
    for p in pnls:
        if p > 0:
            cw += 1
            cl = 0
            max_cw = max(max_cw, cw)
        else:
            cl += 1
            cw = 0
            max_cl = max(max_cl, cl)
    report.consecutive_wins_max = max_cw
    report.consecutive_losses_max = max_cl

    return report


def load_completed_pnls() -> list[float]:
    """Carga PnLs de trades completados del libro de ordenes."""
    if not ORD.exists():
        return []
    data = json.loads(ORD.read_text(encoding="utf-8"))
    completed = data.get("completed", []) or []
    pnls = []
    for o in completed:
        pnl = o.get("pnl_usd")
        if pnl is not None:
            try:
                pnls.append(float(pnl))
            except (ValueError, TypeError):
                continue
    return pnls


def generate_markdown(report: RiskReport) -> str:
    """Genera reporte markdown bonito."""
    lines = [
        "# Risk-Adjusted Metrics Report",
        "",
        f"- Fecha: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Trades: {report.total_trades}",
        "",
        "## Performance",
        "",
        f"| Metrica | Valor |",
        f"|---------|------:|",
        f"| Total PnL | ${report.total_pnl_usd:.2f} |",
        f"| Win Rate | {report.win_rate:.1f}% |",
        f"| Profit Factor | {report.profit_factor:.2f} |",
        f"| Avg PnL/trade | ${report.avg_pnl_usd:.4f} |",
        f"| Avg Win | ${report.avg_win_usd:.4f} |",
        f"| Avg Loss | ${report.avg_loss_usd:.4f} |",
        f"| Win/Loss Ratio | {report.win_loss_ratio:.2f} |",
        "",
        "## Risk Metrics",
        "",
        f"| Metrica | Valor |",
        f"|---------|------:|",
        f"| **Sharpe Ratio** | **{report.sharpe_ratio:.2f}** |",
        f"| **Sortino Ratio** | **{report.sortino_ratio:.2f}** |",
        f"| **Calmar Ratio** | **{report.calmar_ratio:.2f}** |",
        f"| Max Drawdown | ${report.max_drawdown_usd:.2f} ({report.max_drawdown_pct:.1f}%) |",
        f"| Max DD Duration | {report.max_drawdown_duration} trades |",
        f"| Recovery Factor | {report.recovery_factor:.2f} |",
        "",
        "## Sizing",
        "",
        f"| Metrica | Valor |",
        f"|---------|------:|",
        f"| Expectancy (R) | {report.expectancy_r:.3f} |",
        f"| Kelly % | {report.kelly_pct:.1f}% |",
        f"| Max Win Streak | {report.consecutive_wins_max} |",
        f"| Max Loss Streak | {report.consecutive_losses_max} |",
        "",
        "## Interpretacion",
        "",
    ]

    if report.sharpe_ratio > 1.5:
        lines.append("Sharpe > 1.5: excelente relacion riesgo/retorno.")
    elif report.sharpe_ratio > 0.5:
        lines.append("Sharpe 0.5-1.5: aceptable pero mejorable.")
    elif report.sharpe_ratio > 0:
        lines.append("Sharpe 0-0.5: retorno bajo para el riesgo asumido.")
    else:
        lines.append("**Sharpe negativo: el sistema pierde dinero ajustado por riesgo.**")

    if report.calmar_ratio > 2:
        lines.append("Calmar > 2: buen ratio retorno/drawdown.")
    elif report.calmar_ratio < 0:
        lines.append("**Calmar negativo: el sistema no ha recuperado su peor drawdown.**")

    if report.kelly_pct > 0:
        lines.append(f"Kelly sugiere apostar max {report.kelly_pct:.0f}% del capital por trade.")
    else:
        lines.append("**Kelly negativo: no hay edge positivo. No se deberia operar.**")

    return "\n".join(lines)


def main():
    pnls = load_completed_pnls()
    if not pnls:
        print(json.dumps({"ok": False, "error": "no hay trades completados"}, ensure_ascii=False))
        return

    report = compute_risk_metrics(pnls)

    # Guardar JSON
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report_dict = asdict(report)
    report_dict["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    OUT.write_text(json.dumps(report_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    # Guardar Markdown
    md = generate_markdown(report)
    MD_OUT.write_text(md, encoding="utf-8")

    # Resumen en consola
    print(f"\n{'='*50}")
    print(f"RISK METRICS ({report.total_trades} trades)")
    print(f"{'='*50}")
    print(f"Total PnL:         ${report.total_pnl_usd:.2f}")
    print(f"Win Rate:          {report.win_rate:.1f}%")
    print(f"Sharpe:            {report.sharpe_ratio:.2f}")
    print(f"Sortino:           {report.sortino_ratio:.2f}")
    print(f"Calmar:            {report.calmar_ratio:.2f}")
    print(f"Max Drawdown:      ${report.max_drawdown_usd:.2f} ({report.max_drawdown_pct:.1f}%)")
    print(f"Profit Factor:     {report.profit_factor:.2f}")
    print(f"Kelly %:           {report.kelly_pct:.1f}%")
    print(f"\nReportes: {OUT} / {MD_OUT}")
    print(json.dumps({"ok": True, "trades": report.total_trades}, ensure_ascii=False))


if __name__ == "__main__":
    main()
