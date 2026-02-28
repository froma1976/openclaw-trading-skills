#!/usr/bin/env python3
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, UTC
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CFG = BASE / "sources_config_free.json"
OUT_DIR = BASE / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "latest_snapshot_free.json"


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "alpha-scout/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def get_text(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "alpha-scout/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def fetch_fred_series(series_id: str):
    # Endpoint CSV público de FRED graph (sin API key para lectura simple)
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={urllib.parse.quote(series_id)}"
    text = get_text(url)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return {"series": series_id, "latest": None}
    # última línea con valor no vacío
    latest_date, latest_value = None, None
    for ln in reversed(lines[1:]):
        parts = ln.split(",")
        if len(parts) >= 2 and parts[1] not in ("", "."):
            latest_date, latest_value = parts[0], parts[1]
            break
    return {"series": series_id, "latest_date": latest_date, "latest_value": latest_value}


def pct(a, b):
    try:
        if a is None or b is None or b == 0:
            return None
        return round(((a - b) / b) * 100, 2)
    except Exception:
        return None


def score_ticker(ticker: str, chg5, chg20):
    score = 50
    reasons = []

    if chg5 is not None:
        if chg5 > 2:
            score += 12
            reasons.append("momento_5d_fuerte")
        elif chg5 > 0:
            score += 6
            reasons.append("momento_5d_positivo")
        elif chg5 < -2:
            score -= 10
            reasons.append("momento_5d_debil")

    if chg20 is not None:
        if chg20 > 5:
            score += 18
            reasons.append("tendencia_20d_fuerte")
        elif chg20 > 0:
            score += 8
            reasons.append("tendencia_20d_positiva")
        elif chg20 < -5:
            score -= 15
            reasons.append("tendencia_20d_debil")

    # sesgo de priorización NASDAQ tech
    if ticker in {"NVDA", "MSFT", "AMZN", "META", "AMD", "AVGO", "QQQ"}:
        score += 4
        reasons.append("universo_prioritario")

    score = max(0, min(100, score))
    return score, reasons


def fetch_yahoo_ticker(ticker: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?range=3mo&interval=1d"
    data = get_json(url)
    res = data.get("chart", {}).get("result", [])
    if not res:
        return {"ticker": ticker, "ok": False}
    meta = res[0].get("meta", {})
    closes_raw = res[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    closes = [float(v) for v in closes_raw if v is not None]
    close = closes[-1] if closes else None

    chg5 = pct(closes[-1], closes[-6]) if len(closes) >= 6 else None
    chg20 = pct(closes[-1], closes[-21]) if len(closes) >= 21 else None
    score, reasons = score_ticker(ticker, chg5, chg20)

    return {
        "ticker": ticker,
        "ok": True,
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "regularMarketPrice": meta.get("regularMarketPrice"),
        "previousClose": meta.get("previousClose"),
        "lastCloseSeries": close,
        "chg_5d_pct": chg5,
        "chg_20d_pct": chg20,
        "score": score,
        "reasons": reasons,
    }


def translate_to_es(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    try:
        # Endpoint gratuito (no oficial) de Google Translate para MVP
        q = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=es&dt=t&q={q}"
        data = get_text(url)
        parsed = json.loads(data)
        translated = "".join(chunk[0] for chunk in parsed[0] if chunk and chunk[0])
        return translated or text
    except Exception:
        return text


def fetch_rss(url: str, limit=5):
    xml = get_text(url)
    root = ET.fromstring(xml)
    items = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        items.append({
            "title": title,
            "title_es": translate_to_es(title),
            "link": (item.findtext("link") or "").strip(),
            "pubDate": (item.findtext("pubDate") or "").strip(),
        })
    return {"feed": url, "items": items}


def fetch_stocktwits_symbol(symbol: str):
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{urllib.parse.quote(symbol)}.json"
    data = get_json(url)
    msgs = data.get("messages", [])[:30]
    bullish = 0
    bearish = 0
    for m in msgs:
        entities = m.get("entities") or {}
        sentiment = entities.get("sentiment") or {}
        sent = sentiment.get("basic")
        if sent == "Bullish":
            bullish += 1
        elif sent == "Bearish":
            bearish += 1

    total_tagged = bullish + bearish
    score = None
    if total_tagged > 0:
        score = round(((bullish - bearish) / total_tagged) * 100, 1)

    return {
        "symbol": symbol,
        "messages_checked": len(msgs),
        "bullish": bullish,
        "bearish": bearish,
        "sentiment_score": score,
    }


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))

    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "macro": [],
        "market": [],
        "news": [],
        "social": []
    }

    for s in cfg["macro"]["fred_series"]:
        try:
            out["macro"].append(fetch_fred_series(s))
        except Exception as e:
            out["macro"].append({"series": s, "error": str(e)})

    for t in cfg["market"]["tickers"]:
        try:
            out["market"].append(fetch_yahoo_ticker(t))
        except Exception as e:
            out["market"].append({"ticker": t, "error": str(e), "score": 0})

    # ranking simple por score
    ranked = [m for m in out["market"] if isinstance(m, dict) and m.get("ok")]
    ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
    out["top_opportunities"] = ranked[:5]

    for f in cfg["news"]["rss_feeds"]:
        try:
            out["news"].append(fetch_rss(f))
        except Exception as e:
            out["news"].append({"feed": f, "error": str(e), "items": []})

    for s in cfg.get("social", {}).get("symbols", []):
        try:
            out["social"].append(fetch_stocktwits_symbol(s))
        except Exception as e:
            out["social"].append({"symbol": s, "error": str(e)})

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK snapshot -> {OUT}")


if __name__ == "__main__":
    main()
