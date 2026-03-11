#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
UNIVERSE = BASE / "data" / "universe_status.json"
OUT_JSON = BASE / "data" / "core_market_research.json"
OUT_MD = BASE / "reports" / "core_market_research_latest.md"
ENV = Path("C:/Users/Fernando/.openclaw/.env")
ANTIGRAVITY_MCP = Path("C:/Users/Fernando/AppData/Roaming/Antigravity/User/mcp.json")

ASSET_QUERIES = {
    "DOGE": "Dogecoin DOGE crypto market catalyst",
    "AAVE": "Aave AAVE crypto market catalyst",
    "SUI": "Sui SUI crypto market catalyst",
    "SOL": "Solana SOL crypto market catalyst",
}


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_env_file():
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_antigravity_keys():
    if not ANTIGRAVITY_MCP.exists():
        return
    try:
        data = json.loads(ANTIGRAVITY_MCP.read_text(encoding="utf-8"))
    except Exception:
        return
    servers = data.get("mcpServers") or {}
    brave = ((servers.get("brave-search") or {}).get("env") or {}).get("BRAVE_API_KEY")
    tavily = ((servers.get("tavily-search") or {}).get("env") or {}).get("TAVILY_API_KEY")
    if brave:
        os.environ.setdefault("BRAVE_API_KEY", brave)
    if tavily:
        os.environ.setdefault("TAVILY_API_KEY", tavily)


def load_core_assets():
    data = {"core": []}
    if UNIVERSE.exists():
        data = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    return [str(x).upper() for x in (data.get("core") or [])]


def fetch_json(url: str, headers=None, data=None):
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def brave_news(query: str, api_key: str):
    url = "https://api.search.brave.com/res/v1/news/search?" + urllib.parse.urlencode(
        {"q": query, "count": 5, "freshness": "pd", "search_lang": "en", "country": "US"}
    )
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    data = fetch_json(url, headers=headers)
    results = []
    for row in (data.get("results") or [])[:5]:
        results.append(
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "description": row.get("description"),
                "age": row.get("age"),
                "source": (row.get("meta_url") or {}).get("hostname"),
            }
        )
    return results


def tavily_search(query: str, api_key: str):
    payload = json.dumps(
        {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "topic": "news",
            "max_results": 5,
            "include_answer": True,
            "include_raw_content": False,
        }
    ).encode("utf-8")
    data = fetch_json(
        "https://api.tavily.com/search",
        headers={"Content-Type": "application/json"},
        data=payload,
    )
    results = []
    for row in (data.get("results") or [])[:5]:
        results.append(
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "content": row.get("content"),
                "score": row.get("score"),
            }
        )
    return {"answer": data.get("answer"), "results": results}


def score_signal(brave_rows: list, tavily_payload: dict):
    text = " ".join(
        [
            *(str(x.get("title") or "") + " " + str(x.get("description") or "") for x in brave_rows),
            str(tavily_payload.get("answer") or ""),
            *(str(x.get("title") or "") + " " + str(x.get("content") or "") for x in (tavily_payload.get("results") or [])),
        ]
    ).lower()
    bullish = ["upgrade", "approval", "launch", "inflow", "partnership", "adoption", "growth", "surge", "record"]
    bearish = ["hack", "exploit", "outflow", "downgrade", "lawsuit", "delay", "sell-off", "risk", "investigation"]
    pos = sum(1 for word in bullish if word in text)
    neg = sum(1 for word in bearish if word in text)
    if pos > neg:
        sentiment = "positive"
    elif neg > pos:
        sentiment = "negative"
    else:
        sentiment = "mixed"
    return {
        "sentiment": sentiment,
        "bullish_hits": pos,
        "bearish_hits": neg,
        "catalyst_score": pos - neg,
    }


def main():
    load_env_file()
    load_antigravity_keys()
    brave_key = os.getenv("BRAVE_API_KEY", "").strip()
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
    core = load_core_assets()

    report = {
        "generated_at": now_iso(),
        "core": core,
        "sources": {"brave": bool(brave_key), "tavily": bool(tavily_key)},
        "assets": [],
    }

    for ticker in core:
        query = ASSET_QUERIES.get(ticker, f"{ticker} crypto market catalyst")
        asset = {"ticker": ticker, "query": query, "brave_news": [], "tavily": {"answer": "", "results": []}, "signal": {}}
        if brave_key:
            try:
                asset["brave_news"] = brave_news(query, brave_key)
            except Exception as exc:
                asset["brave_error"] = str(exc)
        if tavily_key:
            try:
                asset["tavily"] = tavily_search(query, tavily_key)
            except Exception as exc:
                asset["tavily_error"] = str(exc)
        asset["signal"] = score_signal(asset.get("brave_news") or [], asset.get("tavily") or {})
        report["assets"].append(asset)

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Core market research",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Core universe: {', '.join(core) if core else '-'}",
        f"- Sources: Brave={'on' if brave_key else 'off'} | Tavily={'on' if tavily_key else 'off'}",
        "",
    ]
    for asset in report["assets"]:
        signal = asset.get("signal") or {}
        lines += [
            f"## {asset['ticker']}",
            f"- Query: {asset['query']}",
            f"- Sentiment: {signal.get('sentiment')} | Catalyst score: {signal.get('catalyst_score')}",
        ]
        answer = ((asset.get("tavily") or {}).get("answer") or "").strip()
        if answer:
            lines.append(f"- Tavily summary: {answer}")
        brave_rows = asset.get("brave_news") or []
        if brave_rows:
            lines.append("- Brave headlines:")
            for row in brave_rows[:3]:
                lines.append(f"  - {row.get('title')} ({row.get('source') or 'source'})")
        tavily_rows = ((asset.get("tavily") or {}).get("results") or [])[:3]
        if tavily_rows:
            lines.append("- Tavily results:")
            for row in tavily_rows:
                lines.append(f"  - {row.get('title')}")
        if asset.get("brave_error"):
            lines.append(f"- Brave error: {asset['brave_error']}")
        if asset.get("tavily_error"):
            lines.append(f"- Tavily error: {asset['tavily_error']}")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "assets": len(report["assets"]), "output": str(OUT_JSON), "markdown": str(OUT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
