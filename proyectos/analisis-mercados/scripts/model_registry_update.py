#!/usr/bin/env python3
"""
Actualiza el registry de modelos LSTM con champion gating.
Solo promueve un modelo si su val_mse mejora vs el champion actual.
"""
import json
from pathlib import Path
from datetime import datetime, UTC

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
REG = BASE / "models" / "registry.json"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def main():
    reg = {"version": 1, "symbols": {}}
    if REG.exists():
        try:
            reg = json.loads(REG.read_text(encoding="utf-8"))
        except Exception:
            pass

    results = []
    for sym in SYMBOLS:
        meta_path = BASE / "models" / f"lstm_{sym}_meta.json"
        model_path = BASE / "models" / f"lstm_{sym}.pt"
        if not (meta_path.exists() and model_path.exists()):
            continue

        m = json.loads(meta_path.read_text(encoding="utf-8"))
        mse = float(m.get("val_mse") or 999)
        cur = reg.get("symbols", {}).get(sym, {})
        best = float(cur.get("best_val_mse", 999))
        hist = cur.get("history", [])

        # Champion gating: solo promover si mejora
        champion_action = "PROMOTED" if mse <= best else "REJECTED"
        champion = cur.get("champion_model")

        hist.append({
            "at": datetime.now(UTC).isoformat(),
            "val_mse": mse,
            "champion_action": champion_action,
            "model": str(model_path),
            "meta": str(meta_path),
        })

        if champion_action == "PROMOTED":
            best = mse
            champion = str(model_path)

        reg.setdefault("symbols", {})[sym] = {
            "best_val_mse": best,
            "champion_model": champion,
            "history": hist[-30:],
        }
        results.append({"symbol": sym, "val_mse": mse, "action": champion_action})

    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "registry": str(REG), "results": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
