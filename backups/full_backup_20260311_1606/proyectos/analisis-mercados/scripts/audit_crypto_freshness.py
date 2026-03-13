#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
DATA = BASE / "data"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

SNAP = DATA / "crypto_snapshot_free.json"
ORD = DATA / "crypto_orders_sim.json"
OUT = DATA / "crypto_watchdog_status.json"
STATE = DATA / "crypto_watchdog_state.json"
ALERT = LOGS / "crypto_watchdog_alerts.log"
ENV = Path("C:/Users/Fernando/.openclaw/.env")


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(s: str):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_env():
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def send_telegram(msg: str):
    load_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT_ID")
    if not token or not chat:
        return False, "missing telegram env"
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        body = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            _ = r.read().decode("utf-8", errors="ignore")
        return True, "sent"
    except Exception as e:
        return False, str(e)


def main():
    issues = []
    out = {"ts": now_iso(), "ok": True, "checks": {}}

    # Check snapshot freshness
    if not SNAP.exists():
        issues.append("snapshot_missing")
    else:
        try:
            snap = json.loads(SNAP.read_text(encoding="utf-8"))
            gen = snap.get("generated_at")
            if not gen:
                issues.append("snapshot_no_generated_at")
            else:
                age_sec = int((datetime.now(UTC) - parse_iso(gen)).total_seconds())
                out["checks"]["snapshot_age_sec"] = age_sec
                if age_sec > 8 * 60:
                    issues.append(f"snapshot_stale_{age_sec}s")
        except Exception as e:
            issues.append(f"snapshot_read_error:{e}")

    # Check orders freshness and movement hints
    if not ORD.exists():
        issues.append("orders_missing")
    else:
        try:
            orders = json.loads(ORD.read_text(encoding="utf-8"))
            active = orders.get("active", []) or []
            out["checks"]["active_count"] = len(active)
            if active:
                zeros = 0
                for o in active:
                    pct = o.get("pct_move")
                    pnl = o.get("pnl_usd_est")
                    if (pct in (0, 0.0, "0", "0.0", None)) and (pnl in (0, 0.0, "0", "0.0", None)):
                        zeros += 1
                out["checks"]["active_zero_like"] = zeros
                if zeros == len(active) and zeros >= 3:
                    issues.append("all_active_zero_like")
        except Exception as e:
            issues.append(f"orders_read_error:{e}")

    out["issues"] = issues
    out["ok"] = len(issues) == 0
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # Alerting logic (avoid spam): send when status changes OK->ALERT or new issue fingerprint
    prev = {}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    fingerprint = "|".join(sorted(issues))
    prev_fingerprint = prev.get("fingerprint", "")
    prev_ok = bool(prev.get("ok", True))

    should_alert = False
    if not out["ok"] and (prev_ok or fingerprint != prev_fingerprint):
        should_alert = True

    alert_sent = False
    alert_info = ""
    if issues:
        with ALERT.open("a", encoding="utf-8") as f:
            f.write(f"[{out['ts']}] ALERT: {', '.join(issues)}\n")

    if should_alert:
        msg = (
            f"🚨 Crypto watchdog ALERT\n"
            f"Hora: {out['ts']}\n"
            f"Problemas: {', '.join(issues)}\n"
            f"Checks: {json.dumps(out.get('checks', {}), ensure_ascii=False)}"
        )
        alert_sent, alert_info = send_telegram(msg)

    state = {
        "ts": out["ts"],
        "ok": out["ok"],
        "fingerprint": fingerprint,
        "last_alert_sent": alert_sent,
        "last_alert_info": alert_info,
    }
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"watchdog": out, "alert_sent": alert_sent, "alert_info": alert_info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
