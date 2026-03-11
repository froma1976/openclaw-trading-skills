#!/usr/bin/env python3
import json, os, urllib.parse, urllib.request
from datetime import datetime, UTC
from pathlib import Path

ORD = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados/data/crypto_orders_sim.json")
ENV = Path("C:/Users/Fernando/.openclaw/.env")


def load_env():
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k,v = s.split('=',1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace('+00:00','Z')


def main():
    load_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT_ID")
    if not token or not chat:
        print("SKIP: missing telegram env")
        return

    d = {"active":[],"completed":[],"daily":{},"portfolio":{}}
    if ORD.exists():
        d = json.loads(ORD.read_text(encoding="utf-8"))
    active = d.get("active",[]) or []
    completed = d.get("completed",[]) or []
    daily = d.get("daily",{}) or {}
    p = d.get("portfolio",{}) or {}

    msg = (
        f"🪙 Crypto bot resumen ({now_iso()})\n"
        f"Estado: {'PAUSADO' if daily.get('paused') else 'ACTIVO'}\n"
        f"Modo: {daily.get('mode','normal')} | Motivo: {daily.get('mode_reason') or daily.get('pause_reason') or '-'}\n"
        f"Activas: {len(active)} | Cerradas: {len(completed)}\n"
        f"Trades hoy: {daily.get('trades',0)} | Racha pérdidas: {daily.get('loss_streak',0)}\n"
        f"Cash: {p.get('cash_usd',0)} | Equity: {p.get('equity_usd',0)}"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        _ = r.read().decode("utf-8", errors="ignore")
    print("OK sent")


if __name__ == "__main__":
    main()
