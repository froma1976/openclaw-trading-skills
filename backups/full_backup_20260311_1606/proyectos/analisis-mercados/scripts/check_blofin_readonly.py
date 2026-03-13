#!/usr/bin/env python3
import os
import json
import base64
import hmac
import hashlib
import uuid
from datetime import datetime, UTC
from urllib import request
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


def sign(secret: str, method: str, path_q: str, ts: str, nonce: str, body: str = ""):
    prehash = f"{path_q}{method.upper()}{ts}{nonce}{body}"
    hex_sig = hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).hexdigest().encode()
    return base64.b64encode(hex_sig).decode()


def main():
    load_env(ENV)
    key = os.getenv("BLOFIN_API_KEY", "")
    sec = os.getenv("BLOFIN_API_SECRET", "")
    pph = os.getenv("BLOFIN_API_PASSPHRASE", "")

    if not key or not sec:
        print(json.dumps({"ok": False, "stage": "config", "error": "missing BLOFIN_API_KEY/BLOFIN_API_SECRET"}, ensure_ascii=False))
        return
    if not pph:
        print(json.dumps({"ok": False, "stage": "config", "error": "missing BLOFIN_API_PASSPHRASE (required by Blofin private API)"}, ensure_ascii=False))
        return

    path_q = "/api/v1/asset/balances?accountType=futures"
    url = "https://openapi.blofin.com" + path_q
    ts = str(int(datetime.now(UTC).timestamp() * 1000))
    nonce = str(uuid.uuid4())
    sig = sign(sec, "GET", path_q, ts, nonce, "")

    headers = {
        "ACCESS-KEY": key,
        "ACCESS-SIGN": sig,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-NONCE": nonce,
        "ACCESS-PASSPHRASE": pph,
        "Content-Type": "application/json",
        "User-Agent": "openclaw-readonly-check/1.0",
    }

    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(json.dumps({"ok": False, "stage": "request", "error": str(e)}, ensure_ascii=False))
        return

    # Do not print full balances; only connectivity proof
    code = payload.get("code") if isinstance(payload, dict) else None
    msg = payload.get("msg") if isinstance(payload, dict) else ""
    print(json.dumps({"ok": str(code) == "0", "stage": "request", "code": code, "msg": msg}, ensure_ascii=False))


if __name__ == "__main__":
    main()
