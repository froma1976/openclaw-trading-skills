#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
REGISTRY = ROOT / "data" / "research_experiment_registry.jsonl"
OUT_JSON = ROOT / "data" / "research_memory.json"
OUT_MD = ROOT / "reports" / "research_memory.md"


def now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def main():
    rows = []
    if REGISTRY.exists():
        for line in REGISTRY.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    by_module = defaultdict(lambda: Counter())
    by_decision = Counter()
    taxonomy = defaultdict(list)
    last_promoted = []
    for row in rows:
        module = str(row.get("target_module") or "unknown")
        decision = str(row.get("decision") or "unknown")
        by_module[module][decision] += 1
        by_decision[decision] += 1
        taxonomy[module].append(str(row.get("experiment") or ""))
        if decision == "promote":
            last_promoted.append({
                "experiment": row.get("experiment"),
                "module": module,
                "logged_at": row.get("logged_at"),
                "rationale": row.get("rationale"),
            })

    out = {
        "generated_at": now_iso(),
        "totals": dict(by_decision),
        "by_module": {k: dict(v) for k, v in by_module.items()},
        "taxonomy": {k: sorted(set(v)) for k, v in taxonomy.items()},
        "last_promoted": last_promoted[-5:],
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Research memory",
        "",
        f"- Generated at: {out['generated_at']}",
        "",
        "## Totals",
    ]
    for k, v in out["totals"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## By module"]
    for k, v in out["by_module"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Last promoted"]
    for row in out["last_promoted"]:
        lines.append(f"- {row['experiment']} ({row['module']}): {row['rationale']}")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "rows": len(rows), "out_json": str(OUT_JSON), "out_md": str(OUT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
