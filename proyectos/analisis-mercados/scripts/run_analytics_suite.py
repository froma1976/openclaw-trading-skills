#!/usr/bin/env python3
"""
Ejecuta la suite completa de analytics:
1. Regime detector (ADX/Hurst/ATR para BTC, ETH, SOL)
2. Risk metrics (Sharpe, Sortino, Calmar, Kelly)
3. Correlation monitor (entre posiciones activas)

Diseñado para ejecutarse como cron job cada 4 horas.
Uso: py -3 scripts/run_analytics_suite.py
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/scripts")


def run_script(name: str, args: list[str] | None = None) -> dict:
    cmd = [sys.executable, str(BASE / name)] + (args or [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(BASE))
        ok = result.returncode == 0
        return {"script": name, "ok": ok, "stdout": result.stdout[-500:] if result.stdout else "", "stderr": result.stderr[-300:] if result.stderr else ""}
    except subprocess.TimeoutExpired:
        return {"script": name, "ok": False, "error": "timeout"}
    except Exception as e:
        return {"script": name, "ok": False, "error": str(e)}


def main():
    results = []

    # 1. Regime detector
    r = run_script("regime_detector.py", ["--all"])
    results.append(r)

    # 2. Risk metrics
    r = run_script("risk_metrics.py")
    results.append(r)

    # 3. Correlation monitor
    r = run_script("correlation_monitor.py")
    results.append(r)

    # 4. Learn from trades (edge model update)
    r = run_script("learn_from_crypto_trades.py")
    results.append(r)

    all_ok = all(x["ok"] for x in results)
    summary = {"ok": all_ok, "results": results}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
