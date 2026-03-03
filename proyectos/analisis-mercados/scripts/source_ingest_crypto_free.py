#!/usr/bin/env python3
import json
from datetime import datetime, UTC
from pathlib import Path
from urllib import request

OUT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
COINS = ["bitcoin", "ethereum", "solana"]
SYMBOL = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}


def get_json(url: str):
    req = request.Request(url, headers={"User-Agent": "crypto-scout/1.0"})
    with request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def score_crypto(row: dict):
    ch24 = float(row.get("price_change_percentage_24h") or 0)
    ch7 = float(row.get("price_change_percentage_7d_in_currency") or 0)
    vol = float(row.get("total_volume") or 0)
    mcap = float(row.get("market_cap") or 0)
    rank = int(row.get("market_cap_rank") or 999)

    score = 50
    reasons = []

    # Momento
    if ch24 >= 2:
        score += 10
        reasons.append("momento_24h_fuerte")
    elif ch24 >= 0:
        score += 4
        reasons.append("momento_24h_positivo")
    elif ch24 <= -3:
        score -= 12
        reasons.append("momento_24h_debil")

    if ch7 >= 6:
        score += 20
        reasons.append("tendencia_7d_fuerte")
    elif ch7 >= 2:
        score += 10
        reasons.append("tendencia_7d_positiva")
    elif ch7 <= -8:
        score -= 18
        reasons.append("tendencia_7d_debil")

    # Flujo aproximado (volumen / marketcap)
    vol_ratio = (vol / mcap) if mcap > 0 else 0
    if vol_ratio >= 0.12:
        score += 10
        reasons.append("flujo_fuerte")
    elif vol_ratio >= 0.07:
        score += 5
        reasons.append("flujo_ok")
    elif vol_ratio < 0.03:
        score -= 6
        reasons.append("flujo_debil")

    # Calidad base por tamaño (evitar basura)
    if rank <= 10:
        score += 5
        reasons.append("liquidez_alta")

    bubble = "Bajo"
    argumento_en_contra = "Sin objeción crítica detectada"
    if ch24 > 8 or ch7 > 20:
        bubble = "Crítico"
        score -= 10
        argumento_en_contra = "Subida demasiado vertical: riesgo de barrida y retroceso"
    elif ch24 > 5 or ch7 > 12:
        bubble = "Medio"
        score -= 4
        argumento_en_contra = "Euforia parcial: entrar con tamaño pequeño"

    score = max(0, min(100, int(round(score))))

    state = "WATCH"
    if score >= 66:
        state = "READY"
    if score >= 78:
        state = "TRIGGERED"

    # Decisión final conservadora
    decision = "AVOID"
    if score >= 80 and bubble != "Crítico":
        decision = "BUY"
    elif score >= 60:
        decision = "HOLD"

    return {
        "score": score,
        "state": state,
        "decision_final": decision,
        "reasons": reasons,
        "bubble_level": bubble,
        "argumento_en_contra": argumento_en_contra,
        "flow_ratio": round(vol_ratio, 4),
    }


def main():
    ids = ",".join(COINS)
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false&price_change_percentage=24h,7d"
    )
    rows = get_json(url)
    assets = []

    for r in rows:
        p = float(r.get("current_price") or 0)
        ch24 = float(r.get("price_change_percentage_24h") or 0)
        ch7 = float(r.get("price_change_percentage_7d_in_currency") or 0)
        sc = score_crypto(r)

        assets.append({
            "id": r.get("id"),
            "ticker": SYMBOL.get(r.get("id"), str(r.get("symbol", "")).upper()),
            "name": r.get("name"),
            "price_usd": p,
            "chg_24h_pct": round(ch24, 2),
            "chg_7d_pct": round(ch7, 2),
            "market_cap_rank": r.get("market_cap_rank"),
            "total_volume": r.get("total_volume"),
            "score": sc["score"],
            "score_final": sc["score"],
            "confidence_pct": sc["score"],
            "state": sc["state"],
            "decision_final": sc["decision_final"],
            "reasons": sc["reasons"],
            "bubble_level": sc["bubble_level"],
            "flow_ratio": sc["flow_ratio"],
            "argumento_en_contra": sc["argumento_en_contra"],
        })

    top = sorted(assets, key=lambda x: x["score"], reverse=True)
    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "assets": assets,
        "top_opportunities": top,
        "source": "coingecko-free",
        "notes": "Scoring cripto con momentum+flujo+risk bubble en modo conservador",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK crypto snapshot -> {OUT}")


if __name__ == "__main__":
    main()
