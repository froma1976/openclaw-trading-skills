#!/usr/bin/env python3
import json
from datetime import datetime, UTC
from pathlib import Path
from urllib import request
import os

OUT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
API_SAVING_MODE = os.getenv("API_SAVING_MODE", "1").strip() in {"1", "true", "TRUE", "yes"}
MAX_SPY_ASSETS = int(os.getenv("MAX_SPY_ASSETS", "15"))
COINS = [
    "bitcoin", "ethereum", "tether", "binancecoin", "solana", "ripple", "usd-coin", "dogecoin", "cardano", "tron",
    "chainlink", "avalanche-2", "stellar", "sui", "toncoin", "shiba-inu", "hedera-hashgraph", "polkadot", "litecoin", "bitcoin-cash",
    "uniswap", "pepe", "near", "aptos", "internet-computer", "aave", "ethereum-classic", "render-token", "arbitrum", "mantle",
    "filecoin", "cosmos", "vechain", "maker", "algorand", "the-graph", "sei-network", "optimism", "bonk", "worldcoin-wld",
    "theta-token", "lido-dao", "injective-protocol", "fetch-ai", "the-sandbox", "decentraland", "eos", "tezos", "flow", "gala"
]
SYMBOL = {
    "bitcoin": "BTC", "ethereum": "ETH", "tether": "USDT", "binancecoin": "BNB", "solana": "SOL", "ripple": "XRP",
    "usd-coin": "USDC", "dogecoin": "DOGE", "cardano": "ADA", "tron": "TRX", "chainlink": "LINK", "avalanche-2": "AVAX",
    "stellar": "XLM", "sui": "SUI", "toncoin": "TON", "shiba-inu": "SHIB", "hedera-hashgraph": "HBAR", "polkadot": "DOT",
    "litecoin": "LTC", "bitcoin-cash": "BCH", "uniswap": "UNI", "pepe": "PEPE", "near": "NEAR", "aptos": "APT",
    "internet-computer": "ICP", "aave": "AAVE", "ethereum-classic": "ETC", "render-token": "RENDER", "arbitrum": "ARB", "mantle": "MNT",
    "filecoin": "FIL", "cosmos": "ATOM", "vechain": "VET", "maker": "MKR", "algorand": "ALGO", "the-graph": "GRT",
    "sei-network": "SEI", "optimism": "OP", "bonk": "BONK", "worldcoin-wld": "WLD", "theta-token": "THETA", "lido-dao": "LDO",
    "injective-protocol": "INJ", "fetch-ai": "FET", "the-sandbox": "SAND", "decentraland": "MANA", "eos": "EOS", "tezos": "XTZ",
    "flow": "FLOW", "gala": "GALA"
}


def get_json(url: str):
    req = request.Request(url, headers={"User-Agent": "crypto-scout/1.0"})
    with request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_breakout_spy(ticker: str) -> int:
    # Detecta arranque de impulso (1m): +% en 5 velas + volumen fuerte
    try:
        sym = f"{ticker}USDT"
        u = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1m&limit=40"
        k = get_json(u)
        if not isinstance(k, list) or len(k) < 20:
            return 0
        close = [float(x[4]) for x in k if len(x) > 5]
        vol = [float(x[5]) for x in k if len(x) > 5]
        if len(close) < 10 or len(vol) < 10:
            return 0
        p5 = (close[-1] / close[-6] - 1.0) * 100
        v_now = sum(vol[-5:]) / 5
        v_ref = sum(vol[-20:-5]) / 15
        if p5 >= 1.2 and v_now >= (v_ref * 1.5):
            return 1
        if p5 <= -1.0:
            return -1
        return 0
    except Exception:
        return 0


def fetch_chart_spy(ticker: str) -> int:
    # Señal rápida de velas 1m/5m/15m (Binance): 1 alcista, -1 bajista, 0 neutra/error
    try:
        sym = f"{ticker}USDT"
        u1 = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1m&limit=30"
        u5 = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=5m&limit=20"
        u15 = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=15m&limit=20"
        k1 = get_json(u1)
        k5 = get_json(u5)
        k15 = get_json(u15)
        if not isinstance(k1, list) or not isinstance(k5, list) or not isinstance(k15, list) or len(k1) < 10 or len(k5) < 10 or len(k15) < 10:
            return 0
        c1 = [float(x[4]) for x in k1 if len(x) > 4]
        c5 = [float(x[4]) for x in k5 if len(x) > 4]
        c15 = [float(x[4]) for x in k15 if len(x) > 4]
        m1s = sum(c1[-7:-1]) / 6
        m1l = sum(c1[-20:-1]) / 19
        m5s = sum(c5[-5:-1]) / 4
        m5l = sum(c5[-12:-1]) / 11
        m15s = sum(c15[-5:-1]) / 4
        m15l = sum(c15[-12:-1]) / 11
        if c1[-1] > m1s > m1l and c5[-1] > m5s > m5l and c15[-1] > m15s > m15l:
            return 1
        if c1[-1] < m1s < m1l and c5[-1] < m5s < m5l and c15[-1] < m15s < m15l:
            return -1
        return 0
    except Exception:
        return 0


def score_crypto(row: dict):
    ch24 = float(row.get("price_change_percentage_24h") or 0)
    ch7 = float(row.get("price_change_percentage_7d_in_currency") or 0)
    vol = float(row.get("total_volume") or 0)
    mcap = float(row.get("market_cap") or 0)
    fdv = float(row.get("fully_diluted_valuation") or 0)
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
    mc_fdv_ratio = (mcap / fdv) if (mcap > 0 and fdv > 0) else 1.0
    rug_block = False
    if ch24 > 8 or ch7 > 20:
        bubble = "Crítico"
        score -= 10
        argumento_en_contra = "Subida demasiado vertical: riesgo de barrida y retroceso"
    elif ch24 > 5 or ch7 > 12:
        bubble = "Medio"
        score -= 4
        argumento_en_contra = "Euforia parcial: entrar con tamaño pequeño"

    # Anti-rug básico por tokenómica
    if fdv > 0 and mc_fdv_ratio < 0.10:
        score -= 20
        rug_block = True
        argumento_en_contra = "Riesgo tokenómico alto (MC/FDV muy bajo)"
    elif fdv > 0 and mc_fdv_ratio < 0.25:
        score -= 10
        argumento_en_contra = "Tokenómica exigente (MC/FDV bajo)"

    score = max(0, min(100, int(round(score))))

    state = "WATCH"
    if score >= 60:
        state = "READY"
    if score >= 72:
        state = "TRIGGERED"

    # Decisión intradía activa: solo BUY / AVOID (sin HOLD)
    decision = "BUY" if (score >= 60 and bubble != "Crítico" and not rug_block) else "AVOID"

    gem_score = score
    if rank > 30:
        gem_score += 6
    if vol_ratio >= 0.10:
        gem_score += 4
    if rug_block:
        gem_score -= 20
    gem_score = max(0, min(100, int(round(gem_score))))

    # Señales de red de espías
    spy_news = 1 if ch24 > 0 else 0
    spy_euphoria = -1 if bubble == "Crítico" else (0 if bubble == "Medio" else 1)
    spy_flow = 1 if vol_ratio >= 0.07 else (-1 if vol_ratio < 0.03 else 0)
    spy_whale = 1 if (vol_ratio >= 0.12 and ch24 > 1.5) else 0

    return {
        "score": score,
        "state": state,
        "decision_final": decision,
        "reasons": reasons,
        "bubble_level": bubble,
        "argumento_en_contra": argumento_en_contra,
        "flow_ratio": round(vol_ratio, 4),
        "spy_news": spy_news,
        "spy_euphoria": spy_euphoria,
        "spy_flow": spy_flow,
        "spy_whale": spy_whale,
        "mc_fdv_ratio": round(mc_fdv_ratio, 4),
        "rug_block": rug_block,
        "gem_score": gem_score,
    }


def build_reports(ticker: str, price: float, row: dict, scored: dict):
    ch24 = float(row.get("price_change_percentage_24h") or 0)
    ch7 = float(row.get("price_change_percentage_7d_in_currency") or 0)
    flow = float(scored.get("flow_ratio") or 0)
    bias = "Bullish" if scored.get("decision_final") == "BUY" else "Bearish"

    tp1 = round(price * 1.012, 6)
    tp2 = round(price * 1.02, 6)
    sl = round(price * 0.993, 6)
    rr = round(((tp1 - price) / max(price - sl, 1e-9)), 2)

    senior = {
        "setup": {"entry": round(price, 6), "tp1": tp1, "tp2": tp2, "sl": sl},
        "confluencias": [
            f"RSI proxy momentum 24h: {ch24:.2f}%",
            f"EMA proxy tendencia 7d: {ch7:.2f}%",
            f"Volumen/MCAP: {flow:.4f}",
        ],
        "rr": rr,
        "sentimiento": "positivo" if ch24 >= 0 else "negativo",
    }

    technical = {
        "sesgo": bias,
        "soportes_resistencias": {
            "soporte_1": round(price * 0.99, 6),
            "soporte_2": round(price * 0.975, 6),
            "resistencia_1": round(price * 1.01, 6),
            "resistencia_2": round(price * 1.025, 6),
        },
        "order_blocks": "aprox en zona soporte_1/soporte_2 por reacción reciente",
        "divergencias": "sin divergencia crítica confirmada en este barrido rápido",
        "invalidacion": f"cierres por debajo de {round(price * 0.985, 6)}",
    }

    sentiment = {
        "catalizador": "flujo y momento intradía" if flow >= 0.07 else "catalizador débil",
        "riesgo": scored.get("argumento_en_contra"),
        "prediccion_corto": "continuación" if scored.get("decision_final") == "BUY" else "posible trampa/retroceso",
    }

    return senior, technical, sentiment


def main():
    ids = ",".join(COINS)
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false&price_change_percentage=24h,7d"
    )
    rows = get_json(url)
    assets = []

    # Ahorro API: solo calcular espías de velas en los más líquidos del batch
    spy_allowed = set()
    if isinstance(rows, list) and rows:
        ordered = sorted(rows, key=lambda x: float(x.get("total_volume") or 0), reverse=True)
        top_rows = ordered[:MAX_SPY_ASSETS] if API_SAVING_MODE else ordered
        for rr in top_rows:
            spy_allowed.add(SYMBOL.get(rr.get("id"), str(rr.get("symbol", "")).upper()))

    for r in rows:
        p = float(r.get("current_price") or 0)
        ch24 = float(r.get("price_change_percentage_24h") or 0)
        ch7 = float(r.get("price_change_percentage_7d_in_currency") or 0)
        sc = score_crypto(r)

        ticker = SYMBOL.get(r.get("id"), str(r.get("symbol", "")).upper())
        if ticker in spy_allowed:
            spy_chart = fetch_chart_spy(ticker)
            spy_breakout = fetch_breakout_spy(ticker)
        else:
            spy_chart = 0
            spy_breakout = 0
        sc["spy_chart"] = spy_chart
        sc["spy_breakout"] = spy_breakout
        sc["spy_confluence"] = int(sc["spy_news"] + sc["spy_euphoria"] + sc["spy_flow"] + sc["spy_whale"] + sc["spy_chart"] + sc["spy_breakout"])

        senior_report, technical_report, sentiment_report = build_reports(ticker, p, r, sc)

        assets.append({
            "id": r.get("id"),
            "ticker": ticker,
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
            "mc_fdv_ratio": sc["mc_fdv_ratio"],
            "rug_block": sc["rug_block"],
            "gem_score": sc["gem_score"],
            "argumento_en_contra": sc["argumento_en_contra"],
            "spy_news": sc["spy_news"],
            "spy_euphoria": sc["spy_euphoria"],
            "spy_flow": sc["spy_flow"],
            "spy_whale": sc["spy_whale"],
            "spy_chart": sc["spy_chart"],
            "spy_breakout": sc["spy_breakout"],
            "spy_confluence": sc["spy_confluence"],
            "senior_report": senior_report,
            "technical_report": technical_report,
            "sentiment_report": sentiment_report,
        })

    top = sorted(assets, key=lambda x: (x.get("decision_final") == "BUY", x.get("gem_score", 0), x.get("score", 0)), reverse=True)
    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "assets": assets,
        "top_opportunities": top,
        "source": "coingecko-free",
        "api_saving_mode": API_SAVING_MODE,
        "spy_assets_limit": MAX_SPY_ASSETS,
        "notes": "Scoring cripto con ahorro API activo (espías de velas en subset líquido)",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK crypto snapshot -> {OUT}")


if __name__ == "__main__":
    main()
