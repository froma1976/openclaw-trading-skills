#!/usr/bin/env python3
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from pathlib import Path
from urllib import request
import os

from runtime_utils import atomic_write_json, file_lock

OUT = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_snapshot_free.json")
UNIVERSE_STATUS = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/universe_status.json")
CORE_RESEARCH = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/core_market_research.json")
TRADE_EDGE_MODEL = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/trade_edge_model.json")
API_SAVING_MODE = os.getenv("API_SAVING_MODE", "1").strip() in {"1", "true", "TRUE", "yes"}
MAX_SPY_ASSETS = int(os.getenv("MAX_SPY_ASSETS", "15"))
STABLECOIN_IDS = {"tether", "usd-coin", "dai", "true-usd", "first-digital-usd", "binance-usd", "ethena-usde", "frax", "usdd", "pax-dollar"}
STABLECOIN_TICKERS = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE", "FRAX", "USDD", "USDP", "PYUSD", "GUSD", "CRVUSD"}
EXCLUDED_TICKERS = {"PEPE"}
RUNTIME_LOCK = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/locks/crypto_runtime.lock")
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
    try:
        req = request.Request(url, headers={"User-Agent": "crypto-scout/1.0"})
        with request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def get_json_with_retry(url: str, attempts: int = 3, sleep_seconds: float = 1.5):
    for idx in range(max(1, attempts)):
        data = get_json(url)
        if isinstance(data, list) and data:
            return data
        if idx < attempts - 1:
            time.sleep(sleep_seconds)
    return None


def get_binance_price(ticker: str) -> float:
    if not ticker:
        return 0.0
    try:
        # Binance Public API (No key required for ticker price)
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={ticker}USDT"
        data = get_json(url)
        if data and "price" in data:
            return float(data["price"])
    except Exception:
        pass
    return 0.0


def get_binance_24h_stats_bulk() -> dict:
    try:
        # Fetch all tickers 24h stats in one call (very efficient)
        url = "https://api.binance.com/api/v3/ticker/24hr"
        data = get_json(url)
        if isinstance(data, list):
            return {item["symbol"]: item for item in data if "symbol" in item}
    except Exception:
        pass
    return {}


def rebuild_rows_from_previous_assets(previous_assets: list[dict]) -> list[dict]:
    rows = []
    for asset in previous_assets or []:
        if not isinstance(asset, dict):
            continue
        ticker = str(asset.get("ticker") or "").upper()
        rows.append({
            "id": asset.get("id") or ticker.lower(),
            "symbol": ticker.lower(),
            "name": asset.get("name") or ticker,
            "current_price": asset.get("price_usd") or 0,
            "price_change_percentage_24h": asset.get("chg_24h_pct") or 0,
            "price_change_percentage_7d_in_currency": asset.get("chg_7d_pct") or 0,
            "market_cap_rank": asset.get("market_cap_rank") or 9999,
            "total_volume": asset.get("total_volume") or 0,
            "market_cap": asset.get("market_cap") or 0,
            "fully_diluted_valuation": asset.get("fully_diluted_valuation") or asset.get("market_cap") or 0,
        })
    return rows


def load_universe_status():
    if not UNIVERSE_STATUS.exists():
        return {"core": set(), "watch": set(), "excluded": set()}
    try:
        data = json.loads(UNIVERSE_STATUS.read_text(encoding="utf-8"))
        return {
            "core": {str(x).upper() for x in (data.get("core") or [])},
            "watch": {str(x).upper() for x in (data.get("watch") or [])},
            "excluded": {str(x).upper() for x in (data.get("excluded") or [])},
        }
    except Exception:
        return {"core": set(), "watch": set(), "excluded": set()}


def load_core_research():
    if not CORE_RESEARCH.exists():
        return {}
    try:
        data = json.loads(CORE_RESEARCH.read_text(encoding="utf-8"))
        out = {}
        for asset in (data.get("assets") or []):
            ticker = str(asset.get("ticker") or "").upper()
            if ticker:
                out[ticker] = asset
        return out
    except Exception:
        return {}


def load_trade_edge_model():
    if not TRADE_EDGE_MODEL.exists():
        return {"ticker_edge": {}, "confidence_edge": {}, "confluence_edge": {}, "research_edge": {}, "hour_edge": {}, "setup_edge": {}}
    try:
        data = json.loads(TRADE_EDGE_MODEL.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"ticker_edge": {}, "confidence_edge": {}, "confluence_edge": {}, "research_edge": {}, "hour_edge": {}, "setup_edge": {}}
    except Exception:
        return {"ticker_edge": {}, "confidence_edge": {}, "confluence_edge": {}, "research_edge": {}, "hour_edge": {}, "setup_edge": {}}


def infer_setup_tag(scored: dict) -> str:
    breakout = int(scored.get("spy_breakout") or 0)
    chart = int(scored.get("spy_chart") or 0)
    flow = int(scored.get("spy_flow") or 0)
    news = int(scored.get("spy_news") or 0)
    whale = int(scored.get("spy_whale") or 0)
    euphoria = int(scored.get("spy_euphoria") or 0)
    if breakout > 0 and chart > 0:
        return "breakout_trend"
    if breakout > 0:
        return "breakout"
    if chart > 0 and flow > 0:
        return "trend_flow"
    if whale > 0 and flow > 0:
        return "whale_flow"
    if news > 0 and euphoria <= 0:
        return "news_reversal"
    if flow > 0:
        return "flow_momentum"
    return "base"


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
    coin_id = str(row.get("id") or "")
    ticker = SYMBOL.get(coin_id, str(row.get("symbol", "")).upper())
    is_stablecoin = coin_id in STABLECOIN_IDS or ticker in STABLECOIN_TICKERS
    is_excluded = ticker in EXCLUDED_TICKERS
    ch24 = float(row.get("price_change_percentage_24h") or 0)
    ch7 = float(row.get("price_change_percentage_7d_in_currency") or 0)
    vol = float(row.get("total_volume") or 0)
    mcap = float(row.get("market_cap") or 0)
    fdv = float(row.get("fully_diluted_valuation") or 0)
    rank = int(row.get("market_cap_rank") or 999)

    score = 50
    reasons = []

    if is_stablecoin:
        return {
            "score": 0,
            "state": "INVALIDATED",
            "decision_final": "AVOID",
            "reasons": ["stablecoin_bloqueada"],
            "bubble_level": "Bajo",
            "argumento_en_contra": "Stablecoin excluida del universo operativo",
            "flow_ratio": 0.0,
            "spy_news": 0,
            "spy_euphoria": 0,
            "spy_flow": 0,
            "spy_whale": 0,
            "mc_fdv_ratio": 1.0,
            "rug_block": True,
            "gem_score": 0,
        }

    if is_excluded:
        return {
            "score": 0,
            "state": "INVALIDATED",
            "decision_final": "AVOID",
            "reasons": ["asset_excluido_runtime"],
            "bubble_level": "Bajo",
            "argumento_en_contra": "Activo excluido por distorsionar el edge defendible",
            "flow_ratio": 0.0,
            "spy_news": 0,
            "spy_euphoria": 0,
            "spy_flow": 0,
            "spy_whale": 0,
            "mc_fdv_ratio": 1.0,
            "rug_block": True,
            "gem_score": 0,
        }

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


def apply_research_overlay(ticker: str, scored: dict, research_map: dict):
    research = research_map.get(str(ticker).upper())
    if not research:
        scored["research_sentiment"] = "unknown"
        scored["research_catalyst_score"] = 0
        scored["research_score_delta"] = 0
        return scored

    signal = research.get("signal") or {}
    sentiment = str(signal.get("sentiment") or "mixed").lower()
    catalyst_score = int(signal.get("catalyst_score") or 0)
    delta = 0
    if sentiment == "positive" and catalyst_score >= 1:
        delta = min(6, 2 + catalyst_score)
    elif sentiment == "negative" and catalyst_score <= -1:
        delta = max(-10, -3 + catalyst_score)
    elif sentiment == "mixed" and catalyst_score <= -2:
        delta = -3

    scored["research_sentiment"] = sentiment
    scored["research_catalyst_score"] = catalyst_score
    scored["research_score_delta"] = delta
    score_final = max(0, min(100, int(round(scored.get("score", 0) + delta))))
    scored["score_final"] = score_final
    scored["confidence_pct"] = score_final
    if delta > 0:
        scored.setdefault("reasons", []).append("research_catalyst_positive")
    elif delta < 0:
        scored.setdefault("reasons", []).append("research_catalyst_negative")

    state = "WATCH"
    if score_final >= 60:
        state = "READY"
    if score_final >= 72:
        state = "TRIGGERED"
    scored["state"] = state
    scored["decision_final"] = "BUY" if (score_final >= 60 and scored.get("bubble_level") != "Crítico" and not scored.get("rug_block")) else "AVOID"
    return scored


def apply_trade_edge_overlay(ticker: str, scored: dict, edge_model: dict):
    ticker_edge = (((edge_model or {}).get("ticker_edge") or {}).get(str(ticker).upper()) or {}).get("edge_score", 0)
    conf_bucket = "80+" if int(scored.get("confidence_pct") or scored.get("score_final") or scored.get("score") or 0) >= 80 else ("70-79" if int(scored.get("confidence_pct") or scored.get("score_final") or scored.get("score") or 0) >= 70 else ("60-69" if int(scored.get("confidence_pct") or scored.get("score_final") or scored.get("score") or 0) >= 60 else "<60"))
    confidence_edge = (((edge_model or {}).get("confidence_edge") or {}).get(conf_bucket) or {}).get("edge_score", 0)
    confluence_edge = (((edge_model or {}).get("confluence_edge") or {}).get(str(int(scored.get("spy_confluence") or 0))) or {}).get("edge_score", 0)
    research_key = str(scored.get("research_sentiment") or "unknown")
    research_edge = (((edge_model or {}).get("research_edge") or {}).get(research_key) or {}).get("edge_score", 0)
    current_hour = datetime.now(UTC).strftime("%H")
    setup_tag = infer_setup_tag(scored)
    hour_edge = (((edge_model or {}).get("hour_edge") or {}).get(current_hour) or {}).get("edge_score", 0)
    setup_edge = (((edge_model or {}).get("setup_edge") or {}).get(setup_tag) or {}).get("edge_score", 0)
    trades_used = int((edge_model or {}).get("trades_used") or 0)
    maturity_scale = min(1.0, max(0.0, trades_used / 80.0))
    raw_delta = ticker_edge * 0.55 + confidence_edge * 0.25 + confluence_edge * 0.35 + research_edge * 0.2 + hour_edge * 0.3 + setup_edge * 0.45
    delta = int(round(raw_delta * maturity_scale))
    delta = max(-10, min(10, delta))

    scored["trade_edge_score"] = ticker_edge
    scored["trade_edge_hour"] = current_hour
    scored["trade_edge_hour_score"] = hour_edge
    scored["setup_tag"] = setup_tag
    scored["setup_edge_score"] = setup_edge
    scored["trade_edge_maturity"] = round(maturity_scale, 3)
    scored["trade_edge_delta"] = delta
    score_final = max(0, min(100, int(round(scored.get("score_final", scored.get("score", 0)) + delta))))
    scored["score_final"] = score_final
    scored["confidence_pct"] = score_final
    if delta > 0:
        scored.setdefault("reasons", []).append("trade_edge_positive")
    elif delta < 0:
        scored.setdefault("reasons", []).append("trade_edge_negative")
    state = "WATCH"
    if score_final >= 60:
        state = "READY"
    if score_final >= 72:
        state = "TRIGGERED"
    scored["state"] = state
    scored["decision_final"] = "BUY" if (score_final >= 60 and scored.get("bubble_level") != "Crítico" and not scored.get("rug_block")) else "AVOID"
    return scored


def apply_edge_guardrails(scored: dict):
    maturity = float(scored.get("trade_edge_maturity") or 0.0)
    if maturity < 0.6:
        return scored

    trade_edge_delta = int(scored.get("trade_edge_delta") or 0)
    setup_edge_score = int(scored.get("setup_edge_score") or 0)
    hour_edge_score = int(scored.get("trade_edge_hour_score") or 0)
    confluence = int(scored.get("spy_confluence") or 0)

    guardrail_reason = None
    if setup_edge_score <= -8:
        guardrail_reason = "setup_edge_guardrail"
    elif hour_edge_score <= -8:
        guardrail_reason = "hour_edge_guardrail"
    elif trade_edge_delta <= -4 and confluence < 4:
        guardrail_reason = "trade_edge_guardrail"

    if not guardrail_reason:
        return scored

    reasons = scored.setdefault("reasons", [])
    if guardrail_reason not in reasons:
        reasons.append(guardrail_reason)
    scored["state"] = "WATCH"
    scored["decision_final"] = "AVOID"
    return scored


def main():
    try:
        with file_lock(RUNTIME_LOCK, stale_seconds=900, wait_seconds=0):
            _main_locked()
    except RuntimeError:
        print("LOCK_BUSY crypto_runtime")


def _main_locked():
    universe = load_universe_status()
    research_map = load_core_research()
    edge_model = load_trade_edge_model()
    dynamic_excluded = universe.get("excluded") or set()
    ids = ",".join(COINS)
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false&price_change_percentage=24h,7d"
    )
    source_label = "coingecko-free"
    note_flags = ["Scoring cripto con ahorro API activo (espias de velas en subset liquido)"]
    rows = get_json_with_retry(url, attempts=3, sleep_seconds=1.5)
    if not isinstance(rows, list):
        previous = {"assets": []}
        if OUT.exists():
            try:
                previous = json.loads(OUT.read_text(encoding="utf-8"))
            except Exception:
                pass
        rebuilt_rows = rebuild_rows_from_previous_assets(previous.get("assets", []) or [])
        if rebuilt_rows:
            rows = rebuilt_rows
            source_label = "snapshot-recovered"
            note_flags = ["Coingecko fallo; snapshot reconstruido con ultimo universo y refresco Binance"]
        else:
            rows = previous.get("assets", []) or []
            source_label = "snapshot-cache"
            note_flags = ["Fallback a ultimo snapshot local por rate limit/error externo"]
    
    # Obtener stats de 24h de Binance para rellenar huecos
    b24h = get_binance_24h_stats_bulk()
    
    assets = []

    # Ahorro API: solo calcular espías de velas en los más líquidos del batch
    spy_allowed = set()
    if isinstance(rows, list) and rows:
        ordered = sorted(rows, key=lambda x: float(x.get("total_volume") or 0), reverse=True)
        top_rows = ordered[:MAX_SPY_ASSETS] if API_SAVING_MODE else ordered
        for rr in top_rows:
            spy_allowed.add(str(SYMBOL.get(str(rr.get("id") or ""), str(rr.get("symbol", "")).upper()) or ""))

    # --- PRE-CALCULAR SPY SIGNALS EN PARALELO (ThreadPoolExecutor) ---
    # Antes: 45+ llamadas HTTP secuenciales (~60s). Ahora: paralelas (~8-12s).
    spy_results = {}
    spy_tickers_to_fetch = [t for t in spy_allowed if t not in STABLECOIN_TICKERS and t not in EXCLUDED_TICKERS]

    def _fetch_spy_pair(ticker: str) -> tuple:
        chart = fetch_chart_spy(ticker)
        breakout = fetch_breakout_spy(ticker)
        return ticker, {"chart": chart, "breakout": breakout}

    if spy_tickers_to_fetch:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(_fetch_spy_pair, t): t for t in spy_tickers_to_fetch}
            for future in as_completed(futures):
                try:
                    ticker_result, signals = future.result()
                    spy_results[ticker_result] = signals
                except Exception:
                    pass

    for r in rows:
        ticker = str(SYMBOL.get(str(r.get("id") or ""), str(r.get("symbol", "")).upper()) or "")
        p = float(r.get("current_price") or 0)
        ch24 = float(r.get("price_change_percentage_24h") or 0)
        
        # Inyectar datos de Binance si CG falla
        b_data = b24h.get(f"{ticker}USDT")
        if b_data:
            if p <= 0:
                p = float(b_data.get("lastPrice") or 0)
                r["current_price"] = p
            if ch24 == 0:
                ch24 = float(b_data.get("priceChangePercent") or 0)
                r["price_change_percentage_24h"] = ch24
                if "Variacion 24h recuperada via Binance" not in note_flags:
                    note_flags.append("Variacion 24h recuperada via Binance")
        
        # Fallback individual de precio si el bulk falló o no estaba el ticker
        if p <= 0:
            p = get_binance_price(ticker)
            r["current_price"] = p
            if p > 0:
                if "Precios recuperados via Binance (individual)" not in note_flags:
                    note_flags.append("Precios recuperados via Binance (individual)")
        
        ch7 = float(r.get("price_change_percentage_7d_in_currency") or 0)
        sc = score_crypto(r)

        ticker = str(SYMBOL.get(str(r.get("id") or ""), str(r.get("symbol", "")).upper()) or "")
        sc = apply_research_overlay(ticker, sc, research_map or {})
        # Spy signals se pre-calculan en paralelo (ver abajo)
        spy_chart = spy_results.get(ticker, {}).get("chart", 0)
        spy_breakout = spy_results.get(ticker, {}).get("breakout", 0)
        sc["spy_chart"] = spy_chart
        sc["spy_breakout"] = spy_breakout
        sc["spy_confluence"] = int(sc["spy_news"] + sc["spy_euphoria"] + sc["spy_flow"] + sc["spy_whale"] + sc["spy_chart"] + sc["spy_breakout"])
        sc = apply_trade_edge_overlay(ticker, sc, edge_model)
        sc = apply_edge_guardrails(sc)

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
            "score_final": sc.get("score_final", sc["score"]),
            "confidence_pct": sc.get("confidence_pct", sc["score"]),
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
            "research_sentiment": sc.get("research_sentiment"),
            "research_catalyst_score": sc.get("research_catalyst_score", 0),
            "research_score_delta": sc.get("research_score_delta", 0),
            "trade_edge_score": sc.get("trade_edge_score", 0),
            "trade_edge_delta": sc.get("trade_edge_delta", 0),
            "trade_edge_hour": sc.get("trade_edge_hour"),
            "trade_edge_hour_score": sc.get("trade_edge_hour_score", 0),
            "setup_tag": sc.get("setup_tag", "base"),
            "setup_edge_score": sc.get("setup_edge_score", 0),
            "trade_edge_maturity": sc.get("trade_edge_maturity", 0),
            "senior_report": senior_report,
            "technical_report": technical_report,
            "sentiment_report": sentiment_report,
        })

    top = [a for a in sorted(assets, key=lambda x: (x.get("decision_final") == "BUY", x.get("gem_score", 0), x.get("score_final", x.get("score", 0))), reverse=True) if a.get("ticker") not in STABLECOIN_TICKERS and a.get("ticker") not in EXCLUDED_TICKERS and a.get("ticker") not in dynamic_excluded]
    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "assets": assets,
        "top_opportunities": top,
        "source": source_label,
        "api_saving_mode": API_SAVING_MODE,
        "spy_assets_limit": MAX_SPY_ASSETS,
        "notes": " | ".join(note_flags),
        "universe_core": sorted(universe.get("core") or []),
        "universe_watch": sorted(universe.get("watch") or []),
        "universe_excluded": sorted(dynamic_excluded),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUT, out)
    print(f"OK crypto snapshot -> {OUT}")


if __name__ == "__main__":
    main()
