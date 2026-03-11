#!/usr/bin/env python3
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ORD = BASE / "data" / "crypto_orders_sim.json"
JSON_OUT = BASE / "reports" / "edge_breakdown.json"
MD_OUT = BASE / "reports" / "edge_breakdown.md"
STABLECOIN_TICKERS = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE"}


def parse_iso(ts: str):
    return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))


def bucket_hour(dt: datetime) -> str:
    h = dt.hour
    if h < 8:
        return "00-07"
    if h < 16:
        return "08-15"
    return "16-23"


def touch_bucket(container: dict, key: str):
    container.setdefault(key, {"count": 0, "wins": 0, "losses": 0, "pnl_usd": 0.0})
    return container[key]


def apply_stats(stats: dict, pnl: float):
    stats["count"] += 1
    stats["pnl_usd"] += pnl
    if pnl > 0:
        stats["wins"] += 1
    elif pnl < 0:
        stats["losses"] += 1


def finalize(container: dict):
    rows = []
    for key, value in container.items():
        count = value["count"] or 0
        win_rate = (value["wins"] / count * 100.0) if count else 0.0
        expectancy = (value["pnl_usd"] / count) if count else 0.0
        rows.append({
            "key": key,
            "count": count,
            "wins": value["wins"],
            "losses": value["losses"],
            "win_rate": round(win_rate, 2),
            "expectancy_usd": round(expectancy, 4),
            "pnl_usd": round(value["pnl_usd"], 4),
        })
    return sorted(rows, key=lambda x: (-x["count"], -x["pnl_usd"], x["key"]))


def main():
    data = {"completed": []}
    if ORD.exists():
        data = json.loads(ORD.read_text(encoding="utf-8"))
    rows = data.get("completed", []) or []
    now = datetime.now(UTC)
    d7 = now - timedelta(days=7)

    by_ticker = {}
    by_result = {}
    by_hour = {}
    by_risk_mode = {}

    used = 0
    for order in rows:
        try:
            closed_at = parse_iso(order.get("closed_at"))
        except Exception:
            continue
        if closed_at < d7:
            continue
        pnl = float(order.get("pnl_usd") or 0)
        ticker = str(order.get("ticker") or "?").upper()
        if ticker in STABLECOIN_TICKERS:
            continue
        result = str(order.get("result") or "unknown").lower()
        risk_mode = str(order.get("risk_mode") or order.get("mode") or "unknown").lower()
        hour_key = bucket_hour(closed_at)

        apply_stats(touch_bucket(by_ticker, ticker), pnl)
        apply_stats(touch_bucket(by_result, result), pnl)
        apply_stats(touch_bucket(by_hour, hour_key), pnl)
        apply_stats(touch_bucket(by_risk_mode, risk_mode), pnl)
        used += 1

    report = {
        "as_of": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "window": "7d",
        "orders_used": used,
        "by_ticker": finalize(by_ticker),
        "by_result": finalize(by_result),
        "by_hour_bucket_utc": finalize(by_hour),
        "by_risk_mode": finalize(by_risk_mode),
    }
    JSON_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Edge breakdown (7d)",
        "",
        f"- As of: {report['as_of']}",
        f"- Orders used: {used}",
        "",
        "## By ticker",
        "| Key | Count | Win rate | Expectancy USD | PnL USD |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in report["by_ticker"][:15]:
        lines.append(f"| {row['key']} | {row['count']} | {row['win_rate']:.2f}% | {row['expectancy_usd']:.4f} | {row['pnl_usd']:.4f} |")

    lines += ["", "## By hour bucket UTC", "| Key | Count | Win rate | Expectancy USD | PnL USD |", "|---|---:|---:|---:|---:|"]
    for row in report["by_hour_bucket_utc"]:
        lines.append(f"| {row['key']} | {row['count']} | {row['win_rate']:.2f}% | {row['expectancy_usd']:.4f} | {row['pnl_usd']:.4f} |")

    lines += ["", "## By risk mode", "| Key | Count | Win rate | Expectancy USD | PnL USD |", "|---|---:|---:|---:|---:|"]
    for row in report["by_risk_mode"]:
        lines.append(f"| {row['key']} | {row['count']} | {row['win_rate']:.2f}% | {row['expectancy_usd']:.4f} | {row['pnl_usd']:.4f} |")

    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
