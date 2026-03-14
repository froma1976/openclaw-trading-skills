#!/usr/bin/env python3
import json
from datetime import UTC, datetime
from pathlib import Path

from runtime_utils import atomic_write_json


BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
LONG_SNAPSHOT = BASE / "data" / "crypto_snapshot_free.json"
OUT = BASE / "data" / "crypto_snapshot_short.json"
STABLES = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE"}
EXCLUDED = {"PEPE"}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def short_reports(asset: dict):
    price = float(asset.get("price_usd") or 0)
    if price <= 0:
        return {"setup": {"entry": 0, "tp1": 0, "tp2": 0, "sl": 0}, "rr": 0.0, "sentimiento": "neutro"}
    tp1 = round(price * 0.99, 8)
    tp2 = round(price * 0.982, 8)
    sl = round(price * 1.0065, 8)
    return {
        "setup": {"entry": price, "tp1": tp1, "tp2": tp2, "sl": sl},
        "confluencias": [
            f"Momentum 24h: {float(asset.get('chg_24h_pct') or 0):.2f}%",
            f"Momentum 7d: {float(asset.get('chg_7d_pct') or 0):.2f}%",
            f"Espias bearish netos: {int(asset.get('spy_chart') or 0) + int(asset.get('spy_breakout') or 0)}",
        ],
        "rr": round((price - tp1) / max(sl - price, 1e-9), 2),
        "sentimiento": "bajista",
    }


def score_short(asset: dict):
    ticker = str(asset.get("ticker") or "").upper()
    if not ticker or ticker in STABLES or ticker in EXCLUDED or bool(asset.get("rug_block")):
        return None

    ch24 = float(asset.get("chg_24h_pct") or 0)
    ch7 = float(asset.get("chg_7d_pct") or 0)
    chart = int(asset.get("spy_chart") or 0)
    breakout = int(asset.get("spy_breakout") or 0)
    confluence = int(asset.get("spy_confluence") or 0)
    euphoria = int(asset.get("spy_euphoria") or 0)
    whale = int(asset.get("spy_whale") or 0)
    bubble = str(asset.get("bubble_level") or "Bajo")
    research_sentiment = str(asset.get("research_sentiment") or "unknown").lower()
    research_catalyst = int(asset.get("research_catalyst_score") or 0)

    score = 50.0
    reasons = []
    if ch24 <= -5:
        score += 18
        reasons.append("momento_24h_bajista_fuerte")
    elif ch24 <= -2:
        score += 10
        reasons.append("momento_24h_bajista")
    if ch7 <= -7:
        score += 10
        reasons.append("tendencia_7d_debil")
    elif ch7 <= -3:
        score += 5
        reasons.append("sesgo_7d_bajista")
    if chart < 0:
        score += 12
        reasons.append("chart_spy_bearish")
    if breakout < 0:
        score += 14
        reasons.append("breakdown_activo")
    if confluence >= 2 and (chart < 0 or breakout < 0):
        score += min(8, confluence * 2)
        reasons.append("confluencia_bajista")
    if bubble in {"Medio", "Crítico"} and ch24 < 0:
        score += 6
        reasons.append("pinchazo_post_euforia")
    if euphoria > 0 and ch24 < 0:
        score += 6
        reasons.append("euforia_fallida")
    if whale < 0:
        score += 4
        reasons.append("whale_pressure")
    if research_sentiment in {"negative", "mixed"} and research_catalyst <= 0:
        score += 5
        reasons.append("research_no_apoya_rebote")
    if research_sentiment == "positive" and research_catalyst >= 2:
        score -= 12
        reasons.append("research_catalyst_contrario")
    if ch24 > 0:
        score -= 18
    if asset.get("decision_final") == "BUY" and float(asset.get("score_final") or 0) >= 75 and max(chart, breakout) >= 0:
        score -= 10

    short_score = round(clamp(score), 2)
    if short_score >= 82:
        state = "TRIGGERED" if breakout < 0 else "READY"
        decision = "SELL_SHORT"
    elif short_score >= 72:
        state = "READY"
        decision = "SELL_SHORT"
    elif short_score >= 60:
        state = "WATCH"
        decision = "WATCH_SHORT"
    else:
        state = "WATCH"
        decision = "AVOID"

    return {
        **asset,
        "score_short": short_score,
        "state_short": state,
        "decision_short": decision,
        "reasons_short": reasons[:6],
        "senior_report_short": short_reports(asset),
        "side": "SHORT",
    }


def main():
    long_snapshot = load_json(LONG_SNAPSHOT, {"assets": []})
    assets = []
    for asset in long_snapshot.get("assets", []) or []:
        row = score_short(asset)
        if row:
            assets.append(row)
    top = sorted(assets, key=lambda item: (item.get("decision_short") == "SELL_SHORT", item.get("score_short", 0)), reverse=True)
    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": "derived-from-crypto-long-snapshot",
        "notes": "Motor short separado sobre el mismo mercado base, enfocado en breakdowns y debilidad.",
        "assets": assets,
        "top_opportunities": top,
    }
    atomic_write_json(OUT, out)
    print(json.dumps({"ok": True, "assets": len(assets), "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
