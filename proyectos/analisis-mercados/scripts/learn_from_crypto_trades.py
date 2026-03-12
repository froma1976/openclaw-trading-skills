#!/usr/bin/env python3
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ORD = ROOT / "data" / "crypto_orders_sim.json"
OUT = ROOT / "data" / "trade_edge_model.json"
REP = ROOT / "reports" / "trade_edge_model.md"
STABLECOIN_TICKERS = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE"}
EXCLUDED_TICKERS = {"PEPE"}


def parse_iso(ts: str):
    return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))


def bucket_confidence(v):
    x = int(v or 0)
    if x >= 80:
        return "80+"
    if x >= 70:
        return "70-79"
    if x >= 60:
        return "60-69"
    return "<60"


def stats(rows):
    pnl = [float(r.get("pnl_usd") or 0) for r in rows]
    count = len(pnl)
    wins = sum(1 for p in pnl if p > 0)
    expectancy = (sum(pnl) / count) if count else 0.0
    return {
        "count": count,
        "wins": wins,
        "win_rate": round((wins / count * 100.0), 2) if count else 0.0,
        "expectancy_usd": round(expectancy, 4),
        "pnl_usd": round(sum(pnl), 4),
    }


def score_block(m):
    count = m.get("count", 0)
    expectancy = m.get("expectancy_usd", 0.0)
    win_rate = m.get("win_rate", 0.0)
    if count < 5:
        return 0
    return int(round(max(-10, min(12, expectancy * 40 + (win_rate - 50) * 0.18))))


def main():
    data = {"completed": []}
    if ORD.exists():
        data = json.loads(ORD.read_text(encoding="utf-8"))
    rows = data.get("completed", []) or []
    now = datetime.now(UTC)
    d14 = now - timedelta(days=14)
    recent = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker in STABLECOIN_TICKERS or ticker in EXCLUDED_TICKERS:
            continue
        try:
            if parse_iso(row.get("closed_at")) >= d14:
                recent.append(row)
        except Exception:
            continue

    by_ticker = {}
    by_conf = {}
    by_confluence = {}
    by_research = {}
    for row in recent:
        ticker = str(row.get("ticker") or "?").upper()
        by_ticker.setdefault(ticker, []).append(row)
        by_conf.setdefault(bucket_confidence(row.get("confidence") or row.get("score")), []).append(row)
        by_confluence.setdefault(str(int(row.get("spy_confluence") or 0)), []).append(row)
        by_research.setdefault(str(row.get("research_sentiment") or "unknown"), []).append(row)

    ticker_stats = {k: stats(v) for k, v in by_ticker.items()}
    conf_stats = {k: stats(v) for k, v in by_conf.items()}
    confluence_stats = {k: stats(v) for k, v in by_confluence.items()}
    research_stats = {k: stats(v) for k, v in by_research.items()}

    out = {
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "window": "14d",
        "trades_used": len(recent),
        "ticker_edge": {k: {**m, "edge_score": score_block(m)} for k, m in ticker_stats.items()},
        "confidence_edge": {k: {**m, "edge_score": score_block(m)} for k, m in conf_stats.items()},
        "confluence_edge": {k: {**m, "edge_score": score_block(m)} for k, m in confluence_stats.items()},
        "research_edge": {k: {**m, "edge_score": score_block(m)} for k, m in research_stats.items()},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Trade edge model",
        "",
        f"- Generated at: {out['generated_at']}",
        f"- Trades used: {out['trades_used']}",
        "",
        "## Ticker edge",
    ]
    for k, m in sorted(out["ticker_edge"].items(), key=lambda kv: (-kv[1]["edge_score"], -kv[1]["count"], kv[0]))[:15]:
        lines.append(f"- {k}: edge {m['edge_score']} | count {m['count']} | wr {m['win_rate']}% | exp {m['expectancy_usd']}")
    REP.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "trades_used": len(recent), "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
