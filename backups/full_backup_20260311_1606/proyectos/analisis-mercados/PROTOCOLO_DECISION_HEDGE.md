# Protocolo de Decisión Tipo Hedge (Pre-Trade)

## Checklist binaria por agente

### A) Macro Agent
- [ ] Régimen no adverso (Risk-on o neutral)
- [ ] VIX en rango aceptable
- [ ] Dólar/yields sin shock

### B) News/Catalyst Agent
- [ ] Catalizador concreto identificado
- [ ] Fecha/ventana temporal definida
- [ ] Impacto potencial en negocio validado

### C) Technical Agent
- [ ] Precio sobre EMA20 (o setup claro de recuperación)
- [ ] Estructura técnica válida (base/ruptura)
- [ ] Volumen relativo confirma (>= 1.2)
- [ ] RSI no en zona de debilidad extrema

### D) Capital Signal
- [ ] Señal de flujo/capital (social fuerte, insider, opciones, etc.)

### E) Risk-Exec Agent
- [ ] Stop lógico definido
- [ ] Pérdida máxima dentro de límites
- [ ] Exposición global dentro de límites

## Regla de resultado
- Si faltan condiciones críticas → `WATCH`
- Si cumple convergencia mínima → `READY`
- Si cumple convergencia total + trigger técnico → `TRIGGERED`

## Protocolo de salida
- Salida por invalidación (sin negociar)
- Parcial de beneficios en objetivo 1
- Trailing/gestión según estructura
