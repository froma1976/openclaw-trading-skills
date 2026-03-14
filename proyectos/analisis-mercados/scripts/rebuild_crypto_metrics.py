#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parent
PIPELINE = [
    "normalize_crypto_orders.py",
    "dataset_quality.py",
    "learning_daily.py",
    "learn_from_crypto_trades.py",
    "walkforward_eval.py",
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
    results = [run_step(name) for name in PIPELINE]
    ok = all(item["returncode"] == 0 for item in results)
    print(json.dumps({"ok": ok, "steps": results}, ensure_ascii=True, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
