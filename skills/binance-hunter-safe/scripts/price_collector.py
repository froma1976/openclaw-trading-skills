import urllib.request
import json
import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'memory')
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, 'price_warehouse.sqlite')

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "TSLA"]

def get_binance_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return float(data['price'])
    except Exception:
        return None

def main():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS asset_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset TEXT NOT NULL,
                    price REAL NOT NULL,
                    timestamp_utc DATETIME DEFAULT CURRENT_TIMESTAMP
                 )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_asset ON asset_prices(asset)')
    
    count = 0
    for asset in ASSETS:
        if asset.endswith("USDT"):
            px = get_binance_price(asset)
            if px is not None:
                c.execute("INSERT INTO asset_prices (asset, price) VALUES (?, ?)", (asset, px))
                count += 1
                
    conn.commit()
    conn.close()
    if count > 0:
        print(f"Guardados {count} precios correctamente en el Warehouse.")
    else:
        print("No se pudo extraer ningun precio.")

if __name__ == "__main__":
    main()
