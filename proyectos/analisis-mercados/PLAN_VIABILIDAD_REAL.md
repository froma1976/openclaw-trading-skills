# Plan de viabilidad real

Fecha: 2026-03-17

## Diagnostico corto

- El sistema sigue en `sim_only`.
- La infraestructura es fuerte, pero el edge reciente es negativo.
- El problema principal no es tecnico sino economico: demasiadas entradas flojas para el coste total de operar.

## Fase 0: correcciones inmediatas

Objetivo: dejar de abrir operaciones que no compensan fees, slippage y ruido.

- Subir exigencia base del score.
- Exigir mayor retorno neto minimo por trade.
- Subir notional minimo y beneficio neto esperado minimo.
- Reducir la cadencia total de operaciones.
- Endurecer el modo defensivo, no expandirlo.
- Excluir temporalmente tickers con edge reciente claramente negativo.

## Fase 1: estabilizacion en simulacion

Objetivo: demostrar que el sistema deja de perder por estructura.

- Medir por separado `NORMAL`, `LATERAL`, `ALCISTA` y `SHORT`.
- Revisar semanalmente setup edge y ticker edge.
- Mantener fuera los activos que sigan drenando capital.
- Validar que el beneficio neto ya supera comisiones y slippage de forma repetida.

## Fase 2: readiness para capital real pequeno

Solo deberia plantearse si se cumplen durante una ventana sostenida:

- profit factor > 1.2
- expectancy neta > 0
- drawdown controlado
- consistencia por modo, no solo agregada
- operativa estable sin fallos recurrentes del scheduler o del entrenamiento

## Fase 3: capital real prudente

- desplegar una fraccion pequena del capital
- aumentar solo si se mantiene edge neto despues de costes
- no escalar por sensacion de mercado alcista; solo por evidencia

## Cambios inmediatos aplicados hoy

- score base mas alto
- filtros economicos mas duros
- menor frecuencia maxima de operacion
- modo defensivo mas estricto
- exclusiones temporales de tickers muy debiles

## Regla operativa clave

Mejor perder oportunidades que seguir operando oportunidades con edge negativo.
