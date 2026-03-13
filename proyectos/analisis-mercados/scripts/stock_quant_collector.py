import urllib.request
import urllib.parse
import json
import csv
import os
from datetime import datetime, UTC
from pathlib import Path

# Activos principales para no saturar las APIs
# Usamos Yahoo Finance público (que no requiere API key para datos básicos, límite amplio)
TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]
DB_PATH = Path("C:/Users/Fernando/.openclaw/workspace/memory/stock_price_warehouse.csv")

def run():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    file_exists = DB_PATH.exists()
    
    with open(DB_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp_utc", "asset", "price", "volume"])
            
        now_str = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        
        for tkr in TICKERS:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(tkr)}?range=1d&interval=1m"
                req = urllib.request.Request(url, headers={"User-Agent": "agent-ops-collect/1.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode("utf-8", errors="ignore"))
                
                res = (((data or {}).get("chart") or {}).get("result") or [{}])[0]
                meta = res.get("meta", {})
                price = meta.get("regularMarketPrice")
                vol = meta.get("regularMarketVolume", 0)
                
                if price:
                    writer.writerow([now_str, tkr, round(float(price), 2), vol])
                    print(f"[{now_str}] {tkr}: {price}")
                    
            except Exception as e:
                print(f"Error fetching {tkr}: {e}")

if __name__ == "__main__":
    run()
