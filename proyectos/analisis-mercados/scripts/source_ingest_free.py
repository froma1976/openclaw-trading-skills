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


def fetch_yahoo_ticker(ticker: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?range=3mo&interval=1d"
    data = get_json(url)
    res = data.get("chart", {}).get("result", [])
    if not res:
        return {"ticker": ticker, "ok": False}
    meta = res[0].get("meta", {})
    closes = res[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    close = None
    for v in reversed(closes):
        if v is not None:
            close = float(v)
            break
    return {
        "ticker": ticker,
        "ok": True,
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "regularMarketPrice": meta.get("regularMarketPrice"),
        "previousClose": meta.get("previousClose"),
        "lastCloseSeries": close,
    }


def fetch_rss(url: str, limit=5):
    xml = get_text(url)
    root = ET.fromstring(xml)
    items = []
    for item in root.findall(".//item")[:limit]:
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "pubDate": (item.findtext("pubDate") or "").strip(),
        })
    return {"feed": url, "items": items}


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))

    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "macro": [],
        "market": [],
        "news": []
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
            out["market"].append({"ticker": t, "error": str(e)})

    for f in cfg["news"]["rss_feeds"]:
        try:
            out["news"].append(fetch_rss(f))
        except Exception as e:
            out["news"].append({"feed": f, "error": str(e), "items": []})

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK snapshot -> {OUT}")


if __name__ == "__main__":
    main()
