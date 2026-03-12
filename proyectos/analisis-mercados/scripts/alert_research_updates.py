#!/usr/bin/env python3
import json, os, urllib.parse, urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
QUEUE = ROOT / "data" / "research_experiment_queue.json"
STATE = ROOT / "data" / "research_alert_state.json"
ENV = Path(r"C:/Users/Fernando/.openclaw/.env")


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_env():
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def send(msg: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT_ID")
    if not token or not chat:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        _ = r.read()
    return True


def main():
    load_env()
    queue = load_json(QUEUE, {"items": []})
    state = load_json(STATE, {"seen": []})
    seen = set(state.get("seen", []))
    new_seen = set(seen)
    alerts = []
    for item in queue.get("items", []):
        key = f"{item.get('name')}|{item.get('decision')}|{item.get('last_run_at')}"
        if key in seen:
            continue
        if item.get("decision") in {"promote", "discard"}:
            alerts.append(item)
        new_seen.add(key)
    if alerts:
        msg = [f"Research updates {now_iso()}"]
        for item in alerts[:8]:
            msg.append(f"- {item.get('target_module')}: {item.get('name')} -> {item.get('decision')} ({item.get('rationale')})")
        send("\n".join(msg))
    STATE.write_text(json.dumps({"seen": sorted(new_seen)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "alerts": len(alerts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
