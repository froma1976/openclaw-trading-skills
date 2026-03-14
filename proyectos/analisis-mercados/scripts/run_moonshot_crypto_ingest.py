#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

import source_ingest_crypto_free as crypto_ingest
from runtime_utils import atomic_write_json, file_lock


BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
CFG = BASE / "config" / "moonshot_sources.json"
OUT = BASE / "data" / "crypto_snapshot_moonshot.json"
LOCK = BASE / "data" / "locks" / "crypto_runtime.lock"


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def unique(items):
    out = []
    seen = set()
    for item in items:
        key = str(item or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def main():
    cfg = load_json(CFG, {"crypto": {}})
    coin_ids = unique((cfg.get("crypto") or {}).get("coin_ids") or [])
    if not coin_ids:
        print(json.dumps({"ok": False, "error": "no crypto universe configured"}, ensure_ascii=False))
        return

    try:
        with file_lock(LOCK, stale_seconds=900, wait_seconds=20):
            universe = crypto_ingest.load_universe_status()
            research_map = crypto_ingest.load_core_research()
            edge_model = crypto_ingest.load_trade_edge_model()
            dynamic_excluded = universe.get("excluded") or set()

            ids = ",".join(coin_ids)
            url = (
                "https://api.coingecko.com/api/v3/coins/markets"
                f"?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false&price_change_percentage=24h,7d"
            )
            rows = crypto_ingest.get_json(url)
            source_label = "coingecko-moonshot"
            notes = "Moonshot crypto universe focused on alt/beta candidates"
            if not isinstance(rows, list):
                rows = []

            b24h = crypto_ingest.get_binance_24h_stats_bulk()
            ordered = sorted(rows, key=lambda x: float(x.get("total_volume") or 0), reverse=True)
            top_rows = ordered[: max(10, min(20, len(ordered)))] if crypto_ingest.API_SAVING_MODE else ordered
            spy_allowed = {crypto_ingest.SYMBOL.get(rr.get("id"), str(rr.get("symbol", "")).upper()) for rr in top_rows}

            assets = []
            for row in rows:
                ticker = crypto_ingest.SYMBOL.get(row.get("id"), str(row.get("symbol", "")).upper())
                p = float(row.get("current_price") or 0)
                ch24 = float(row.get("price_change_percentage_24h") or 0)
                b_data = b24h.get(f"{ticker}USDT")
                if b_data:
                    if p <= 0:
                        p = float(b_data.get("lastPrice") or 0)
                        row["current_price"] = p
                    if ch24 == 0:
                        ch24 = float(b_data.get("priceChangePercent") or 0)
                        row["price_change_percentage_24h"] = ch24
                if p <= 0:
                    p = crypto_ingest.get_binance_price(ticker)
                    row["current_price"] = p
                ch7 = float(row.get("price_change_percentage_7d_in_currency") or 0)

                scored = crypto_ingest.score_crypto(row)
                scored = crypto_ingest.apply_research_overlay(ticker, scored, research_map or {})
                if ticker in crypto_ingest.STABLECOIN_TICKERS or ticker in crypto_ingest.EXCLUDED_TICKERS:
                    spy_chart = 0
                    spy_breakout = 0
                elif ticker in spy_allowed:
                    spy_chart = crypto_ingest.fetch_chart_spy(ticker)
                    spy_breakout = crypto_ingest.fetch_breakout_spy(ticker)
                else:
                    spy_chart = 0
                    spy_breakout = 0
                scored["spy_chart"] = spy_chart
                scored["spy_breakout"] = spy_breakout
                scored["spy_confluence"] = int(scored["spy_news"] + scored["spy_euphoria"] + scored["spy_flow"] + scored["spy_whale"] + scored["spy_chart"] + scored["spy_breakout"])
                scored = crypto_ingest.apply_trade_edge_overlay(ticker, scored, edge_model)
                senior_report, technical_report, sentiment_report = crypto_ingest.build_reports(ticker, p, row, scored)

                assets.append({
                    "id": row.get("id"),
                    "ticker": ticker,
                    "name": row.get("name"),
                    "price_usd": p,
                    "chg_24h_pct": round(ch24, 2),
                    "chg_7d_pct": round(ch7, 2),
                    "market_cap_rank": row.get("market_cap_rank"),
                    "total_volume": row.get("total_volume"),
                    "score": scored["score"],
                    "score_final": scored.get("score_final", scored["score"]),
                    "confidence_pct": scored.get("confidence_pct", scored["score"]),
                    "state": scored["state"],
                    "decision_final": scored["decision_final"],
                    "reasons": scored["reasons"],
                    "bubble_level": scored["bubble_level"],
                    "flow_ratio": scored["flow_ratio"],
                    "mc_fdv_ratio": scored["mc_fdv_ratio"],
                    "rug_block": scored["rug_block"],
                    "gem_score": scored["gem_score"],
                    "argumento_en_contra": scored["argumento_en_contra"],
                    "spy_news": scored["spy_news"],
                    "spy_euphoria": scored["spy_euphoria"],
                    "spy_flow": scored["spy_flow"],
                    "spy_whale": scored["spy_whale"],
                    "spy_chart": scored["spy_chart"],
                    "spy_breakout": scored["spy_breakout"],
                    "spy_confluence": scored["spy_confluence"],
                    "research_sentiment": scored.get("research_sentiment"),
                    "research_catalyst_score": scored.get("research_catalyst_score", 0),
                    "research_score_delta": scored.get("research_score_delta", 0),
                    "trade_edge_score": scored.get("trade_edge_score", 0),
                    "trade_edge_delta": scored.get("trade_edge_delta", 0),
                    "trade_edge_hour": scored.get("trade_edge_hour"),
                    "trade_edge_hour_score": scored.get("trade_edge_hour_score", 0),
                    "setup_tag": scored.get("setup_tag", "base"),
                    "setup_edge_score": scored.get("setup_edge_score", 0),
                    "trade_edge_maturity": scored.get("trade_edge_maturity", 0),
                    "senior_report": senior_report,
                    "technical_report": technical_report,
                    "sentiment_report": sentiment_report,
                })

            top = [a for a in sorted(assets, key=lambda x: (x.get("decision_final") == "BUY", x.get("gem_score", 0), x.get("score_final", x.get("score", 0))), reverse=True) if a.get("ticker") not in crypto_ingest.STABLECOIN_TICKERS and a.get("ticker") not in crypto_ingest.EXCLUDED_TICKERS and a.get("ticker") not in dynamic_excluded]
            out = {
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "engine": "moonshot-crypto-ingest",
                "assets": assets,
                "top_opportunities": top,
                "source": source_label,
                "notes": notes,
                "universe_ids": coin_ids,
                "universe_excluded": sorted(dynamic_excluded),
            }
            atomic_write_json(OUT, out)
            print(json.dumps({"ok": True, "coins": len(coin_ids), "out": str(OUT)}, ensure_ascii=False))
    except RuntimeError:
        fallback = load_json(OUT, {"assets": []})
        print(json.dumps({"ok": True, "coins": len(coin_ids), "out": str(OUT), "fallback": bool(fallback.get("assets")), "note": "lock busy, using existing moonshot crypto snapshot"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
