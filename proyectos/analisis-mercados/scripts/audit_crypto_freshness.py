#!/usr/bin/env python3
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
LOG = BASE / "logs" / "universe_maintenance.log"
OUT = BASE / "logs" / "crypto_watchdog.log"
MAX_AGE_MIN = 330
TASK = "\\OpenClaw-Universe-Maintenance-4h"
PRICE_WAREHOUSE = Path("C:/Users/Fernando/.openclaw/workspace/memory/price_warehouse.csv")
COLLECTOR_MAX_AGE_MIN = 25
COLLECTOR_TASK = "\\OpenClaw_Crypto_Collector"


def now_utc():
    return datetime.now(UTC)


def append(message: str):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    stamp = now_utc().isoformat(timespec="seconds").replace("+00:00", "Z")
    with OUT.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {message}\n")


def age_minutes(path: Path):
    if not path.exists():
        return None
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return int((now_utc() - modified).total_seconds() // 60)


def run_task(task_name: str):
    proc = subprocess.run(
        ["schtasks", "/Run", "/TN", task_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "returncode": proc.returncode,
    }


def main():
    age = age_minutes(LOG)
    status = {
        "as_of": now_utc().isoformat(timespec="seconds").replace("+00:00", "Z"),
        "log_exists": LOG.exists(),
        "log_age_min": age,
        "threshold_min": MAX_AGE_MIN,
        "restarted": False,
    }

    if age is None:
        append("universe_maintenance.log missing -> relanzando tarea")
        res = run_task(TASK)
        status["restarted"] = True
        status["task_run"] = res
    elif age > MAX_AGE_MIN:
        append(f"universe_maintenance stale ({age} min) -> relanzando tarea")
        res = run_task(TASK)
        status["restarted"] = True
        status["task_run"] = res
    else:
        append(f"ok universe_maintenance fresh ({age} min)")

    collector_age = age_minutes(PRICE_WAREHOUSE)
    status["collector"] = {
        "warehouse_exists": PRICE_WAREHOUSE.exists(),
        "warehouse_age_min": collector_age,
        "threshold_min": COLLECTOR_MAX_AGE_MIN,
        "restarted": False,
    }
    if collector_age is None:
        append("price_warehouse.csv missing -> relanzando collector")
        res = run_task(COLLECTOR_TASK)
        status["collector"]["restarted"] = True
        status["collector"]["task_run"] = res
    elif collector_age > COLLECTOR_MAX_AGE_MIN:
        append(f"collector stale ({collector_age} min) -> relanzando collector")
        res = run_task(COLLECTOR_TASK)
        status["collector"]["restarted"] = True
        status["collector"]["task_run"] = res
    else:
        append(f"ok collector fresh ({collector_age} min)")

    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
