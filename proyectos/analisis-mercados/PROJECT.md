# Proyecto: OpenClaw — Detección de señales pre-boom y gestión de capital asimétrico

## Agente líder
- **Nombre:** Claw-Prime
- **Identidad:** Entidad de anticipación de liquidez (no reactiva al precio)

## Misión
Anticipar flujos de masa monetaria hacia activos de riesgo antes de su corrección por mercado minorista, priorizando la asimetría informativa de 6–12 meses.

## Principios axiales
1. **Vigilancia Líquida** (M2 global como señal primaria)
2. **Neutralidad de Ruido** (filtrado de eventos sin impacto estructural)
3. **Preservación Evolutiva** (validación en fase simulada antes de capital real)

## Arquitectura multi-agente
- **L-Scanner:** liquidez global / balances BC / M2
- **I-Watcher:** compras de insiders de alta convicción
- **T-Analyst:** ejecución técnica (niveles y timing)

## Regla de activación (convergencia)
No hay compra por señal aislada. Se exige convergencia:
- Liquidez favorable (L-Scanner)
- Validación de insiders (I-Watcher)
- Confirmación técnica (T-Analyst)

## Fases
### Fase 1 (simulada)
- KPI 1: Alpha > S&P500 en 3–6 meses
- KPI 2: correlación > 0.85 entre predicción de liquidez y movimientos en picks

### Fase 2 (capital real)
- 70% de señales pre-boom rentables
- VIX < 18.06
- despliegue inicial: 10% de capital

## Estado
- Inicializado.
- Identidad del agente definida en `AGENT_IDENTITY.md` (Alpha Scout).
- Pendiente: definición de universo, fuentes de datos y cadencia operativa.
