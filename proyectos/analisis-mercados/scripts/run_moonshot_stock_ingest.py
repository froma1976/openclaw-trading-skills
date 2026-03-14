#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

import source_ingest_free as stock_ingest
from runtime_utils import atomic_write_json


BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
CFG = BASE / "config" / "moonshot_sources.json"
OUT = BASE / "data" / "latest_snapshot_moonshot.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def unique(seq):
    out = []
    seen = set()
    for item in seq:
        key = str(item or "").upper().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def main():
    stock_ingest.load_env_fallback()
    cfg = load_json(CFG, {"market": {}, "social": {}, "finviz": {}})
    tickers = unique((cfg.get("market") or {}).get("tickers") or [])
    social_symbols = unique((cfg.get("social") or {}).get("symbols") or tickers[:12])
    finviz_symbols = unique((cfg.get("finviz") or {}).get("symbols") or tickers[:12])

    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "engine": "moonshot-stock-ingest",
        "macro": [],
        "market": [],
        "news": [],
        "social": [],
        "earnings": [],
        "options": [],
        "finviz_news": [],
        "insider_map": {},
        "universe": tickers,
    }

    for s in ["M2SL", "DGS10", "DGS2", "DTWEXBGS", "VIXCLS"]:
        try:
            out["macro"].append(stock_ingest.fetch_fred_series(s))
        except Exception as exc:
            out["macro"].append({"series": s, "error": str(exc)})

    for ticker in tickers:
        try:
            out["market"].append(stock_ingest.fetch_yahoo_ticker(ticker))
        except Exception as exc:
            out["market"].append({"ticker": ticker, "ok": False, "error": str(exc), "score": 0})

    for symbol in social_symbols:
        try:
            out["social"].append(stock_ingest.fetch_stocktwits_symbol(symbol))
        except Exception as exc:
            out["social"].append({"symbol": symbol, "error": str(exc)})

    for ticker in tickers:
        try:
            earnings = stock_ingest.fetch_earnings_finnhub(ticker) or stock_ingest.fetch_earnings_fmp(ticker)
            if earnings:
                out["earnings"].append(earnings)
        except Exception:
            pass
        try:
            out["options"].append(stock_ingest.fetch_yahoo_options_signal(ticker))
        except Exception:
            pass

    for ticker in finviz_symbols:
        try:
            out["finviz_news"].append(stock_ingest.fetch_finviz_headlines(ticker, limit=4))
        except Exception as exc:
            out["finviz_news"].append({"ticker": ticker, "error": str(exc), "items": []})

    try:
        insider_rows = stock_ingest.fetch_openinsider_latest(limit=180)
        out["insider_map"] = stock_ingest.build_openinsider_map(insider_rows)
    except Exception:
        out["insider_map"] = {}

    stock_ingest.apply_final_score(out)
    ranked = [m for m in out.get("market", []) if isinstance(m, dict) and m.get("ok")]
    ranked.sort(key=lambda x: x.get("score_final", x.get("score", 0)), reverse=True)
    out["top_opportunities"] = ranked[:15]

    atomic_write_json(OUT, out)
    print(json.dumps({"ok": True, "tickers": len(tickers), "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
