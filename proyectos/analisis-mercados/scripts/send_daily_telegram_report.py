#!/usr/bin/env python3
import os
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ENV = Path("C:/Users/Fernando/.openclaw/.env")
REPORT = BASE / "data" / "daily_report_latest.txt"


def load_env():
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT_ID")
    if not token or not chat:
        print("SKIP: missing telegram env")
        return
    if not REPORT.exists():
        print("SKIP: missing daily report")
        return
    msg = REPORT.read_text(encoding="utf-8", errors="ignore").strip()
    if not msg:
        print("SKIP: empty daily report")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        _ = r.read().decode("utf-8", errors="ignore")
    print("OK sent daily report")


if __name__ == "__main__":
    main()
