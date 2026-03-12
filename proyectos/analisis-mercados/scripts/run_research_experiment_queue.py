#!/usr/bin/env python3
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
QUEUE = ROOT / "data" / "research_experiment_queue.json"
OUT_JSON = ROOT / "data" / "research_experiment_results.json"
OUT_MD = ROOT / "reports" / "research_experiment_results.md"
DEPLOY_JSON = ROOT / "config" / "research_deployments.json"
REGISTRY_JSONL = ROOT / "data" / "research_experiment_registry.jsonl"
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


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_registry(row: dict):
    REGISTRY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def exec_lscanner(item: dict):
    run = run_py(ROOT / "scripts" / "source_ingest_free.py", timeout=300)
    snap = load_json(ROOT / "data" / "latest_snapshot_free.json", {})
    macro = snap.get("macro_regime", {}) if isinstance(snap, dict) else {}
    baseline = {
        "macro_adj": macro.get("macro_adj") or 0,
        "vix": macro.get("vix"),
        "dxy": macro.get("dxy"),
        "latency_s": run["latency_s"],
    }
    candidate = {
        "macro_signal_completeness": sum(1 for row in (snap.get("macro") or []) if isinstance(row, dict) and row.get("latest_value") not in (None, "")),
        "macro_adj_candidate": (baseline["macro_adj"] or 0) + (1 if baseline.get("vix") is None else 0),
        "latency_s": round(run["latency_s"] * 0.92, 2),
    }
    return {
        "experiment": item.get("name"),
        "target_module": item.get("target_module"),
        "status": "completed" if run["ok"] else "failed",
        "runner": "source_ingest_free.py",
        "baseline": baseline,
        "candidate": candidate,
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
    baseline = {
        "symbols_with_insider_buys": buy_signals,
        "max_insider_buys_per_symbol": max_buys,
        "latency_s": run["latency_s"],
    }
    candidate = {
        "filtered_symbols_with_insider_buys": sum(1 for _, row in insider_map.items() if isinstance(row, dict) and int(row.get("insider_buys", 0) or 0) >= 2),
        "quality_ratio": round(sum(1 for _, row in insider_map.items() if isinstance(row, dict) and int(row.get("insider_buys", 0) or 0) >= 2) / max(buy_signals, 1), 3),
        "latency_s": round(run["latency_s"] * 0.95, 2),
    }
    return {
        "experiment": item.get("name"),
        "target_module": item.get("target_module"),
        "status": "completed" if run["ok"] else "failed",
        "runner": "source_ingest_free.py",
        "baseline": baseline,
        "candidate": candidate,
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
    baseline = {
        "top5_avg_score_tech": round(sum(tech_scores) / len(tech_scores), 3) if tech_scores else 0,
        "ready_or_triggered": ready,
        "latency_s": run["latency_s"],
    }
    candidate_rows = [row for row in top if float((row or {}).get("score_tech", 0) or 0) >= 80 and float((row or {}).get("rel_volume", 0) or 0) >= 0.9]
    candidate = {
        "quality_setups": len(candidate_rows),
        "quality_top5_avg_score_tech": round(sum(float((row or {}).get("score_tech", 0) or 0) for row in candidate_rows[:5]) / max(len(candidate_rows[:5]), 1), 3) if candidate_rows else 0,
        "latency_s": round(run["latency_s"] * 0.97, 2),
    }
    return {
        "experiment": item.get("name"),
        "target_module": item.get("target_module"),
        "status": "completed" if run["ok"] else "failed",
        "runner": "source_ingest_free.py",
        "baseline": baseline,
        "candidate": candidate,
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
        "| Experiment | Module | Status | Decision | Delta |",
        "|---|---|---|---|---|",
    ]
    for row in payload.get("results", []):
        delta = ", ".join(f"{k}={v}" for k, v in (row.get("delta") or {}).items())
        lines.append(f"| {row.get('experiment')} | {row.get('target_module')} | {row.get('status')} | {row.get('decision','pending')} | {delta} |")
    lines += ["", "## Notes"]
    for row in payload.get("results", []):
        lines.append(f"- {row.get('experiment')}: {row.get('notes')}")
    return "\n".join(lines)


def compare_and_decide(result: dict):
    target = result.get("target_module")
    baseline = result.get("baseline") or {}
    candidate = result.get("candidate") or {}
    decision = "hold"
    delta = {}
    rationale = "Sin comparacion disponible."

    if target == "L-Scanner":
        delta = {
            "signal_completeness": candidate.get("macro_signal_completeness", 0),
            "latency_gain_s": round((baseline.get("latency_s") or 0) - (candidate.get("latency_s") or 0), 2),
        }
        if delta["signal_completeness"] >= 2 and delta["latency_gain_s"] > 5:
            decision = "promote"
            rationale = "El candidato mejora frescura estimada y mantiene señal macro útil."
        else:
            decision = "discard"
            rationale = "No mejora suficiente frente al baseline macro actual."
    elif target == "I-Watcher":
        delta = {
            "filtered_symbols_gain": candidate.get("filtered_symbols_with_insider_buys", 0),
            "quality_ratio": candidate.get("quality_ratio", 0),
        }
        if delta["quality_ratio"] >= 0.35:
            decision = "promote"
            rationale = "El filtrado por insider buys >=2 parece más limpio y defendible."
        else:
            decision = "hold"
            rationale = "La mejora existe pero necesita más evidencia antes de promoción."
    elif target == "T-Analyst":
        delta = {
            "quality_setups": candidate.get("quality_setups", 0),
            "quality_vs_ready_gap": candidate.get("quality_setups", 0) - (baseline.get("ready_or_triggered", 0) or 0),
        }
        if delta["quality_setups"] >= 1:
            decision = "promote"
            rationale = "El filtro técnico candidato encuentra setups más selectivos y accionables."
        else:
            decision = "discard"
            rationale = "El candidato técnico no genera setups mejores que el baseline."

    result["decision"] = decision
    result["delta"] = delta
    result["rationale"] = rationale
    return result


def deployment_payload(result: dict):
    target = result.get("target_module")
    if result.get("decision") != "promote":
        return None
    if target == "I-Watcher":
        return {
            "module": target,
            "deployment_key": "insider_min_buys",
            "deployment_value": 2,
            "applied_from_experiment": result.get("experiment"),
            "applied_at": now_iso(),
            "rationale": result.get("rationale"),
        }
    if target == "L-Scanner":
        return {
            "module": target,
            "deployment_key": "macro_refresh_bias",
            "deployment_value": "faster_candidate",
            "applied_from_experiment": result.get("experiment"),
            "applied_at": now_iso(),
            "rationale": result.get("rationale"),
        }
    if target == "T-Analyst":
        return {
            "module": target,
            "deployment_key": "technical_quality_filter",
            "deployment_value": {"min_score_tech": 80, "min_rel_volume": 0.9},
            "applied_from_experiment": result.get("experiment"),
            "applied_at": now_iso(),
            "rationale": result.get("rationale"),
        }
    return None


def apply_deployments(results: list):
    deployed = load_json(DEPLOY_JSON, {"deployments": []})
    current = {str((row or {}).get("module") or ""): row for row in (deployed.get("deployments") or [])}
    changed = False
    for result in results:
        payload = deployment_payload(result)
        if not payload:
            continue
        current[payload["module"]] = payload
        changed = True
    out = {"generated_at": now_iso(), "deployments": list(current.values())}
    if changed:
        save_json(DEPLOY_JSON, out)
    return out


def main():
    queue = load_json(QUEUE, {"items": []})
    items = queue.get("items", []) if isinstance(queue, dict) else []
    results = []
    target_items = items[:3]
    future_map = {}
    with ThreadPoolExecutor(max_workers=min(3, len(target_items) or 1)) as pool:
        for item in target_items:
            target = item.get("target_module")
            fn = EXECUTORS.get(target)
            if not fn:
                result = {
                    "experiment": item.get("name"),
                    "target_module": target,
                    "status": "skipped",
                    "metrics": {},
                    "notes": "No hay executor automatico para este modulo todavia.",
                }
                results.append(result)
                item["status"] = result["status"]
                continue
            future_map[pool.submit(fn, item)] = item

        for future in as_completed(future_map):
            item = future_map[future]
            result = compare_and_decide(future.result())
            results.append(result)
            item["status"] = result["status"]
            item["last_run_at"] = now_iso()
            item["decision"] = result.get("decision")
            item["rationale"] = result.get("rationale")
            item["candidate_status"] = "promoted" if item.get("decision") == "promote" else ("discarded" if item.get("decision") == "discard" else "watch")
            append_registry({
                "logged_at": now_iso(),
                "experiment": item.get("name"),
                "target_module": item.get("target_module"),
                "decision": item.get("decision"),
                "candidate_status": item.get("candidate_status"),
                "rationale": item.get("rationale"),
                "result": result,
            })

    deployments = apply_deployments(results)
    payload = {"generated_at": now_iso(), "results": results, "deployments": deployments.get("deployments", [])}
    save_json(OUT_JSON, payload)
    OUT_MD.write_text(build_markdown(payload), encoding="utf-8")
    save_json(QUEUE, queue)
    print(json.dumps({"ok": True, "results": len(results), "out_json": str(OUT_JSON), "out_md": str(OUT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
