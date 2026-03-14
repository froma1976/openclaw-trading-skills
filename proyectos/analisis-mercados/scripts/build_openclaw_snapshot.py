#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

from runtime_utils import atomic_write_json, atomic_write_text


BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
SIGNALS = BASE / "data" / "latest_snapshot_free.json"
CRYPTO = BASE / "data" / "crypto_snapshot_free.json"
LEARNING = BASE / "data" / "learning_status.json"
MOONSHOT = BASE / "data" / "moonshot_candidates.json"
ORDERS = BASE / "data" / "crypto_orders_sim.json"
OUT = BASE / "data" / "openclaw_system_snapshot.json"
REPORT = BASE / "reports" / "openclaw_system_snapshot.md"
HISTORY_DIR = BASE / "data" / "snapshots" / "openclaw"


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def freshness_minutes(iso_value):
    if not iso_value:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
        return int((datetime.now(UTC) - dt).total_seconds() // 60)
    except Exception:
        return None


def archive_snapshot(snapshot: dict) -> str:
    ts = datetime.now(UTC)
    day_dir = HISTORY_DIR / ts.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    rel = f"snapshots/openclaw/{ts.strftime('%Y-%m-%d')}/{ts.strftime('%H%M%S')}.json"
    atomic_write_json(BASE / "data" / rel, snapshot)
    return rel.replace("\\", "/")


def recent_history(limit: int = 12) -> list[dict]:
    if not HISTORY_DIR.exists():
        return []
    files = sorted(HISTORY_DIR.glob("**/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    for path in files[:limit]:
        data = load_json(path, {})
        if not isinstance(data, dict):
            continue
        summary = data.get("summary") or {}
        rows.append({
            "generated_at": data.get("generated_at"),
            "risk_mode": summary.get("risk_mode"),
            "equity_usd": summary.get("equity_usd"),
            "moonshot_top_count": summary.get("moonshot_top_count"),
            "prime_count": (((data.get("domains") or {}).get("moonshot") or {}).get("summary") or {}).get("prime_count"),
            "path": str(path.relative_to(BASE / "data")).replace("\\", "/"),
        })
    return list(reversed(rows))


def compare_narratives(previous: dict, current: dict) -> list[dict]:
    prev_rows = ((((previous.get("domains") or {}).get("moonshot") or {}).get("leaderboards") or {}).get("by_narrative") or [])
    cur_rows = ((((current.get("domains") or {}).get("moonshot") or {}).get("leaderboards") or {}).get("by_narrative") or [])
    prev_map = {str(row.get("label")): row for row in prev_rows}
    alerts = []
    for row in cur_rows:
        label = str(row.get("label") or "")
        prev = prev_map.get(label, {})
        diff = round(float(row.get("avg_score") or 0) - float(prev.get("avg_score") or 0), 2)
        count_diff = int(row.get("count") or 0) - int(prev.get("count") or 0)
        direction = None
        if diff >= 6:
            direction = "UP"
        elif diff <= -6:
            direction = "DOWN"
        elif prev and count_diff >= 2:
            direction = "BROADENING"
        if direction:
            alerts.append({
                "label": label,
                "direction": direction,
                "avg_score_diff": diff,
                "count_diff": count_diff,
                "current_avg_score": row.get("avg_score"),
                "top_ticker": row.get("top_ticker"),
            })
    alerts.sort(key=lambda item: (abs(float(item.get("avg_score_diff") or 0)), abs(int(item.get("count_diff") or 0))), reverse=True)
    return alerts[:10]


def risk_label(learning: dict, portfolio: dict) -> tuple[str, str]:
    pf = float(learning.get("profit_factor") or 0)
    expectancy = float(learning.get("expectancy_usd") or 0)
    semaforo = str(learning.get("semaforo") or "ROJO")
    realized = float(portfolio.get("realized_pnl_usd") or 0)
    if semaforo == "ROJO" or pf < 1 or expectancy <= 0 or realized < 0:
        return "DEFENSIVE", "scalper sin edge confirmado; proteger capital"
    if pf >= 1.4 and expectancy > 0:
        return "OFFENSIVE", "edge operativo suficiente para ampliar vigilancia"
    return "SELECTIVE", "solo setups de calidad alta; nada de sobreoperar"


def build_summary(signals: dict, crypto: dict, moonshot: dict, learning: dict, orders: dict) -> dict:
    stock_top = ((signals or {}).get("top_opportunities") or [])[:5]
    crypto_top = ((crypto or {}).get("top_opportunities") or [])[:5]
    moonshot_top = ((moonshot or {}).get("combined_top") or [])[:8]
    portfolio = (orders or {}).get("portfolio") or {}
    active = (orders or {}).get("active") or []
    completed = (orders or {}).get("completed") or []
    mode, reason = risk_label(learning, portfolio)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "version": 1,
        "mission": "compound intelligence for scalp + moonshot discovery",
        "summary": {
            "stock_top_count": len(stock_top),
            "crypto_top_count": len(crypto_top),
            "moonshot_top_count": len(moonshot_top),
            "active_crypto_positions": len(active),
            "completed_crypto_positions": len(completed),
            "equity_usd": round(float(portfolio.get("equity_usd") or 0), 2),
            "cash_usd": round(float(portfolio.get("cash_usd") or 0), 2),
            "risk_mode": mode,
            "risk_reason": reason,
        },
        "freshness": {
            "stocks_min": freshness_minutes((signals or {}).get("generated_at")),
            "crypto_min": freshness_minutes((crypto or {}).get("generated_at")),
            "moonshot_min": freshness_minutes((moonshot or {}).get("generated_at")),
        },
        "domains": {
            "stocks": {
                "top": stock_top,
            },
            "crypto_scalp": {
                "top": crypto_top,
                "learning": learning,
                "portfolio": portfolio,
            },
            "moonshot": {
                "summary": (moonshot or {}).get("summary") or {},
                "top": moonshot_top,
                "leaderboards": (moonshot or {}).get("leaderboards") or {},
            },
        },
    }


def build_markdown(snapshot: dict) -> str:
    lines = [
        "# OpenClaw System Snapshot",
        "",
        f"- Generated at: {snapshot.get('generated_at')}",
        f"- Mission: {snapshot.get('mission')}",
        f"- Risk mode: {snapshot.get('summary', {}).get('risk_mode')} ({snapshot.get('summary', {}).get('risk_reason')})",
        f"- Equity: {snapshot.get('summary', {}).get('equity_usd')} USD | Cash: {snapshot.get('summary', {}).get('cash_usd')} USD",
        "",
        "## Moonshot top",
    ]
    for row in ((snapshot.get("domains") or {}).get("moonshot") or {}).get("top", [])[:8]:
        lines.append(f"- {row.get('ticker')} [{row.get('asset_class')}] | {row.get('state')} | score {row.get('moonshot_score')} | narratives {', '.join(row.get('narrative_tags') or [])}")
    lines.extend(["", "## Moonshot leaderboard by narrative"])
    for row in ((((snapshot.get("domains") or {}).get("moonshot") or {}).get("leaderboards") or {}).get("by_narrative") or [])[:8]:
        lines.append(f"- {row.get('label')}: avg {row.get('avg_score')} | count {row.get('count')} | top {row.get('top_ticker')}")
    lines.extend(["", "## Narrative alerts"])
    for row in (snapshot.get("alerts") or {}).get("narrative_shifts", [])[:8]:
        lines.append(f"- {row.get('label')}: {row.get('direction')} | diff {row.get('avg_score_diff')} | count diff {row.get('count_diff')} | top {row.get('top_ticker')}")
    if not (snapshot.get("alerts") or {}).get("narrative_shifts"):
        lines.append("- Sin cambios fuertes todavía")
    lines.extend(["", "## Scalp learning"])
    learning = ((snapshot.get("domains") or {}).get("crypto_scalp") or {}).get("learning") or {}
    lines.append(f"- Semaforo: {learning.get('semaforo')} | trades_7d {learning.get('trades_7d')} | PF {learning.get('profit_factor')} | expectancy {learning.get('expectancy_usd')}")
    return "\n".join(lines)


def main():
    signals = load_json(SIGNALS, {})
    crypto = load_json(CRYPTO, {})
    moonshot = load_json(MOONSHOT, {})
    learning = load_json(LEARNING, {})
    orders = load_json(ORDERS, {})
    snapshot = build_summary(signals, crypto, moonshot, learning, orders)
    previous = load_json(OUT, {})
    snapshot["alerts"] = {
        "narrative_shifts": compare_narratives(previous, snapshot),
    }
    archive_rel = archive_snapshot(snapshot)
    snapshot["archive_path"] = archive_rel
    snapshot["history"] = recent_history(limit=10)
    atomic_write_json(OUT, snapshot)
    atomic_write_text(REPORT, build_markdown(snapshot))
    print(json.dumps({"ok": True, "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
