#!/usr/bin/env python3
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
CFG = ROOT / "AGENTS_RUNTIME_LOCAL.json"
OUT = ROOT / "data" / "multiagent_health.json"


def run_ollama(model: str, prompt: str, timeout=90):
    cmd = [r"C:/Users/Fernando/AppData/Local/Programs/Ollama/ollama.exe", "run", model.replace("ollama/", ""), prompt]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    dt = round(time.time() - t0, 2)
    ok = p.returncode == 0 and p.stdout.strip() != ""
    return ok, dt, (p.stdout or p.stderr or "").strip()[:300]


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    rows = []
    for a in cfg.get("agents", []):
        model = a.get("model", "deterministic")
        agent_id = a.get("id")
        if model == "deterministic":
            rows.append({"agent": agent_id, "model": model, "ok": True, "latency_s": 0, "note": "Determinista (sin LLM)"})
            continue
        prompt = f"Responde solo OK_{agent_id.upper().replace('-','_')}"
        ok, dt, out = run_ollama(model, prompt)
        rows.append({"agent": agent_id, "model": model, "ok": ok, "latency_s": dt, "note": out})

    # fallback automático para agentes LLM que fallen
    changed = False
    for r in rows:
        if (not r["ok"]) and r["model"].startswith("ollama/"):
            r["model"] = "ollama/phi4-mini"
            r["fallback_applied"] = True
            changed = True

    if changed:
        for a in cfg.get("agents", []):
            for r in rows:
                if a.get("id") == r["agent"] and r.get("fallback_applied"):
                    a["model"] = r["model"]
        CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"results": rows, "changed": changed}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {OUT}")


if __name__ == "__main__":
    main()
