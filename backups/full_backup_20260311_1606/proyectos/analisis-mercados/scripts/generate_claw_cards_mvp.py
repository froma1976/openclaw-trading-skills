#!/usr/bin/env python3
import json
from datetime import datetime, UTC
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SNAP = BASE / "data" / "latest_snapshot_free.json"
OUT_DIR = BASE / "claw_cards"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def now_tag():
    return datetime.now(UTC).strftime("%Y%m%d_%H%M")


def mk_card(o: dict) -> str:
    t = o.get("ticker", "N/A")
    score = o.get("score", 0)
    ch5 = o.get("chg_5d_pct")
    ch20 = o.get("chg_20d_pct")
    reasons = ", ".join(o.get("reasons", []) or [])

    setup = f"Momentum/tendencia favorable en {t}" if score >= 60 else f"Setup en vigilancia para {t}"
    catalyst = "Confirmar continuidad de flujo + ruptura con volumen en sesión USA"
    timing = f"Score {score}, 5D={ch5}, 20D={ch20}"
    invalid = "Cierre diario por debajo de EMA20 o pérdida de soporte reciente"

    return f"""# CLAW CARD — {t}

- **Ticker / Mercado / Sector:** {t} / USA / NASDAQ
- **Setup (1 frase):** {setup}
- **Catalizador (qué + cuándo):** {catalyst} (próximas 1-2 sesiones)
- **Por qué ahora (timing):** {timing}
- **Confirmaciones (3 señales medibles):**
  1. Score cuantitativo >= 60
  2. 20D% positivo
  3. Volumen relativo > 1.2x en ruptura
- **Riesgos (top 3):**
  1. Falso breakout
  2. Giro macro (yields/DXY)
  3. Noticias negativas de sector
- **Invalidación (nivel/condición):** {invalid}
- **Plan de ejecución:**
  - Entrada: ruptura de máximo reciente con confirmación de volumen
  - Objetivo conservador: +4% a +6%
  - Objetivo agresivo: +8% a +12%
  - Gestión: trailing stop tras +3%
- **Probabilidad x Payoff:** 35% x3 (MVP)
- **Horizonte:** días / semanas
- **Estado:** observación
- **Razones de score:** {reasons}
"""


def main():
    if not SNAP.exists():
        print("No snapshot found")
        return
    data = json.loads(SNAP.read_text(encoding="utf-8"))
    tops = data.get("top_opportunities", [])[:3]
    if not tops:
        print("No top opportunities found")
        return

    stamp = now_tag()
    out = OUT_DIR / f"cards_{stamp}.md"
    blocks = [mk_card(o) for o in tops]
    out.write_text("\n\n---\n\n".join(blocks), encoding="utf-8")
    print(f"OK cards -> {out}")


if __name__ == "__main__":
    main()
