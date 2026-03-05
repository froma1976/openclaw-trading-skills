#!/usr/bin/env python3
import os
import json
import hmac
import hashlib
import time
from urllib import parse, request
from pathlib import Path

ENV = Path("C:/Users/Fernando/.openclaw/.env")


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


def main():
    load_env(ENV)
    key = os.getenv("BINANCE_API_KEY", "")
    sec = os.getenv("BINANCE_API_SECRET", "")
    if not key or not sec:
        print(json.dumps({"ok": False, "error": "missing BINANCE_API_KEY/BINANCE_API_SECRET"}, ensure_ascii=False))
        return

    ts = int(time.time() * 1000)
    qs = parse.urlencode({"timestamp": ts, "recvWindow": 5000})
    sig = hmac.new(sec.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com/api/v3/account?{qs}&signature={sig}"
    req = request.Request(url, headers={"X-MBX-APIKEY": key, "User-Agent": "openclaw-readonly-check/1.0"})
    try:
        with request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return

    print(json.dumps({
        "ok": True,
        "canTrade": payload.get("canTrade"),
        "makerCommission": payload.get("makerCommission"),
        "takerCommission": payload.get("takerCommission")
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
