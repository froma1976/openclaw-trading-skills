# Señales de Asimetría Positiva (x5-x10) — Marco V2

Documento base para el motor de detección de "booms" en acciones individuales.

## 1) Operaciones especiales / Spinoffs
**Qué buscar**
- Anuncio oficial de escisión de unidad de alto crecimiento.
- Narrativa de "unlock value" + desglose de segmento.

**Señales fuertes**
- División escindida con crecimiento superior al core.
- Múltiplos implícitos muy superiores al de la matriz.

**Implementación en score**
- Flag `spinoff_event=1`
- Bonus alto por evento confirmado + ventana temporal.

---

## 2) Insider Buying agresivo
**Qué buscar**
- Compras relevantes de CEO/CFO/directivos con dinero propio.
- Frecuencia y tamaño crecientes (no compras simbólicas).

**Señales fuertes**
- Múltiples insiders comprando en periodo corto.
- Porcentaje de participación insider elevado/al alza.

**Implementación en score**
- `insider_buy_score` por tamaño, recencia y rol del insider.

---

## 3) Actividad inusual en opciones
**Qué buscar**
- Incremento fuerte de Open Interest en Calls.
- Concentración por strike/fecha (convicción).

**Señales fuertes**
- Salto de OI + volumen en calls fuera de lo normal.
- Persistencia en varios días, no un spike aislado.

**Implementación en score**
- `options_flow_score` (OI delta, call/put skew, concentración).

---

## 4) Inflexión operativa (earnings + guidance)
**Qué buscar**
- Paso de pérdidas a beneficio/FCF positivo.
- Ventas >20% YoY y mejora de márgenes.
- Beat de resultados + subida de guidance.

**Señales fuertes**
- Revisiones al alza pre-earnings.
- Earnings ESP favorable.

**Implementación en score**
- `fundamental_inflection_score` con subfactores de crecimiento, margen, beat y guidance.

---

## 5) Catalizadores de desarrollo inminentes
**Qué buscar**
- Fechas binarias próximas (ensayos clínicos, lanzamientos, hitos operativos).
- Eventos con impacto directo en ingresos/adopción.

**Señales fuertes**
- Fecha confirmada + impacto económico claro.
- Baja dependencia de narrativa, alta verificabilidad.

**Implementación en score**
- `catalyst_score` ponderado por cercanía temporal e impacto esperado.

---

## Regla de convergencia para entrada
No entrar por una sola señal.

Se requiere al menos:
- 1 señal estructural (spinoff / inflexión / catalizador)
- 1 señal de capital (insiders / opciones)
- 1 señal técnica (EMA/RSI/Bollinger/volumen)

Si falta convergencia => estado WATCH, sin entrada.

## Estados operativos
- `WATCH`: hay señales parciales
- `READY`: convergencia mínima lograda
- `TRIGGERED`: entrada válida por reglas
- `INVALIDATED`: tesis anulada por condición objetiva
