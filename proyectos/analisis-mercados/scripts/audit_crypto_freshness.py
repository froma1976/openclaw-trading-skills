#!/usr/bin/env python3
import json
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
DATA = BASE / "data"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

SNAP = DATA / "crypto_snapshot_free.json"
ORD = DATA / "crypto_orders_sim.json"
OUT = DATA / "crypto_watchdog_status.json"
ALERT = LOGS / "crypto_watchdog_alerts.log"


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(s: str):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


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
                # Warning only if all active look frozen
                if zeros == len(active):
                    issues.append("all_active_zero_like")
        except Exception as e:
            issues.append(f"orders_read_error:{e}")

    out["issues"] = issues
    out["ok"] = len(issues) == 0
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    if issues:
        with ALERT.open("a", encoding="utf-8") as f:
            f.write(f"[{out['ts']}] ALERT: {', '.join(issues)}\n")

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
