#!/usr/bin/env python3
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
QUEUE = ROOT / "data" / "research_experiment_queue.json"
OUT_JSON = ROOT / "data" / "research_experiment_results.json"
OUT_MD = ROOT / "reports" / "research_experiment_results.md"
PY = r"C:/Windows/py.exe"


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_py(script: Path, timeout: int = 240):
    t0 = time.time()
    proc = subprocess.run([PY, "-3", str(script)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return {
        "ok": proc.returncode == 0,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "latency_s": round(time.time() - t0, 2),
        "returncode": proc.returncode,
    }


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def exec_lscanner(item: dict):
    run = run_py(ROOT / "scripts" / "source_ingest_free.py", timeout=300)
    snap = load_json(ROOT / "data" / "latest_snapshot_free.json", {})
    macro = snap.get("macro_regime", {}) if isinstance(snap, dict) else {}
    return {
        "experiment": item.get("name"),
        "target_module": item.get("target_module"),
        "status": "completed" if run["ok"] else "failed",
        "runner": "source_ingest_free.py",
        "metrics": {
            "macro_adj": macro.get("macro_adj"),
            "vix": macro.get("vix"),
            "dxy": macro.get("dxy"),
            "latency_s": run["latency_s"],
        },
        "notes": "Baseline automatica para evaluar si merece aumentar cadencia/frescura del bloque macro-liquidez.",
        "stdout": run["stdout"][:1200],
        "stderr": run["stderr"][:800],
    }


def exec_iwatcher(item: dict):
    run = run_py(ROOT / "scripts" / "source_ingest_free.py", timeout=300)
    snap = load_json(ROOT / "data" / "latest_snapshot_free.json", {})
    insider_map = snap.get("insider_map", {}) if isinstance(snap, dict) else {}
    buy_signals = sum(1 for _, row in insider_map.items() if isinstance(row, dict) and int(row.get("insider_buys", 0) or 0) > 0)
    max_buys = max([int((row or {}).get("insider_buys", 0) or 0) for row in insider_map.values()] or [0])
    return {
        "experiment": item.get("name"),
        "target_module": item.get("target_module"),
        "status": "completed" if run["ok"] else "failed",
        "runner": "source_ingest_free.py",
        "metrics": {
            "symbols_with_insider_buys": buy_signals,
            "max_insider_buys_per_symbol": max_buys,
            "latency_s": run["latency_s"],
        },
        "notes": "Baseline automatica del bloque insider para decidir si conviene invertir en feed mas rapido o limpieza de eventos.",
        "stdout": run["stdout"][:1200],
        "stderr": run["stderr"][:800],
    }


def exec_tanalyst(item: dict):
    run = run_py(ROOT / "scripts" / "source_ingest_free.py", timeout=300)
    snap = load_json(ROOT / "data" / "latest_snapshot_free.json", {})
    top = snap.get("top_opportunities", []) if isinstance(snap, dict) else []
    top5 = top[:5]
    ready = sum(1 for row in top if (row or {}).get("state") in {"READY", "TRIGGERED"})
    tech_scores = [float((row or {}).get("score_tech", 0) or 0) for row in top5]
    return {
        "experiment": item.get("name"),
        "target_module": item.get("target_module"),
        "status": "completed" if run["ok"] else "failed",
        "runner": "source_ingest_free.py",
        "metrics": {
            "top5_avg_score_tech": round(sum(tech_scores) / len(tech_scores), 3) if tech_scores else 0,
            "ready_or_triggered": ready,
            "latency_s": run["latency_s"],
        },
        "notes": "Baseline automatica del bloque tecnico antes de introducir feeds mas rapidos o nuevos indicadores.",
        "stdout": run["stdout"][:1200],
        "stderr": run["stderr"][:800],
    }


EXECUTORS = {
    "L-Scanner": exec_lscanner,
    "I-Watcher": exec_iwatcher,
    "T-Analyst": exec_tanalyst,
}


def build_markdown(payload: dict):
    lines = [
        "# Research experiment execution",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Items executed: {len(payload.get('results', []))}",
        "",
        "| Experiment | Module | Status | Metrics |",
        "|---|---|---|---|",
    ]
    for row in payload.get("results", []):
        metrics = ", ".join(f"{k}={v}" for k, v in (row.get("metrics") or {}).items())
        lines.append(f"| {row.get('experiment')} | {row.get('target_module')} | {row.get('status')} | {metrics} |")
    lines += ["", "## Notes"]
    for row in payload.get("results", []):
        lines.append(f"- {row.get('experiment')}: {row.get('notes')}")
    return "\n".join(lines)


def main():
    queue = load_json(QUEUE, {"items": []})
    items = queue.get("items", []) if isinstance(queue, dict) else []
    results = []
    for item in items[:3]:
        target = item.get("target_module")
        fn = EXECUTORS.get(target)
        if not fn:
            results.append({
                "experiment": item.get("name"),
                "target_module": target,
                "status": "skipped",
                "metrics": {},
                "notes": "No hay executor automatico para este modulo todavia.",
            })
            continue
        results.append(fn(item))
        item["status"] = results[-1]["status"]
        item["last_run_at"] = now_iso()

    payload = {"generated_at": now_iso(), "results": results}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(build_markdown(payload), encoding="utf-8")
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "results": len(results), "out_json": str(OUT_JSON), "out_md": str(OUT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
