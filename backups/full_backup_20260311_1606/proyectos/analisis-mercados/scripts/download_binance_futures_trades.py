#!/usr/bin/env python3
import os, csv, json, time, hmac, hashlib
from pathlib import Path
from urllib import parse, request

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ENV = Path("C:/Users/Fernando/.openclaw/.env")
OUTDIR = BASE / "data" / "history"
API = "https://fapi.binance.com"


def load_env(path: Path):
    if not path.exists():
        return
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k and k not in os.environ:
            os.environ[k] = v


def signed_get(path: str, params: dict, key: str, secret: str):
    q = parse.urlencode(params)
    sig = hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()
    url = f"{API}{path}?{q}&signature={sig}"
    req = request.Request(url, headers={"X-MBX-APIKEY": key, "User-Agent": "openclaw-binance-futures/1.0"})
    with request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_user_trades(symbol: str, days: int, key: str, secret: str):
    start_ms = int((time.time() - days * 86400) * 1000)
    out = []
    from_id = None
    while True:
        p = {
            "symbol": symbol,
            "limit": 1000,
            "recvWindow": 10000,
            "timestamp": int(time.time() * 1000),
        }
        if from_id is not None:
            p["fromId"] = from_id
        else:
            p["startTime"] = start_ms
        rows = signed_get("/fapi/v1/userTrades", p, key, secret)
        if not isinstance(rows, list) or len(rows) == 0:
            break
        out.extend(rows)
        if len(rows) < 1000:
            break
        from_id = int(rows[-1]["id"]) + 1
        time.sleep(0.12)
    return out


def main():
    load_env(ENV)
    key = os.getenv("BINANCE_API_KEY", "")
    secret = os.getenv("BINANCE_API_SECRET", "")
    if not key or not secret:
        print(json.dumps({"ok": False, "error": "missing BINANCE_API_KEY/BINANCE_API_SECRET"}, ensure_ascii=False))
        return

    OUTDIR.mkdir(parents=True, exist_ok=True)
    report = {"ok": True, "market": "um_futures", "symbols": {}}

    for sym in [
        "BTCUSDT","SOLUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT",
        "DOGEUSDT","AVAXUSDT","LINKUSDT","DOTUSDT","LTCUSDT","BCHUSDT",
        "MATICUSDT","UNIUSDT","APTUSDT","ARBUSDT","OPUSDT","INJUSDT",
        "SUIUSDT","FILUSDT"
    ]:
        try:
            rows = fetch_user_trades(sym, days=180, key=key, secret=secret)
        except Exception as e:
            report["symbols"][sym] = {"ok": False, "error": str(e)}
            continue

        out = OUTDIR / f"binance_futures_usertrades_{sym}.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            fields = [
                "id","orderId","symbol","side","positionSide","price","qty","realizedPnl","commission","commissionAsset","time","maker","buyer"
            ]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in fields})

        report["symbols"][sym] = {"ok": True, "rows": len(rows), "file": str(out)}

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
