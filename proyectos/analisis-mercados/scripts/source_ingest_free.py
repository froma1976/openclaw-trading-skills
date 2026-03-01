#!/usr/bin/env python3
import json
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, UTC, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CFG = BASE / "sources_config_free.json"
OUT_DIR = BASE / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "latest_snapshot_free.json"
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
FMP_API_KEY = os.getenv("FMP_API_KEY", "").strip()


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


def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def stddev(values, n):
    if len(values) < n:
        return None
    w = values[-n:]
    m = sum(w) / n
    var = sum((x - m) ** 2 for x in w) / n
    return var ** 0.5


def ema(values, n):
    if len(values) < n:
        return None
    k = 2 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = (v * k) + (e * (1 - k))
    return e


def rsi14(values):
    if len(values) < 15:
        return None
    gains = []
    losses = []
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[:14]) / 14
    avg_loss = sum(losses[:14]) / 14
    for i in range(14, len(gains)):
        avg_gain = (avg_gain * 13 + gains[i]) / 14
        avg_loss = (avg_loss * 13 + losses[i]) / 14
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def score_ticker_tech_base(ticker: str, chg5, chg20):
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
    quote = res[0].get("indicators", {}).get("quote", [{}])[0]
    closes_raw = quote.get("close", [])
    vols_raw = quote.get("volume", [])
    closes = [float(v) for v in closes_raw if v is not None]
    vols = [float(v) for v in vols_raw if v is not None]
    close = closes[-1] if closes else None

    chg5 = pct(closes[-1], closes[-6]) if len(closes) >= 6 else None
    chg20 = pct(closes[-1], closes[-21]) if len(closes) >= 21 else None

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    rsi = rsi14(closes)
    bb_mid = sma(closes, 20)
    bb_std = stddev(closes, 20)
    bb_upper = (bb_mid + 2 * bb_std) if bb_mid is not None and bb_std is not None else None
    bb_lower = (bb_mid - 2 * bb_std) if bb_mid is not None and bb_std is not None else None

    score_tech, reasons = score_ticker_tech_base(ticker, chg5, chg20)

    vol_avg20 = (sum(vols[-20:]) / 20) if len(vols) >= 20 else None
    vol_last = vols[-1] if vols else None
    rel_volume = (vol_last / vol_avg20) if (vol_last is not None and vol_avg20 not in (None, 0)) else None

    # ruptura simple de máximo 20 sesiones previas
    breakout_20 = False
    if len(closes) >= 21 and close is not None:
        prev_high_20 = max(closes[-21:-1])
        breakout_20 = close > prev_high_20

    if close is not None and ema20 is not None:
        if close > ema20:
            score_tech += 6
            reasons.append("price_above_ema20")
        else:
            score_tech -= 6
            reasons.append("price_below_ema20")

    if ema20 is not None and ema50 is not None:
        if ema20 > ema50:
            score_tech += 6
            reasons.append("ema20_above_ema50")
        else:
            score_tech -= 6
            reasons.append("ema20_below_ema50")

    if rsi is not None:
        if 50 <= rsi <= 70:
            score_tech += 5
            reasons.append("rsi_constructivo")
        elif rsi > 75:
            score_tech -= 3
            reasons.append("rsi_sobrecompra")
        elif rsi < 35:
            score_tech -= 5
            reasons.append("rsi_debil")

    if close is not None and bb_upper is not None and bb_lower is not None:
        if close > bb_upper:
            reasons.append("bollinger_breakout")
            score_tech += 4
        elif close < bb_lower:
            reasons.append("bollinger_breakdown")
            score_tech -= 4

    if rel_volume is not None:
        if rel_volume >= 1.5:
            score_tech += 8
            reasons.append("rel_volume_fuerte")
        elif rel_volume >= 1.2:
            score_tech += 4
            reasons.append("rel_volume_ok")

    if breakout_20 and (rel_volume is not None and rel_volume >= 1.2):
        score_tech += 10
        reasons.append("breakout_20_confirmado")
    elif breakout_20:
        score_tech += 4
        reasons.append("breakout_20_sin_confirmacion")

    score_tech = max(0, min(100, int(round(score_tech))))

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
        "ema20": round(ema20, 3) if ema20 is not None else None,
        "ema50": round(ema50, 3) if ema50 is not None else None,
        "rsi14": round(rsi, 2) if rsi is not None else None,
        "bb_upper": round(bb_upper, 3) if bb_upper is not None else None,
        "bb_lower": round(bb_lower, 3) if bb_lower is not None else None,
        "rel_volume": round(rel_volume, 2) if rel_volume is not None else None,
        "breakout_20": breakout_20,
        "score_tech": score_tech,
        "score": score_tech,
        "reasons": list(dict.fromkeys(reasons)),
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


def fetch_earnings_finnhub(symbol: str):
    if not FINNHUB_API_KEY:
        return None
    try:
        frm = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        to = (datetime.now(UTC) + timedelta(days=14)).strftime("%Y-%m-%d")
        url = (
            "https://finnhub.io/api/v1/calendar/earnings"
            f"?from={frm}&to={to}&symbol={urllib.parse.quote(symbol)}&token={urllib.parse.quote(FINNHUB_API_KEY)}"
        )
        data = get_json(url)
        arr = data.get("earningsCalendar", []) or []
        if not arr:
            return None
        # prioriza el evento más cercano
        arr = sorted(arr, key=lambda x: str(x.get("date") or "9999-99-99"))
        e = arr[0]
        return {
            "symbol": symbol,
            "source": "finnhub",
            "date": e.get("date"),
            "eps_estimate": e.get("epsEstimate"),
            "eps_actual": e.get("epsActual"),
            "revenue_estimate": e.get("revenueEstimate"),
            "revenue_actual": e.get("revenueActual"),
        }
    except Exception:
        return None


def fetch_earnings_fmp(symbol: str):
    if not FMP_API_KEY:
        return None
    try:
        url = f"https://financialmodelingprep.com/api/v3/historical/earning_calendar/{urllib.parse.quote(symbol)}?limit=1&apikey={urllib.parse.quote(FMP_API_KEY)}"
        data = get_json(url)
        if not isinstance(data, list) or not data:
            return None
        e = data[0]
        return {
            "symbol": symbol,
            "source": "fmp",
            "date": e.get("date"),
            "eps_estimate": e.get("epsEstimated"),
            "eps_actual": e.get("eps"),
            "revenue_estimate": e.get("revenueEstimated"),
            "revenue_actual": e.get("revenue"),
        }
    except Exception:
        return None


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


def macro_regime(out):
    vals = {m.get("series"): m.get("latest_value") for m in out.get("macro", []) if isinstance(m, dict)}
    vix = None
    dgs10 = None
    try:
        vix = float(vals.get("VIXCLS")) if vals.get("VIXCLS") not in (None, "") else None
    except Exception:
        pass
    try:
        dgs10 = float(vals.get("DGS10")) if vals.get("DGS10") not in (None, "") else None
    except Exception:
        pass

    macro_adj = 0
    macro_reasons = []
    if vix is not None:
        if vix < 18:
            macro_adj += 8
            macro_reasons.append("macro_vix_bajo")
        elif vix <= 22:
            macro_adj += 2
            macro_reasons.append("macro_vix_neutro")
        else:
            macro_adj -= 8
            macro_reasons.append("macro_vix_alto")
    if dgs10 is not None and dgs10 > 4.5:
        macro_adj -= 3
        macro_reasons.append("macro_yield10_alto")

    return {
        "vix": vix,
        "dgs10": dgs10,
        "macro_adj": macro_adj,
        "macro_reasons": macro_reasons,
    }


def social_map(out):
    mp = {}
    for s in out.get("social", []):
        if not isinstance(s, dict):
            continue
        sym = s.get("symbol")
        ss = s.get("sentiment_score")
        if sym:
            mp[sym] = ss
    return mp


def headline_signal_map(out):
    # Heurística gratis: extrae señales de titulares (earnings/guidance/spinoff/insider/options/catalyst)
    symbols = [m.get("ticker") for m in out.get("market", []) if isinstance(m, dict) and m.get("ticker")]
    mp = {s: {"fundamental": 0, "catalyst": 0, "spinoff": 0, "insider": 0, "options": 0, "hits": 0} for s in symbols}

    KEY = {
        "fundamental": ["earnings", "beneficio", "results", "beat", "miss", "guidance", "outlook"],
        "catalyst": ["launch", "trial", "approval", "contract", "data center", "ai"],
        "spinoff": ["spin-off", "spinoff", "escisión"],
        "insider": ["insider", "director buy", "ceo bought"],
        "options": ["options", "open interest", "calls"],
    }

    for feed in out.get("news", []):
        for item in feed.get("items", []):
            t = ((item.get("title") or "") + " " + (item.get("title_es") or "")).lower()
            for s in symbols:
                if s.lower() not in t:
                    continue
                mp[s]["hits"] += 1
                for k, kws in KEY.items():
                    if any(kw in t for kw in kws):
                        mp[s][k] += 1
    return mp


def earnings_label(e):
    if not e:
        return "No Data"
    eps_a = e.get("eps_actual")
    eps_e = e.get("eps_estimate")
    if eps_a is None or eps_e is None:
        return "Earnings Pending"
    try:
        return "Earnings Beat" if float(eps_a) > float(eps_e) else "Earnings Miss/Inline"
    except Exception:
        return "Earnings Pending"


def earnings_map(out):
    mp = {}
    for e in out.get("earnings", []):
        if isinstance(e, dict) and e.get("symbol"):
            mp[e["symbol"]] = e
    return mp


def apply_final_score(out):
    regime = macro_regime(out)
    smap = social_map(out)
    hmap = headline_signal_map(out)
    emap = earnings_map(out)

    for m in out.get("market", []):
        if not isinstance(m, dict) or not m.get("ok"):
            continue

        ticker = m.get("ticker")
        tech = int(m.get("score_tech", m.get("score", 50)) or 50)
        social = smap.get(ticker)
        hs = hmap.get(ticker, {"fundamental": 0, "catalyst": 0, "spinoff": 0, "insider": 0, "options": 0, "hits": 0})
        er = emap.get(ticker)

        social_adj = 0
        social_reason = None
        if social is not None:
            if social >= 50:
                social_adj = 8
                social_reason = "social_bullish"
            elif social <= -40:
                social_adj = -8
                social_reason = "social_bearish"

        # Sub-scores asimetría V2 (MVP heurístico con fuentes gratis)
        fundamental_score = min(20, hs["fundamental"] * 5)
        # refuerzo por earnings reales cuando existen
        if er:
            eps_a = er.get("eps_actual")
            eps_e = er.get("eps_estimate")
            rev_a = er.get("revenue_actual")
            rev_e = er.get("revenue_estimate")
            try:
                if eps_a is not None and eps_e is not None and float(eps_a) > float(eps_e):
                    fundamental_score += 8
            except Exception:
                pass
            try:
                if rev_a is not None and rev_e is not None and float(rev_a) > float(rev_e):
                    fundamental_score += 6
            except Exception:
                pass
            fundamental_score = min(25, fundamental_score)

        catalyst_score = min(15, hs["catalyst"] * 5)
        spinoff_score = 12 if hs["spinoff"] > 0 else 0
        insider_score = 10 if hs["insider"] > 0 else 0
        options_score = 10 if hs["options"] > 0 else 0

        asym_bonus = fundamental_score + catalyst_score + spinoff_score + insider_score + options_score

        final = tech + regime["macro_adj"] + social_adj + asym_bonus
        final = max(0, min(100, final))

        # Convergencia: estructural + capital + técnico
        structural_ok = (fundamental_score + catalyst_score + spinoff_score) >= 10
        capital_ok = (insider_score + options_score) > 0 or (social is not None and social >= 50)
        technical_ok = tech >= 55
        conv_count = sum([1 if structural_ok else 0, 1 if capital_ok else 0, 1 if technical_ok else 0])

        state = "WATCH"
        if conv_count >= 2 and final >= 65:
            state = "READY"
        if conv_count == 3 and final >= 75:
            state = "TRIGGERED"

        m["score_social"] = social
        m["earnings_label"] = earnings_label(er)
        m["score_macro_adj"] = regime["macro_adj"]
        m["score_asymmetry"] = asym_bonus
        m["fundamental_inflection_score"] = fundamental_score
        m["catalyst_score"] = catalyst_score
        m["spinoff_score"] = spinoff_score
        m["insider_score"] = insider_score
        m["options_flow_score"] = options_score
        m["convergence_count"] = conv_count
        m["state"] = state
        m["score_final"] = final
        m["score"] = final

        reasons = m.get("reasons", [])
        reasons.extend(regime["macro_reasons"])
        if social_reason:
            reasons.append(social_reason)
        if fundamental_score > 0:
            reasons.append("fundamental_inflection")
        if er:
            reasons.append("earnings_calendar_signal")
        if catalyst_score > 0:
            reasons.append("catalyst_detected")
        if spinoff_score > 0:
            reasons.append("spinoff_detected")
        if insider_score > 0:
            reasons.append("insider_signal_detected")
        if options_score > 0:
            reasons.append("options_flow_detected")
        m["reasons"] = list(dict.fromkeys(reasons))

    out["macro_regime"] = regime


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))

    out = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "macro": [],
        "market": [],
        "news": [],
        "social": [],
        "earnings": []
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

    # Earnings calendar (si hay API key)
    for t in cfg["market"]["tickers"]:
        e = fetch_earnings_finnhub(t) or fetch_earnings_fmp(t)
        if e:
            out["earnings"].append(e)

    apply_final_score(out)

    ranked = [m for m in out["market"] if isinstance(m, dict) and m.get("ok")]
    ranked.sort(key=lambda x: x.get("score_final", x.get("score", 0)), reverse=True)
    out["top_opportunities"] = ranked[:5]

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK snapshot -> {OUT}")


if __name__ == "__main__":
    main()
