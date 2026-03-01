# Manual Operativo Multiagente — OpenClaw Alpha Scout

## Objetivo
Convertir señales de mercado en decisiones ejecutables con riesgo controlado, usando varios agentes especializados.

## Roles de agentes

### 1) alpha-scout (Orquestador)
- Consolida señales de todos los agentes.
- Decide estado final: `WATCH`, `READY`, `TRIGGERED`, `INVALIDATED`.
- Autoriza creación de orden simulada.

### 2) macro-agent
- Clasifica régimen diario: `Risk-on` / `Risk-off`.
- Señales clave: VIX, DXY, yields, liquidez.
- Regla: si `Risk-off`, bajar agresividad y exposición.

### 3) news-catalyst-agent
- Detecta catalizadores reales (earnings, guidance, contratos, hitos).
- Etiqueta calidad del evento: Alto / Medio / Bajo.
- Filtra ruido mediático.

### 4) technical-agent (determinista)
- Calcula: EMA20/EMA50, RSI14, Bollinger, volumen relativo, breakout.
- Emite score técnico y confirmación estructural.

### 5) risk-exec-agent (determinista)
- Define tamaño, stop, invalidación y salida.
- Verifica límites de riesgo global.

---

## Protocolo de decisión (voto por convergencia)

Para pasar a `READY`, deben cumplirse mínimo 2 de 3 bloques:
1. **Estructural**: catalizador/fundamental/spinoff
2. **Capital**: insiders/opciones/social fuerte
3. **Técnico**: score técnico >= umbral

Para pasar a `TRIGGERED`:
- 3 de 3 bloques + score final >= umbral alto
- Macro no adverso (`Risk-on` o neutral)
- Riesgo validado por risk-exec-agent

Si no se cumple: `WATCH`.
Si se rompe invalidación: `INVALIDATED`.

---

## Límites de riesgo operativos (fase simulada)
- Capital base: 1000 USD
- Riesgo por operación: 2–3% (máx absoluto 5%)
- Exposición total máxima: 70%
- Máx posiciones simultáneas: 2 al inicio
- Stop siempre definido antes de entrar

---

## Flujo automático
1. Ingesta señales (macro/mercado/news/social/earnings)
2. Scoring (técnico + social + macro + asimetría)
3. Estado por activo (`WATCH/READY/TRIGGERED`)
4. Si `TRIGGERED`: crear tarea + orden simulada pendiente
5. Seguimiento y cierre por reglas
6. Registro en cartera y journal

---

## Reglas anti-error
- No operar por FOMO
- No operar sin catalizador
- No operar sin invalidación
- No mover stop en contra
- No aumentar tamaño tras pérdida

---

## KPI de control
- Win rate
- Expectativa matemática
- Drawdown máximo
- R múltiplos promedio
- % señales que pasan de WATCH a READY/TRIGGERED
