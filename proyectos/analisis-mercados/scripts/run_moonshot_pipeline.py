#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parent
PIPELINE = [
    "run_moonshot_stock_ingest.py",
    "run_moonshot_crypto_ingest.py",
    "run_moonshot_engine.py",
    "build_openclaw_snapshot.py",
]


def run_step(name: str):
    script = BASE / name
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {
        "script": name,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main():
    steps = [run_step(name) for name in PIPELINE]
    ok = all(step["returncode"] == 0 for step in steps)
    print(json.dumps({"ok": ok, "steps": steps}, ensure_ascii=True, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
