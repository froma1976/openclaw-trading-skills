#!/usr/bin/env python3
import argparse
import csv
import json
import time
from datetime import datetime, UTC, timedelta
from pathlib import Path
from urllib import parse, request

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
OUTDIR = BASE / "data" / "history"
API = "https://api.binance.com/api/v3/klines"


def to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1000):
    q = parse.urlencode({
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit,
    })
    url = f"{API}?{q}"
    req = request.Request(url, headers={"User-Agent": "history-downloader/1.0"})
    with request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def append_rows(csv_path: Path, rows):
    exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["open_time", "open", "high", "low", "close", "volume", "close_time"])
        for k in rows:
            w.writerow([k[0], k[1], k[2], k[3], k[4], k[5], k[6]])


def last_open_time(csv_path: Path):
    if not csv_path.exists():
        return None
    try:
        with csv_path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
                if data.count(b"\n") >= 2:
                    break
            lines = data.decode("utf-8", errors="ignore").strip().splitlines()
            if len(lines) < 2:
                return None
            last = lines[-1].split(",")[0]
            return int(last)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--interval", default="5m")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--incremental", action="store_true")
    ap.add_argument("--sleep-ms", type=int, default=250)
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    OUTDIR.mkdir(parents=True, exist_ok=True)

    end_dt = datetime.now(UTC)
    start_dt = end_dt - timedelta(days=365 * args.years)
    end_ms = to_ms(end_dt)

    report = {"started_at": end_dt.isoformat(), "symbols": {}}

    for symbol in symbols:
        csv_path = OUTDIR / f"{symbol}_{args.interval}.csv"
        if args.incremental:
            lo = last_open_time(csv_path)
            start_ms = (lo + 1) if lo else to_ms(start_dt)
        else:
            if csv_path.exists():
                csv_path.unlink()
            start_ms = to_ms(start_dt)

        total = 0
        cursor = start_ms
        while cursor < end_ms:
            rows = fetch_klines(symbol, args.interval, cursor, end_ms, limit=1000)
            if not isinstance(rows, list) or len(rows) == 0:
                break
            append_rows(csv_path, rows)
            total += len(rows)
            cursor = int(rows[-1][0]) + 1
            time.sleep(args.sleep_ms / 1000)

        report["symbols"][symbol] = {
            "rows_written": total,
            "file": str(csv_path),
            "last_open_time": from_ms(cursor).isoformat() if cursor else None,
        }

    report["finished_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
