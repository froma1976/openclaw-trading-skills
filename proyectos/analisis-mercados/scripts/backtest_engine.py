#!/usr/bin/env python3
"""
Motor de backtesting basico para evaluar parametros de trading sobre datos historicos.

Uso:
  py -3 scripts/backtest_engine.py --symbol BTCUSDT --interval 15m
  py -3 scripts/backtest_engine.py --symbol BTCUSDT --interval 15m --target-pct 1.2 --stop-pct 0.6

Lee velas historicas de data/history/ y simula la logica de entrada/salida del autopilot.
Genera un reporte con metricas clave: win rate, expectancy, profit factor, max drawdown, Sharpe.
"""

import argparse
import csv
import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from pathlib import Path
from statistics import mean, stdev

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"
REPORTS = BASE / "reports"


@dataclass
class TradeResult:
    entry_price: float
    exit_price: float
    entry_idx: int
    exit_idx: int
    exit_reason: str  # "target", "stop", "timeout"
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    duration_bars: int = 0


@dataclass
class BacktestConfig:
    target_pct: float = 0.9
    stop_pct: float = 0.55
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    alloc_usd: float = 30.0
    timeout_bars: int = 12  # barras antes de forzar cierre
    min_score: int = 60  # umbral minimo de score para entrar
    cooldown_bars: int = 3  # barras minimas entre trades del mismo activo


@dataclass
class BacktestReport:
    symbol: str = ""
    interval: str = ""
    config: dict = field(default_factory=dict)
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    timeouts: int = 0
    win_rate: float = 0.0
    expectancy_usd: float = 0.0
    profit_factor: float = 0.0
    total_pnl_usd: float = 0.0
    max_drawdown_usd: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    avg_duration_bars: float = 0.0
    best_trade_usd: float = 0.0
    worst_trade_usd: float = 0.0
    trades_per_day: float = 0.0


def load_candles(symbol: str, interval: str) -> list[dict]:
    """Carga velas OHLCV desde CSV historico."""
    p = HIST / f"{symbol}_{interval}.csv"
    if not p.exists():
        raise FileNotFoundError(f"No existe historico: {p}")
    candles = []
    with p.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                candles.append({
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0)),
                })
            except (ValueError, KeyError):
                continue
    return candles


def simulate_trades(candles: list[dict], cfg: BacktestConfig) -> list[TradeResult]:
    """
    Simula trades sobre velas historicas.
    Estrategia simplificada: entra en cada barra si no hay posicion activa
    y aplica target/stop/timeout.
    """
    trades = []
    n = len(candles)
    i = 0
    last_exit = -cfg.cooldown_bars  # permitir trade desde el inicio

    while i < n:
        if i - last_exit < cfg.cooldown_bars:
            i += 1
            continue

        entry_price = candles[i]["close"] * (1 + cfg.slippage_bps / 10000.0)
        if entry_price <= 0:
            i += 1
            continue

        target_price = entry_price * (1 + cfg.target_pct / 100.0)
        stop_price = entry_price * (1 - cfg.stop_pct / 100.0)
        qty = cfg.alloc_usd / entry_price
        fee_open = cfg.alloc_usd * cfg.fee_bps / 10000.0

        exit_price = None
        exit_reason = None
        exit_idx = i

        # Recorrer barras hasta target, stop, o timeout
        for j in range(i + 1, min(i + cfg.timeout_bars + 1, n)):
            bar = candles[j]

            # Comprobar stop primero (peor caso)
            if bar["low"] <= stop_price:
                exit_price = stop_price * (1 - cfg.slippage_bps / 10000.0)
                exit_reason = "stop"
                exit_idx = j
                break

            # Comprobar target
            if bar["high"] >= target_price:
                exit_price = target_price * (1 - cfg.slippage_bps / 10000.0)
                exit_reason = "target"
                exit_idx = j
                break

        # Timeout: cerrar al close de la ultima barra permitida
        if exit_price is None:
            timeout_idx = min(i + cfg.timeout_bars, n - 1)
            exit_price = candles[timeout_idx]["close"] * (1 - cfg.slippage_bps / 10000.0)
            exit_reason = "timeout"
            exit_idx = timeout_idx

        fee_close = abs(exit_price * qty) * cfg.fee_bps / 10000.0
        gross_pnl = (exit_price - entry_price) * qty
        net_pnl = gross_pnl - fee_open - fee_close
        pnl_pct = (net_pnl / cfg.alloc_usd) * 100.0

        trades.append(TradeResult(
            entry_price=round(entry_price, 8),
            exit_price=round(exit_price, 8),
            entry_idx=i,
            exit_idx=exit_idx,
            exit_reason=exit_reason,
            pnl_pct=round(pnl_pct, 4),
            pnl_usd=round(net_pnl, 6),
            duration_bars=exit_idx - i,
        ))

        last_exit = exit_idx
        i = exit_idx + 1

    return trades


def compute_metrics(trades: list[TradeResult], cfg: BacktestConfig, total_bars: int) -> BacktestReport:
    """Calcula metricas agregadas de un set de trades."""
    report = BacktestReport()
    report.config = asdict(cfg)
    report.total_trades = len(trades)

    if not trades:
        return report

    pnls = [t.pnl_usd for t in trades]
    report.wins = sum(1 for p in pnls if p > 0)
    report.losses = sum(1 for p in pnls if p <= 0)
    report.timeouts = sum(1 for t in trades if t.exit_reason == "timeout")
    report.win_rate = round(report.wins / len(trades) * 100, 2) if trades else 0
    report.expectancy_usd = round(mean(pnls), 6) if pnls else 0
    report.total_pnl_usd = round(sum(pnls), 4)
    report.best_trade_usd = round(max(pnls), 6)
    report.worst_trade_usd = round(min(pnls), 6)
    report.avg_duration_bars = round(mean([t.duration_bars for t in trades]), 1)

    # Profit factor
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    report.profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else 999.0

    # Max drawdown
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
    report.max_drawdown_usd = round(max_dd, 4)
    report.max_drawdown_pct = round((max_dd / cfg.alloc_usd) * 100, 2) if cfg.alloc_usd > 0 else 0

    # Sharpe ratio (anualizado, asumiendo barras son intervalos uniformes)
    if len(pnls) >= 2 and stdev(pnls) > 0:
        # Simplificacion: Sharpe = mean / stdev * sqrt(trades_per_year)
        # Estimamos trades/dia y anualizamos
        bars_per_day = max(1, total_bars / max(1, total_bars // 96))  # ~96 barras/dia en 15m
        trades_per_day = len(trades) / max(1, total_bars / bars_per_day)
        report.trades_per_day = round(trades_per_day, 2)
        trades_per_year = trades_per_day * 365
        report.sharpe_ratio = round((mean(pnls) / stdev(pnls)) * math.sqrt(trades_per_year), 4)
    else:
        report.sharpe_ratio = 0.0

    return report


def run_parameter_sweep(candles: list[dict], base_cfg: BacktestConfig) -> list[dict]:
    """Ejecuta un sweep de parametros target/stop para encontrar la combinacion optima."""
    results = []
    target_range = [0.5, 0.7, 0.9, 1.1, 1.3, 1.5]
    stop_range = [0.3, 0.4, 0.55, 0.7, 0.85]

    for target in target_range:
        for stop in stop_range:
            cfg = BacktestConfig(
                target_pct=target,
                stop_pct=stop,
                fee_bps=base_cfg.fee_bps,
                slippage_bps=base_cfg.slippage_bps,
                alloc_usd=base_cfg.alloc_usd,
                timeout_bars=base_cfg.timeout_bars,
                cooldown_bars=base_cfg.cooldown_bars,
            )
            trades = simulate_trades(candles, cfg)
            report = compute_metrics(trades, cfg, len(candles))
            results.append({
                "target_pct": target,
                "stop_pct": stop,
                "total_trades": report.total_trades,
                "win_rate": report.win_rate,
                "expectancy_usd": report.expectancy_usd,
                "profit_factor": report.profit_factor,
                "total_pnl_usd": report.total_pnl_usd,
                "max_drawdown_usd": report.max_drawdown_usd,
                "sharpe_ratio": report.sharpe_ratio,
            })

    # Ordenar por expectancy * profit_factor (score compuesto)
    for r in results:
        r["composite_score"] = round(r["expectancy_usd"] * max(0, r["profit_factor"] - 1), 6)
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Backtest engine para crypto scalping")
    parser.add_argument("--symbol", default="BTCUSDT", help="Simbolo a evaluar")
    parser.add_argument("--interval", default="15m", help="Intervalo de velas")
    parser.add_argument("--target-pct", type=float, default=0.9, help="Target en %%")
    parser.add_argument("--stop-pct", type=float, default=0.55, help="Stop en %%")
    parser.add_argument("--fee-bps", type=float, default=10.0, help="Fee en basis points")
    parser.add_argument("--slippage-bps", type=float, default=5.0, help="Slippage en basis points")
    parser.add_argument("--alloc-usd", type=float, default=30.0, help="Notional por trade en USD")
    parser.add_argument("--timeout-bars", type=int, default=12, help="Timeout en barras")
    parser.add_argument("--cooldown-bars", type=int, default=3, help="Cooldown entre trades")
    parser.add_argument("--sweep", action="store_true", help="Ejecutar sweep de parametros target/stop")
    args = parser.parse_args()

    cfg = BacktestConfig(
        target_pct=args.target_pct,
        stop_pct=args.stop_pct,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        alloc_usd=args.alloc_usd,
        timeout_bars=args.timeout_bars,
        cooldown_bars=args.cooldown_bars,
    )

    try:
        candles = load_candles(args.symbol, args.interval)
    except FileNotFoundError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    if len(candles) < 100:
        print(json.dumps({"ok": False, "error": f"Insuficientes velas: {len(candles)}"}, ensure_ascii=False))
        return

    print(f"Cargadas {len(candles)} velas para {args.symbol} ({args.interval})")

    if args.sweep:
        print("Ejecutando sweep de parametros target/stop...")
        results = run_parameter_sweep(candles, cfg)
        REPORTS.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS / f"backtest_sweep_{args.symbol}_{args.interval}.json"
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

        # Reporte markdown
        md_lines = [
            f"# Backtest Sweep: {args.symbol} ({args.interval})",
            "",
            f"- Velas: {len(candles)}",
            f"- Fee: {cfg.fee_bps} bps | Slippage: {cfg.slippage_bps} bps | Alloc: ${cfg.alloc_usd}",
            f"- Fecha: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Top 10 combinaciones",
            "",
            "| Target% | Stop% | Trades | WR% | Expectancy | PF | PnL | MaxDD | Sharpe |",
            "|--------:|------:|-------:|----:|-----------:|---:|----:|------:|-------:|",
        ]
        for r in results[:10]:
            md_lines.append(
                f"| {r['target_pct']:.1f} | {r['stop_pct']:.2f} | {r['total_trades']} | "
                f"{r['win_rate']:.1f} | ${r['expectancy_usd']:.4f} | {r['profit_factor']:.2f} | "
                f"${r['total_pnl_usd']:.2f} | ${r['max_drawdown_usd']:.2f} | {r['sharpe_ratio']:.2f} |"
            )
        md_path = REPORTS / f"backtest_sweep_{args.symbol}_{args.interval}.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"\nSweep guardado en: {out_path}")
        print(f"Reporte MD: {md_path}")
        print(json.dumps({"ok": True, "best": results[0] if results else None}, ensure_ascii=False))
    else:
        trades = simulate_trades(candles, cfg)
        report = compute_metrics(trades, cfg, len(candles))
        report.symbol = args.symbol
        report.interval = args.interval

        # Guardar reporte JSON
        REPORTS.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS / f"backtest_{args.symbol}_{args.interval}.json"
        out_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")

        # Resumen en consola
        print(f"\n{'='*50}")
        print(f"BACKTEST: {args.symbol} ({args.interval})")
        print(f"{'='*50}")
        print(f"Total trades:     {report.total_trades}")
        print(f"Win rate:         {report.win_rate}%")
        print(f"Expectancy:       ${report.expectancy_usd}")
        print(f"Profit factor:    {report.profit_factor}")
        print(f"Total PnL:        ${report.total_pnl_usd}")
        print(f"Max drawdown:     ${report.max_drawdown_usd} ({report.max_drawdown_pct}%)")
        print(f"Sharpe ratio:     {report.sharpe_ratio}")
        print(f"Avg duration:     {report.avg_duration_bars} barras")
        print(f"Timeouts:         {report.timeouts} ({round(report.timeouts/max(1,report.total_trades)*100,1)}%)")
        print(f"Best trade:       ${report.best_trade_usd}")
        print(f"Worst trade:      ${report.worst_trade_usd}")
        print(f"Trades/dia:       {report.trades_per_day}")
        print(f"\nReporte: {out_path}")
        print(json.dumps({"ok": True, "report": str(out_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
