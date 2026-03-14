#!/usr/bin/env python3
import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from runtime_utils import atomic_write_json, atomic_write_text

ROOT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ORD = ROOT / "data" / "crypto_orders_sim.json"
TRADES = ROOT / "data" / "trades_clean.csv"
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


def bootstrap_ci(pnls: list, n_boot: int = 1000, ci: float = 0.95) -> dict:
    """
    Bootstrap confidence interval para expectancy.
    Retorna: {"mean", "ci_low", "ci_high", "significant"} 
    significant = True si el intervalo no cruza 0.
    """
    import random
    if len(pnls) < 5:
        return {"mean": 0, "ci_low": 0, "ci_high": 0, "significant": False, "n": len(pnls)}
    
    means = []
    for _ in range(n_boot):
        sample = random.choices(pnls, k=len(pnls))
        means.append(sum(sample) / len(sample))
    means.sort()
    
    alpha = (1 - ci) / 2
    low_idx = int(alpha * n_boot)
    high_idx = int((1 - alpha) * n_boot) - 1
    
    mean_val = sum(pnls) / len(pnls)
    ci_low = means[max(0, low_idx)]
    ci_high = means[min(len(means) - 1, high_idx)]
    significant = (ci_low > 0) or (ci_high < 0)  # intervalo no cruza 0
    
    return {
        "mean": round(mean_val, 6),
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "significant": significant,
        "n": len(pnls),
    }


def hour_bucket(value) -> str:
    text = str(value or "").strip()
    if len(text) == 1:
        text = f"0{text}"
    if len(text) != 2 or not text.isdigit():
        return "unknown"
    return text


def setup_bucket(value) -> str:
    text = str(value or "base").strip().lower()
    return text or "base"


def main():
    now = datetime.now(UTC)
    d14 = now - timedelta(days=14)
    recent = []
    if TRADES.exists():
        with TRADES.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                ticker = str(row.get("symbol") or row.get("ticker") or "").upper()
                if ticker in STABLECOIN_TICKERS or ticker in EXCLUDED_TICKERS:
                    continue
                try:
                    if parse_iso(row.get("timestamp_exit") or row.get("closed_at") or "") >= d14:
                        row["ticker"] = ticker
                        recent.append(row)
                except Exception:
                    continue
    elif ORD.exists():
        data = json.loads(ORD.read_text(encoding="utf-8"))
        for row in data.get("completed", []) or []:
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
    by_hour = {}
    by_setup = {}
    for row in recent:
        ticker = str(row.get("ticker") or "?").upper()
        by_ticker.setdefault(ticker, []).append(row)
        by_conf.setdefault(bucket_confidence(row.get("confidence") or row.get("score")), []).append(row)
        by_confluence.setdefault(str(int(row.get("spy_confluence") or 0)), []).append(row)
        by_research.setdefault(str(row.get("research_sentiment") or "unknown"), []).append(row)
        by_hour.setdefault(hour_bucket(row.get("opened_hour_utc")), []).append(row)
        by_setup.setdefault(setup_bucket(row.get("setup_tag")), []).append(row)

    ticker_stats = {k: stats(v) for k, v in by_ticker.items()}
    conf_stats = {k: stats(v) for k, v in by_conf.items()}
    confluence_stats = {k: stats(v) for k, v in by_confluence.items()}
    research_stats = {k: stats(v) for k, v in by_research.items()}
    hour_stats = {k: stats(v) for k, v in by_hour.items()}
    setup_stats = {k: stats(v) for k, v in by_setup.items()}

    # Bootstrap confidence intervals para cada dimension
    def enrich_with_bootstrap(bucket_data: dict, raw_rows: dict) -> dict:
        result = {}
        for k, m in bucket_data.items():
            pnls = [float(r.get("pnl_usd") or 0) for r in raw_rows.get(k, [])]
            ci = bootstrap_ci(pnls)
            result[k] = {**m, "edge_score": score_block(m), "bootstrap": ci}
        return result

    out = {
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "window": "14d",
        "trades_used": len(recent),
        "ticker_edge": enrich_with_bootstrap(ticker_stats, by_ticker),
        "confidence_edge": enrich_with_bootstrap(conf_stats, by_conf),
        "confluence_edge": enrich_with_bootstrap(confluence_stats, by_confluence),
        "research_edge": enrich_with_bootstrap(research_stats, by_research),
        "hour_edge": enrich_with_bootstrap(hour_stats, by_hour),
        "setup_edge": enrich_with_bootstrap(setup_stats, by_setup),
    }
    atomic_write_json(OUT, out)

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
    lines.extend(["", "## Setup edge"])
    for k, m in sorted(out["setup_edge"].items(), key=lambda kv: (-kv[1]["edge_score"], -kv[1]["count"], kv[0]))[:10]:
        lines.append(f"- {k}: edge {m['edge_score']} | count {m['count']} | wr {m['win_rate']}% | exp {m['expectancy_usd']}")
    lines.extend(["", "## Hour edge"])
    for k, m in sorted(out["hour_edge"].items(), key=lambda kv: (-kv[1]["edge_score"], -kv[1]["count"], kv[0]))[:10]:
        lines.append(f"- {k}: edge {m['edge_score']} | count {m['count']} | wr {m['win_rate']}% | exp {m['expectancy_usd']}")
    lines.extend([
        "",
        "- Fuente prioritaria: trades_clean.csv",
        "- Uso: research interno; no valida readiness para capital real por sí solo",
    ])
    atomic_write_text(REP, "\n".join(lines))
    print(json.dumps({"ok": True, "trades_used": len(recent), "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
