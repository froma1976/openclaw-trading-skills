#!/usr/bin/env python3
import csv
import re
import urllib.request
from pathlib import Path

OUT_DIR = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data")
OUT_CSV = OUT_DIR / "public_trader_histories_mql5.csv"

URLS = [
    "https://www.mql5.com/en/signals/2225567",  # BTC ICMarkets 50 high risk
    "https://www.mql5.com/en/signals/1506209",  # BTC Portfolio
    "https://www.mql5.com/en/signals/2267681",  # Bitcoin BTC Ethereum ETH Crypto Trading
    "https://www.mql5.com/en/signals/2317805",  # HiJack BTC
    "https://www.mql5.com/en/signals/2304550",  # BTC Breakout
    "https://www.mql5.com/en/signals/2300970",  # Aura BTC LowRisk
    "https://www.mql5.com/en/signals/2278370",  # BTC trade with small equity
    "https://www.mql5.com/en/signals/2325792",  # ANGELS 6K BTC
    "https://www.mql5.com/en/signals/2329276",  # Master of sol
]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def pick(pattern: str, text: str):
    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return clean(m.group(1)) if m else ""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for url in URLS:
        try:
            html = fetch(url)
        except Exception as e:
            rows.append({"url": url, "status": f"error:{e}"})
            continue

        # Basic status check (disabled/private/etc.)
        lowered = html.lower()
        if "provider has disabled this signal" in lowered:
            rows.append({"url": url, "status": "disabled"})
            continue

        title = pick(r"<h1[^>]*>(.*?)</h1>", html)
        provider = pick(r"<a[^>]+href=\"/en/users/[^\"]+\"[^>]*>(.*?)</a>", html)

        growth = pick(r"Growth:\s*</[^>]+>\s*([^<]+)", html)
        profit = pick(r"Profit:\s*</[^>]+>\s*([^<]+)", html)
        equity = pick(r"Equity:\s*</[^>]+>\s*([^<]+)", html)
        latest_trade = pick(r"Latest trade:\s*</[^>]+>\s*([^<]+)", html)
        started = pick(r"Started:\s*</[^>]+>\s*([^<]+)", html)

        trades = pick(r"Trades:\s*</[^>]+>\s*([^<]+)", html)
        profit_trades = pick(r"Profit Trades:\s*</[^>]+>\s*([^<]+)", html)
        loss_trades = pick(r"Loss Trades:\s*</[^>]+>\s*([^<]+)", html)
        best_trade = pick(r"Best trade:\s*</[^>]+>\s*([^<]+)", html)
        worst_trade = pick(r"Worst trade:\s*</[^>]+>\s*([^<]+)", html)
        profit_factor = pick(r"Profit Factor:\s*</[^>]+>\s*([^<]+)", html)
        expected_payoff = pick(r"Expected Payoff:\s*</[^>]+>\s*([^<]+)", html)

        btc_deals = ""
        sol_deals = ""
        m_btc = re.search(r">BTCUSD<.*?>\s*([0-9][0-9,\.]*)\s*</", html, flags=re.IGNORECASE | re.DOTALL)
        if m_btc:
            btc_deals = clean(m_btc.group(1))
        m_sol = re.search(r">SOLUSD<.*?>\s*([0-9][0-9,\.]*)\s*</", html, flags=re.IGNORECASE | re.DOTALL)
        if m_sol:
            sol_deals = clean(m_sol.group(1))

        rows.append(
            {
                "url": url,
                "status": "ok",
                "source": "mql5-public",
                "provider": provider,
                "signal_name": title,
                "growth": growth,
                "profit": profit,
                "equity": equity,
                "started": started,
                "latest_trade": latest_trade,
                "trades_total": trades,
                "profit_trades": profit_trades,
                "loss_trades": loss_trades,
                "best_trade": best_trade,
                "worst_trade": worst_trade,
                "profit_factor": profit_factor,
                "expected_payoff": expected_payoff,
                "btc_deals": btc_deals,
                "sol_deals": sol_deals,
            }
        )

    fields = [
        "url",
        "status",
        "source",
        "provider",
        "signal_name",
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

    print(f"OK -> {OUT_CSV} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
