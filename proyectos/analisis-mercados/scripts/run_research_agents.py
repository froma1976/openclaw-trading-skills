#!/usr/bin/env python3
import json
import re
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
CFG = ROOT / "config" / "research_agents.json"
OLLAMA = Path(r"C:/Users/Fernando/AppData/Local/Programs/Ollama/ollama.exe")
OUT_JSON = ROOT / "data" / "research_agents_latest.json"
OUT_MD = ROOT / "reports" / "research_agents_latest.md"
QUEUE_JSON = ROOT / "data" / "research_experiment_queue.json"

FILES_TO_SCAN = [
    ROOT / "PROJECT.md",
    ROOT / "config" / "risk.yaml",
    ROOT / "scripts" / "run_crypto_scalp_autopilot.py",
    ROOT / "scripts" / "source_ingest_crypto_free.py",
    ROOT / "scripts" / "walkforward_eval.py",
    ROOT / "scripts" / "learning_daily.py",
    ROOT / "data" / "learning_status.json",
]


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_cfg():
    return json.loads(CFG.read_text(encoding="utf-8")) if CFG.exists() else {
        "auditor_model": "phi4-mini:latest",
        "designer_model": "phi4-mini:latest",
        "judge_model": "phi4-mini:latest",
        "max_context_chars_per_file": 12000,
        "max_files": 12,
        "experiments_target": 12,
    }


def read_context(cfg: dict) -> str:
    limit = int(cfg.get("max_context_chars_per_file", 12000) or 12000)
    max_files = int(cfg.get("max_files", 12) or 12)
    chunks = []
    for path in FILES_TO_SCAN[:max_files]:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        chunks.append(f"\n### FILE: {path.relative_to(ROOT).as_posix()}\n{text[:limit]}\n")
    return "\n".join(chunks)


def extract_json(text: str):
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    for candidate in [text]:
        try:
            return json.loads(candidate)
        except Exception:
            pass
    matches = re.findall(r"\{[\s\S]*?\}\s*(?=\n```|$)", text)
    for m in matches:
        try:
            return json.loads(m)
        except Exception:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def salvage_designer_output(text: str):
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    improvements = []
    for m in re.finditer(r'"title"\s*:\s*"([^"]+)"[\s\S]*?"problem"\s*:\s*"([^"]+)"[\s\S]*?"proposal"\s*:\s*"([^"]+)"[\s\S]*?"priority"\s*:\s*"([^"]+)"', text):
        improvements.append({
            "title": m.group(1),
            "problem": m.group(2),
            "proposal": m.group(3),
            "priority": m.group(4),
        })

    experiments = []
    blocks = re.findall(r'\{[\s\S]*?"name"\s*:\s*"([^"]+)"[\s\S]*?"overfitting_risk"\s*:\s*(\d+)[\s\S]*?\}', text)
    for name, overfit in blocks:
        section = re.search(r'\{[\s\S]*?"name"\s*:\s*"%s"[\s\S]*?\}' % re.escape(name), text)
        chunk = section.group(0) if section else ""
        def pick(key, default=""):
            mm = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, chunk)
            return mm.group(1) if mm else default
        def pick_num(key, default=3):
            mm = re.search(r'"%s"\s*:\s*(\d+)' % key, chunk)
            return int(mm.group(1)) if mm else default
        def pick_list(key):
            mm = re.search(r'"%s"\s*:\s*\[([\s\S]*?)\]' % key, chunk)
            if not mm:
                return []
            return re.findall(r'"([^"]+)"', mm.group(1))
        experiments.append({
            "name": name,
            "hypothesis": pick("hypothesis"),
            "change": pick("change"),
            "backtest_plan": pick("backtest_plan"),
            "success_metrics": pick_list("success_metrics"),
            "new_signals": pick_list("new_signals"),
            "risk_notes": pick("risk_notes"),
            "implementation_effort": pick_num("implementation_effort"),
            "compute_cost": pick_num("compute_cost"),
            "expected_impact": pick_num("expected_impact"),
            "overfitting_risk": int(overfit),
        })

    architecture_changes = re.findall(r'"architecture_changes"\s*:\s*\[([\s\S]*?)\]', text)
    research_lines = re.findall(r'"research_lines"\s*:\s*\[([\s\S]*?)\]', text)
    return {
        "priority_improvements": improvements,
        "experiments": experiments,
        "architecture_changes": re.findall(r'"([^"]+)"', architecture_changes[0]) if architecture_changes else [],
        "research_lines": re.findall(r'"([^"]+)"', research_lines[0]) if research_lines else [],
        "raw_fallback": text[:6000],
    }


def run_ollama(model: str, prompt: str, timeout: int = 600):
    t0 = time.time()
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 1200},
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        out = (data.get("response") or "").strip()
        ok = bool(out)
    except Exception as exc:
        out = str(exc)
        ok = False
    dt = round(time.time() - t0, 2)
    return {"ok": ok, "latency_s": dt, "raw": out, "model": model}


def auditor_prompt(context: str) -> str:
    return f"""
Eres research-auditor, un auditor senior de sistemas cuantitativos.

Analiza el sistema REAL incluido en el contexto. No inventes archivos ni capacidades.
Debes basarte en evidencia explícita del contexto. Si no lo ves en el contexto, no lo afirmes.
Responde SOLO JSON valido con esta forma exacta:
{{
  "system_summary": ["..."],
  "existing_capabilities": ["..."],
  "weaknesses": [{{"area":"...","problem":"...","evidence":"...","impact":"high|medium|low"}}],
  "overfitting_risks": [{{"risk":"...","evidence":"...","severity":"high|medium|low"}}],
  "pipeline_bottlenecks": [{{"bottleneck":"...","why":"..."}}],
  "missing_research_lines": ["..."],
  "quick_wins": ["..."]
}}

Contexto del proyecto:
{context}
""".strip()


def designer_prompt(audit: dict, experiments_target: int) -> str:
    return f"""
Eres experiment-designer, investigador senior de trading cuantitativo.

Diseña {experiments_target} experimentos concretos, automatizables y específicos para ESTE sistema.
No repitas lo que ya existe salvo para corregir un fallo claro.
Evita propuestas genéricas como "usar machine learning" o "mejorar datos" sin aterrizarlas.
Cada experimento debe poder lanzarse como script/backtest dentro del proyecto en menos de 1 semana de trabajo.
Prioriza quick wins y mejoras testeables sobre ideas grandilocuentes.
Responde SOLO JSON valido con esta forma exacta:
{{
  "priority_improvements": [{{"title":"...","problem":"...","proposal":"...","priority":"high|medium|low"}}],
  "experiments": [
    {{
      "name":"...",
      "target_module":"script o modulo a tocar",
      "hypothesis":"...",
      "change":"...",
      "backtest_plan":"...",
      "automation_plan":"como meterlo en pipeline automatico",
      "success_metrics":["..."],
      "new_signals":["..."],
      "risk_notes":"...",
      "implementation_effort":1,
      "compute_cost":1,
      "expected_impact":1,
      "overfitting_risk":1
    }}
  ],
  "architecture_changes": ["..."],
  "research_lines": ["..."]
}}

Diagnostico:
{json.dumps(audit, ensure_ascii=False)}
""".strip()


def judge_prompt(design: dict) -> str:
    return f"""
Eres experiment-judge. No inventes experimentos nuevos. Evalua solo los propuestos.
Penaliza propuestas genéricas, difíciles de backtestear o que requieran infraestructura externa no presente.
Para cada experimento, asigna del 1 al 5:
- robustness
- automation_fit
- data_leakage_risk_inverse
- implementation_clarity

Responde SOLO JSON valido con esta forma exacta:
{{
  "judgements": [
    {{
      "name":"...",
      "robustness":1,
      "automation_fit":1,
      "data_leakage_risk_inverse":1,
      "implementation_clarity":1,
      "judge_note":"..."
    }}
  ],
  "top_5": ["..."],
  "discard_or_delay": ["..."]
}}

Experimentos:
{json.dumps(design.get('experiments', []), ensure_ascii=False)}
""".strip()


def deterministic_score(exp: dict, judge_row: dict):
    expected_impact = float(exp.get("expected_impact", 3) or 3)
    effort = float(exp.get("implementation_effort", 3) or 3)
    compute_cost = float(exp.get("compute_cost", 3) or 3)
    overfit_risk = float(exp.get("overfitting_risk", 3) or 3)
    robustness = float(judge_row.get("robustness", 3) or 3)
    automation_fit = float(judge_row.get("automation_fit", 3) or 3)
    leakage_inverse = float(judge_row.get("data_leakage_risk_inverse", 3) or 3)
    clarity = float(judge_row.get("implementation_clarity", 3) or 3)
    return round(
        0.26 * expected_impact
        + 0.18 * robustness
        + 0.16 * automation_fit
        + 0.12 * leakage_inverse
        + 0.10 * clarity
        + 0.10 * (6 - effort)
        + 0.08 * (6 - compute_cost)
        + 0.10 * (6 - overfit_risk),
        3,
    )


def build_markdown(payload: dict) -> str:
    lines = [
        "# Research agents report",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Auditor model: {payload['models']['auditor']}",
        f"- Designer model: {payload['models']['designer']}",
        f"- Judge model: {payload['models']['judge']}",
        "",
        "## Top priorities",
    ]
    for item in (payload.get("designer") or {}).get("priority_improvements", [])[:8]:
        lines.append(f"- [{item.get('priority','medium')}] {item.get('title')}: {item.get('proposal')}")
    lines += ["", "## Ranked experiments", "| Rank | Experiment | Score | Why |", "|---|---|---:|---|"]
    for i, row in enumerate(payload.get("ranked_experiments", []), start=1):
        lines.append(f"| {i} | {row['name']} | {row['priority_score']:.3f} | {row.get('judge_note','-')} |")
    lines += ["", "## Execution queue"]
    for row in payload.get("execution_queue", []):
        lines.append(f"- [{row.get('status','pending')}] {row.get('name')}: {row.get('target_module')} -> {row.get('automation_plan')}")
    lines += ["", "## Architecture changes"]
    for row in (payload.get("designer") or {}).get("architecture_changes", []):
        lines.append(f"- {row}")
    lines += ["", "## Research lines"]
    for row in (payload.get("designer") or {}).get("research_lines", []):
        lines.append(f"- {row}")
    return "\n".join(lines)


def main():
    cfg = load_cfg()
    context = read_context(cfg)

    auditor_run = run_ollama(cfg["auditor_model"], auditor_prompt(context))
    audit = extract_json(auditor_run["raw"]) or {
        "system_summary": [],
        "existing_capabilities": [],
        "weaknesses": [],
        "overfitting_risks": [],
        "pipeline_bottlenecks": [],
        "missing_research_lines": [],
        "quick_wins": [],
        "raw_fallback": auditor_run["raw"][:4000],
    }

    designer_run = run_ollama(cfg["designer_model"], designer_prompt(audit, int(cfg.get("experiments_target", 12) or 12)))
    design = extract_json(designer_run["raw"]) or salvage_designer_output(designer_run["raw"]) or {
        "priority_improvements": [],
        "experiments": [],
        "architecture_changes": [],
        "research_lines": [],
        "raw_fallback": designer_run["raw"][:6000],
    }

    judge_run = run_ollama(cfg["judge_model"], judge_prompt(design))
    judge = extract_json(judge_run["raw"]) or {"judgements": [], "top_5": [], "discard_or_delay": [], "raw_fallback": judge_run["raw"][:4000]}

    judge_map = {row.get("name"): row for row in (judge.get("judgements") or [])}
    ranked = []
    for exp in (design.get("experiments") or []):
        j = judge_map.get(exp.get("name"), {})
        ranked.append({
            **exp,
            **{k: v for k, v in j.items() if k != "name"},
            "priority_score": deterministic_score(exp, j),
        })
    ranked.sort(key=lambda x: (-x["priority_score"], -float(x.get("expected_impact", 0) or 0), x.get("name", "")))

    execution_queue = []
    for idx, exp in enumerate(ranked[:3], start=1):
        execution_queue.append({
            "rank": idx,
            "name": exp.get("name"),
            "target_module": exp.get("target_module", "research/manual-review"),
            "automation_plan": exp.get("automation_plan", exp.get("backtest_plan", "manual")),
            "status": "pending",
            "priority_score": exp.get("priority_score"),
            "created_at": now_iso(),
        })

    payload = {
        "generated_at": now_iso(),
        "models": {
            "auditor": cfg["auditor_model"],
            "designer": cfg["designer_model"],
            "judge": cfg["judge_model"],
        },
        "audit": audit,
        "designer": design,
        "judge": judge,
        "ranked_experiments": ranked,
        "execution_queue": execution_queue,
        "runtime": {
            "auditor": auditor_run["latency_s"],
            "designer": designer_run["latency_s"],
            "judge": judge_run["latency_s"],
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(build_markdown(payload), encoding="utf-8")
    QUEUE_JSON.write_text(json.dumps({"generated_at": now_iso(), "items": execution_queue}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out_json": str(OUT_JSON), "out_md": str(OUT_MD), "experiments": len(ranked)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
