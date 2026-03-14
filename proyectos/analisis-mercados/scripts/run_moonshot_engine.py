#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

from runtime_utils import atomic_write_json, atomic_write_text


BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
CFG = BASE / "config" / "moonshot_strategy.json"
STOCK_SNAPSHOT = BASE / "data" / "latest_snapshot_free.json"
MOONSHOT_STOCK_SNAPSHOT = BASE / "data" / "latest_snapshot_moonshot.json"
CRYPTO_SNAPSHOT = BASE / "data" / "crypto_snapshot_free.json"
MOONSHOT_CRYPTO_SNAPSHOT = BASE / "data" / "crypto_snapshot_moonshot.json"
OUT_JSON = BASE / "data" / "moonshot_candidates.json"
OUT_MD = BASE / "reports" / "moonshot_candidates.md"

STOCK_NARRATIVES = {
    "AI": {"NVDA", "AMD", "PLTR", "SOUN", "BBAI", "PATH", "APP", "CRWD", "SNOW", "NET", "ARM", "SMCI", "TEM"},
    "SPACE": {"RKLB", "ASTS", "LUNR"},
    "CRYPTO_BETA": {"MSTR", "COIN", "MARA", "RIOT"},
    "FINTECH": {"HOOD", "SOFI", "UPST", "AFRM"},
    "EV": {"TSLA", "RIVN", "QS"},
    "HEALTH_GROWTH": {"HIMS", "TEM"},
    "NUCLEAR_ENERGY": {"OKLO"},
    "CYBER_CLOUD": {"NET", "CRWD", "PANW"},
}

CRYPTO_NARRATIVES = {
    "L1": {"SOL", "SUI", "ADA", "XRP", "XLM", "ATOM", "APT", "SEI", "FLOW", "NEAR", "TON", "ETC", "XTZ", "EOS", "ALGO"},
    "L2": {"OP", "ARB", "MNT"},
    "AI": {"FET", "RENDER", "WLD", "ICP"},
    "MEME": {"DOGE", "SHIB", "BONK", "PEPE", "GALA"},
    "DEFI": {"AAVE", "MKR", "UNI", "INJ", "LINK", "GRT"},
    "METAVERSE": {"SAND", "MANA", "THETA"},
    "INFRA": {"FIL", "ICP", "LINK", "GRT"},
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def moonshot_state(score: float, prime_score: int, early_score: int) -> str:
    if score >= prime_score:
        return "PRIME"
    if score >= early_score:
        return "EARLY"
    return "WATCH"


def top_reasons(reasons: list[str], extra: list[str]) -> list[str]:
    merged = []
    for item in list(extra) + list(reasons or []):
        text = str(item or "").strip()
        if text and text not in merged:
            merged.append(text)
    return merged[:6]


def infer_narratives(asset_class: str, ticker: str, why_now: list[str], drivers: dict) -> list[str]:
    ticker = str(ticker or "").upper()
    found = []
    mapping = STOCK_NARRATIVES if asset_class == "stock" else CRYPTO_NARRATIVES
    for label, symbols in mapping.items():
        if ticker in symbols:
            found.append(label)
    why_blob = " ".join(str(x or "") for x in (why_now or [])).lower()
    if asset_class == "stock":
        if float((drivers or {}).get("catalyst_score") or 0) > 0:
            found.append("CATALYST")
        if float((drivers or {}).get("insider_score") or 0) > 0:
            found.append("INSIDER")
        if float((drivers or {}).get("options_flow_score") or 0) > 0:
            found.append("OPTIONS_FLOW")
    else:
        if int((drivers or {}).get("spy_breakout") or 0) > 0:
            found.append("BREAKOUT")
        if float((drivers or {}).get("flow_ratio") or 0) >= 0.07:
            found.append("FLOW")
        if "research_catalyst_positive" in why_blob:
            found.append("CATALYST")
    ordered = []
    for item in found:
        if item not in ordered:
            ordered.append(item)
    return ordered or ["GENERAL"]


def build_leaderboards(candidates: list[dict]) -> dict:
    def aggregate(rows: list[dict], label_fn):
        groups = {}
        for row in rows:
            key = label_fn(row)
            if not key:
                continue
            slot = groups.setdefault(key, {"count": 0, "avg_score": 0.0, "top_ticker": None, "top_score": -1.0})
            slot["count"] += 1
            slot["avg_score"] += float(row.get("moonshot_score") or 0)
            score = float(row.get("moonshot_score") or 0)
            if score > slot["top_score"]:
                slot["top_score"] = score
                slot["top_ticker"] = row.get("ticker")
        out = []
        for key, value in groups.items():
            out.append({
                "label": key,
                "count": value["count"],
                "avg_score": round(value["avg_score"] / max(1, value["count"]), 2),
                "top_ticker": value["top_ticker"],
                "top_score": round(value["top_score"], 2),
            })
        out.sort(key=lambda item: (item["avg_score"], item["count"]), reverse=True)
        return out

    narrative_rows = []
    for row in candidates:
        for narrative in row.get("narrative_tags", []):
            narrative_rows.append({**row, "narrative": narrative})

    crypto_rows = [row for row in candidates if row.get("asset_class") == "crypto"]

    return {
        "by_asset_class": aggregate(candidates, lambda row: row.get("asset_class")),
        "by_state": aggregate(candidates, lambda row: row.get("state")),
        "by_narrative": aggregate(narrative_rows, lambda row: row.get("narrative")),
        "by_ticker": aggregate(candidates, lambda row: row.get("ticker")),
        "moonshot_crypto_setup": aggregate(crypto_rows, lambda row: ((row.get("drivers") or {}).get("setup_tag") or "base")),
        "moonshot_crypto_hour": aggregate(crypto_rows, lambda row: ((row.get("drivers") or {}).get("trade_edge_hour") or "unknown")),
    }


def build_stock_candidate(asset: dict, cfg: dict):
    if not isinstance(asset, dict) or not asset.get("ok"):
        return None
    weights = cfg.get("weights") or {}
    base_score = float(asset.get("score_final") or asset.get("score") or 0)
    if base_score < float(cfg.get("min_base_score", 55)):
        return None

    rel_volume = float(asset.get("rel_volume") or 0)
    breakout_20 = bool(asset.get("breakout_20"))
    options_score = float(asset.get("options_flow_score") or 0)
    insider_score = float(asset.get("insider_score") or 0)
    catalyst_score = float(asset.get("catalyst_score") or 0)
    spinoff_score = float(asset.get("spinoff_score") or 0)
    fundamental_score = float(asset.get("fundamental_inflection_score") or 0)
    asymmetry_score = float(asset.get("score_asymmetry") or 0)
    convergence = int(asset.get("convergence_count") or 0)
    chg_5d = float(asset.get("chg_5d_pct") or 0)
    chg_20d = float(asset.get("chg_20d_pct") or 0)
    intraday_bias = str(asset.get("intraday_15m_bias") or "").lower()
    bubble = str(asset.get("bubble_level") or "Bajo")
    decision = str(asset.get("decision_final") or "WATCH")

    score = base_score * float(weights.get("base_score", 0.45))
    score += min(float(weights.get("rel_volume_cap", 12)), max(0.0, (rel_volume - 1.0) * 10.0))
    if breakout_20:
        score += float(weights.get("breakout_bonus", 12))
    score += min(float(weights.get("options_bonus", 8)), options_score * 2.0)
    score += min(float(weights.get("insider_bonus", 10)), insider_score * 1.8)
    score += min(float(weights.get("catalyst_bonus", 10)), catalyst_score * 1.6)
    score += min(float(weights.get("spinoff_bonus", 7)), spinoff_score * 1.5)
    score += min(float(weights.get("fundamental_bonus", 9)), fundamental_score * 1.4)
    score += min(float(weights.get("asymmetry_bonus", 10)), asymmetry_score * 1.4)
    score += min(float(weights.get("convergence_bonus", 8)), convergence * 2.0)
    if chg_5d > 0 and chg_20d > 0:
        score += float(weights.get("momentum_bonus", 6))
    if intraday_bias == "alcista":
        score += float(weights.get("intraday_bonus", 3))
    if bubble == "Crítico":
        score -= float(weights.get("bubble_penalty", 14))
    elif bubble == "Medio":
        score -= float(weights.get("bubble_penalty", 14)) * 0.35
    if decision == "AVOID":
        score -= float(weights.get("avoid_penalty", 10))

    final = round(clamp(score), 2)
    state = moonshot_state(final, int(cfg.get("prime_score", 78)), int(cfg.get("early_score", 68)))
    thesis = []
    if breakout_20:
        thesis.append("breakout_20_confirmado")
    if rel_volume >= 1.5:
        thesis.append("volumen_relativo_fuerte")
    if catalyst_score > 0:
        thesis.append("catalizador_activo")
    if insider_score > 0:
        thesis.append("insiders_a_favor")
    if options_score > 0:
        thesis.append("flujo_opciones")
    if fundamental_score > 0:
        thesis.append("inflexion_fundamental")

    row = {
        "asset_class": "stock",
        "ticker": asset.get("ticker"),
        "name": asset.get("ticker"),
        "price": asset.get("regularMarketPrice"),
        "moonshot_score": final,
        "state": state,
        "decision_hint": "BUILD_POSITION" if state == "PRIME" else "WATCHLIST_BUILD" if state == "EARLY" else "WATCH_ONLY",
        "horizon": "weeks_to_months",
        "why_now": top_reasons(asset.get("reasons") or [], thesis),
        "risk": asset.get("argumento_en_contra"),
        "drivers": {
            "score_final": base_score,
            "rel_volume": rel_volume,
            "breakout_20": breakout_20,
            "catalyst_score": catalyst_score,
            "insider_score": insider_score,
            "options_flow_score": options_score,
            "fundamental_inflection_score": fundamental_score,
            "score_asymmetry": asymmetry_score,
            "convergence_count": convergence,
            "bubble_level": bubble,
        },
    }
    row["narrative_tags"] = infer_narratives("stock", str(row.get("ticker") or ""), row.get("why_now") or [], row.get("drivers") or {})
    return row


def build_crypto_candidate(asset: dict, cfg: dict):
    if not isinstance(asset, dict):
        return None
    ticker = str(asset.get("ticker") or "")
    if not ticker or ticker in {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE"}:
        return None
    weights = cfg.get("weights") or {}
    base_score = float(asset.get("score_final") or asset.get("score") or 0)
    gem_score = float(asset.get("gem_score") or 0)
    if max(base_score, gem_score) < float(cfg.get("min_base_score", 58)):
        return None

    flow_ratio = float(asset.get("flow_ratio") or 0)
    confluence = int(asset.get("spy_confluence") or 0)
    breakout = int(asset.get("spy_breakout") or 0)
    chart = int(asset.get("spy_chart") or 0)
    research_sentiment = str(asset.get("research_sentiment") or "unknown")
    research_catalyst_score = int(asset.get("research_catalyst_score") or 0)
    rank = int(asset.get("market_cap_rank") or 999)
    bubble = str(asset.get("bubble_level") or "Bajo")
    rug_block = bool(asset.get("rug_block"))
    decision = str(asset.get("decision_final") or "WATCH")
    chg_24h = float(asset.get("chg_24h_pct") or 0)
    chg_7d = float(asset.get("chg_7d_pct") or 0)
    setup_tag = str(asset.get("setup_tag") or "base")
    trade_edge_hour = str(asset.get("trade_edge_hour") or "unknown")

    score = base_score * float(weights.get("base_score", 0.4))
    score += gem_score * float(weights.get("gem_score", 0.25))
    score += min(float(weights.get("flow_cap", 12)), flow_ratio * 100.0)
    score += min(float(weights.get("confluence_bonus", 10)), confluence * 2.0)
    if breakout > 0:
        score += float(weights.get("breakout_bonus", 12))
    if chart > 0:
        score += float(weights.get("chart_bonus", 6))
    if research_sentiment == "positive" and research_catalyst_score > 0:
        score += min(float(weights.get("research_bonus", 7)), 2.0 + research_catalyst_score)
    if 15 <= rank <= 150:
        score += float(weights.get("rank_sweetspot_bonus", 8))
    elif rank > 250:
        score -= float(weights.get("microcap_penalty", 12))
    if chg_24h > 12 or chg_7d > 35:
        score -= float(weights.get("bubble_penalty", 12))
    elif bubble == "Crítico":
        score -= float(weights.get("bubble_penalty", 12))
    elif bubble == "Medio":
        score -= float(weights.get("bubble_penalty", 12)) * 0.35
    if rug_block:
        score -= float(weights.get("rug_penalty", 25))
    if decision == "AVOID":
        score -= float(weights.get("avoid_penalty", 10))

    final = round(clamp(score), 2)
    state = moonshot_state(final, int(cfg.get("prime_score", 80)), int(cfg.get("early_score", 70)))
    thesis = []
    if breakout > 0:
        thesis.append("breakout_activo")
    if confluence >= 3:
        thesis.append("confluencia_alta")
    if flow_ratio >= 0.07:
        thesis.append("flujo_relativo_fuerte")
    if research_sentiment == "positive" and research_catalyst_score > 0:
        thesis.append("research_catalyst_positive")
    if 15 <= rank <= 150:
        thesis.append("zona_capitalizacion_explosiva")

    row = {
        "asset_class": "crypto",
        "ticker": ticker,
        "name": asset.get("name") or ticker,
        "price": asset.get("price_usd"),
        "moonshot_score": final,
        "state": state,
        "decision_hint": "BUILD_POSITION" if state == "PRIME" else "WATCHLIST_BUILD" if state == "EARLY" else "WATCH_ONLY",
        "horizon": "days_to_weeks",
        "why_now": top_reasons(asset.get("reasons") or [], thesis),
        "risk": asset.get("argumento_en_contra"),
        "drivers": {
            "score_final": base_score,
            "gem_score": gem_score,
            "chg_24h_pct": chg_24h,
            "chg_7d_pct": chg_7d,
            "flow_ratio": flow_ratio,
            "spy_confluence": confluence,
            "spy_breakout": breakout,
            "spy_chart": chart,
            "research_sentiment": research_sentiment,
            "research_catalyst_score": research_catalyst_score,
            "market_cap_rank": rank,
            "bubble_level": bubble,
            "setup_tag": setup_tag,
            "trade_edge_hour": trade_edge_hour,
        },
    }
    row["narrative_tags"] = infer_narratives("crypto", str(row.get("ticker") or ""), row.get("why_now") or [], row.get("drivers") or {})
    return row


def build_markdown(payload: dict) -> str:
    lines = [
        "# Moonshot Engine",
        "",
        f"- Generated at: {payload.get('generated_at')}",
        f"- Stocks candidates: {len(payload.get('stocks', []))}",
        f"- Crypto candidates: {len(payload.get('crypto', []))}",
        "- Purpose: detectar activos antes de un movimiento explosivo, no scalping.",
        "",
        "## Top Combined",
    ]
    for row in payload.get("combined_top", []):
        lines.append(
            f"- [{row['asset_class']}] {row['ticker']} | score {row['moonshot_score']} | {row['state']} | {row['decision_hint']} | narratives {', '.join(row.get('narrative_tags') or [])} | {', '.join(row.get('why_now') or [])}"
        )
    lines.extend(["", "## Narrative leaderboard"])
    for row in (payload.get("leaderboards") or {}).get("by_narrative", [])[:10]:
        lines.append(f"- {row['label']}: avg {row['avg_score']} | count {row['count']} | top {row['top_ticker']} ({row['top_score']})")
    lines.extend(["", "## Stocks"])
    for row in payload.get("stocks", []):
        lines.append(
            f"- {row['ticker']} | score {row['moonshot_score']} | {row['state']} | rv {row['drivers'].get('rel_volume')} | catalysts {row['drivers'].get('catalyst_score')} | insiders {row['drivers'].get('insider_score')}"
        )
    lines.extend(["", "## Crypto"])
    for row in payload.get("crypto", []):
        lines.append(
            f"- {row['ticker']} | score {row['moonshot_score']} | {row['state']} | confluence {row['drivers'].get('spy_confluence')} | flow {row['drivers'].get('flow_ratio')} | rank {row['drivers'].get('market_cap_rank')}"
        )
    return "\n".join(lines)


def main():
    cfg = load_json(CFG, {"stocks": {}, "crypto": {}})
    stock_snapshot_primary = load_json(MOONSHOT_STOCK_SNAPSHOT, {"market": []})
    stock_snapshot_fallback = load_json(STOCK_SNAPSHOT, {"market": []})
    crypto_snapshot_primary = load_json(MOONSHOT_CRYPTO_SNAPSHOT, {"assets": []})
    crypto_snapshot_fallback = load_json(CRYPTO_SNAPSHOT, {"assets": []})

    merged_market = []
    seen_tickers = set()
    for snap in [stock_snapshot_primary, stock_snapshot_fallback]:
        for asset in snap.get("market", []) or []:
            ticker = str((asset or {}).get("ticker") or "").upper()
            if not ticker or ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)
            merged_market.append(asset)

    merged_crypto = []
    seen_crypto = set()
    for snap in [crypto_snapshot_primary, crypto_snapshot_fallback]:
        for asset in snap.get("assets", []) or []:
            ticker = str((asset or {}).get("ticker") or "").upper()
            if not ticker or ticker in seen_crypto:
                continue
            seen_crypto.add(ticker)
            merged_crypto.append(asset)

    stock_candidates = []
    for asset in merged_market:
        row = build_stock_candidate(asset, cfg.get("stocks") or {})
        if row:
            stock_candidates.append(row)

    crypto_candidates = []
    for asset in merged_crypto:
        row = build_crypto_candidate(asset, cfg.get("crypto") or {})
        if row:
            crypto_candidates.append(row)

    stock_candidates.sort(key=lambda item: item.get("moonshot_score", 0), reverse=True)
    crypto_candidates.sort(key=lambda item: item.get("moonshot_score", 0), reverse=True)

    stock_candidates = stock_candidates[: int((cfg.get("stocks") or {}).get("max_candidates", 12))]
    crypto_candidates = crypto_candidates[: int((cfg.get("crypto") or {}).get("max_candidates", 12))]

    combined = sorted(stock_candidates + crypto_candidates, key=lambda item: item.get("moonshot_score", 0), reverse=True)
    summary = {
        "total_candidates": len(combined),
        "prime_count": sum(1 for row in combined if row.get("state") == "PRIME"),
        "early_count": sum(1 for row in combined if row.get("state") == "EARLY"),
        "watch_count": sum(1 for row in combined if row.get("state") == "WATCH"),
        "top_stock": stock_candidates[0]["ticker"] if stock_candidates else None,
        "top_crypto": crypto_candidates[0]["ticker"] if crypto_candidates else None,
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "engine": "moonshot-v1",
        "mission": "find_the_move_before_the_move",
        "notes": [
            "Separate engine from scalping runtime.",
            "Uses a dedicated moonshot stock universe plus current crypto snapshot.",
            "Focuses on asymmetry, catalysts, breakout potential, and room to run.",
        ],
        "summary": summary,
        "stocks": stock_candidates,
        "crypto": crypto_candidates,
        "combined_top": combined[:15],
        "leaderboards": build_leaderboards(combined),
    }

    atomic_write_json(OUT_JSON, payload)
    atomic_write_text(OUT_MD, build_markdown(payload))
    print(json.dumps({
        "ok": True,
        "stocks": len(stock_candidates),
        "crypto": len(crypto_candidates),
        "out": str(OUT_JSON),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
