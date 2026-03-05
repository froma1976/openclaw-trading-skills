#!/usr/bin/env python3
import csv
import re
import urllib.request
from pathlib import Path

OUT_DIR = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data")
OUT_CSV = OUT_DIR / "public_trader_histories_mql5_bulk.csv"

BASE_LIST_URLS = [
    "https://www.mql5.com/en/signals/mt4/page{n}",
    "https://www.mql5.com/en/signals/mt5/page{n}",
]
PAGES_PER_LIST = 10


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def strip_html(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text


def grab_between(text: str, start: str, end: str = None) -> str:
    i = text.find(start)
    if i == -1:
        return ""
    s = text[i + len(start):]
    if end:
        j = s.find(end)
        if j != -1:
            s = s[:j]
    return s.strip()


def extract_metrics(text: str):
    growth = grab_between(text, "Growth:", "Profit:")
    profit = grab_between(text, "Profit:", "Equity:")
    equity = grab_between(text, "Equity:", "Balance:")
    latest_trade = grab_between(text, "Latest trade:", "Trades per week:")
    started = grab_between(text, "Started:", "More from author:")

    trades_total = grab_between(text, "Trades:", "Profit Trades:")
    profit_trades = grab_between(text, "Profit Trades:", "Loss Trades:")
    loss_trades = grab_between(text, "Loss Trades:", "Best trade:")
    best_trade = grab_between(text, "Best trade:", "Worst trade:")
    worst_trade = grab_between(text, "Worst trade:", "Gross Profit:")
    profit_factor = grab_between(text, "Profit Factor:", "Expected Payoff:")
    expected_payoff = grab_between(text, "Expected Payoff:", "Average Profit:")

    btc_deals = ""
    sol_deals = ""
    m_btc = re.search(r"BTCUSD\s+([0-9][0-9,\.]*)", text, flags=re.I)
    if m_btc:
        btc_deals = m_btc.group(1)
    m_sol = re.search(r"SOLUSD\s+([0-9][0-9,\.]*)", text, flags=re.I)
    if m_sol:
        sol_deals = m_sol.group(1)

    return {
        "growth": growth,
        "profit": profit,
        "equity": equity,
        "latest_trade": latest_trade,
        "started": started,
        "trades_total": trades_total,
        "profit_trades": profit_trades,
        "loss_trades": loss_trades,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "profit_factor": profit_factor,
        "expected_payoff": expected_payoff,
        "btc_deals": btc_deals,
        "sol_deals": sol_deals,
    }


def extract_signal_links(html: str):
    links = set(re.findall(r'href="(/en/signals/\d+)(?:\?[^\"]*)?"', html, flags=re.I))
    return sorted(links)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    discovered = set()
    for tpl in BASE_LIST_URLS:
        for n in range(1, PAGES_PER_LIST + 1):
            url = tpl.format(n=n)
            try:
                html = fetch(url)
            except Exception:
                continue
            for rel in extract_signal_links(html):
                discovered.add("https://www.mql5.com" + rel)

    rows = []
    for url in sorted(discovered):
        try:
            html = fetch(url)
        except Exception as e:
            rows.append({"url": url, "status": f"error:{e}"})
            continue

        low = html.lower()
        if "provider has disabled this signal" in low:
            rows.append({"url": url, "status": "disabled"})
            continue

        text = strip_html(html)

        title = grab_between(text, "Signals /", "Signals")
        if not title:
            # fallback: first h1-like phrase in text
            m_title = re.search(r"Copy trades of the\s+(.+?)\s+trading signal", text, flags=re.I)
            title = m_title.group(1).strip() if m_title else ""

        # Keep BTC/SOL related signals only
        hay = f"{title} {text[:5000]}".lower()
        is_btc_sol = any(k in hay for k in [" btc", "btcusd", " bitcoin", " sol", "solusd", "solana"])
        if not is_btc_sol:
            continue

        provider = grab_between(text, "Copy trades of the", "trading signal")
        if not provider:
            provider = ""

        m = extract_metrics(text)

        rows.append(
            {
                "url": url,
                "status": "ok",
                "source": "mql5-public",
                "signal_name": title,
                "provider_hint": provider,
                **m,
            }
        )

    fields = [
        "url",
        "status",
        "source",
        "signal_name",
        "provider_hint",
        "growth",
        "profit",
        "equity",
        "started",
        "latest_trade",
        "trades_total",
        "profit_trades",
        "loss_trades",
        "best_trade",
        "worst_trade",
        "profit_factor",
        "expected_payoff",
        "btc_deals",
        "sol_deals",
    ]

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    ok_rows = sum(1 for r in rows if r.get("status") == "ok")
    print(f"DISCOVERED={len(discovered)} FILTERED_ROWS={len(rows)} OK={ok_rows} OUT={OUT_CSV}")


if __name__ == "__main__":
    main()
