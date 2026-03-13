#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, UTC

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
REG = BASE / "models" / "registry.json"


def main():
    reg = {"version": 1, "symbols": {}}
    if REG.exists():
        reg = json.loads(REG.read_text(encoding="utf-8"))

    for sym in ["BTCUSDT", "SOLUSDT"]:
        meta = BASE / "models" / f"lstm_{sym}_meta.json"
        model = BASE / "models" / f"lstm_{sym}.pt"
        if not (meta.exists() and model.exists()):
            continue
        m = json.loads(meta.read_text(encoding="utf-8"))
        mse = float(m.get("val_mse") or 999)
        cur = reg["symbols"].get(sym, {})
        best = float(cur.get("best_val_mse", 999))
        hist = cur.get("history", [])
        hist.append({
            "at": datetime.now(UTC).isoformat(),
            "val_mse": mse,
            "model": str(model),
            "meta": str(meta)
        })
        champion = cur.get("champion_model")
        if mse <= best:
            best = mse
            champion = str(model)
        reg["symbols"][sym] = {
            "best_val_mse": best,
            "champion_model": champion,
            "history": hist[-30:]
        }

    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "registry": str(REG)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
