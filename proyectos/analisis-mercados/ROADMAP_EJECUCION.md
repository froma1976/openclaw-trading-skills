# Roadmap de ejecucion automatica

Fecha base: 2026-03-11

## Objetivo

Pasar el sistema desde una simulacion prometedora pero rigida a un motor mas limpio, adaptable y defendible ante compradores serios.

## Fase 1 - 2 a 3 dias

### Meta
- Dejar el motor de riesgo menos binario: `normal -> defensivo -> pausa`.
- Sacar reglas hardcodeadas basicas y leer riesgo desde configuracion.

### Entregables
- Lectura real de `config/risk.yaml` en el autopilot.
- Nuevo estado operativo `defensive`.
- Resumen horario mostrando modo y motivo.
- Base lista para afinar reactivacion y sizing dinamico.

### Criterio de exito
- El motor ya no pasa directamente de normal a pausa por una sola racha.
- Los limites clave quedan centralizados en configuracion.

## Fase 2 - 3 a 5 dias

### Meta
- Limpiar verdad de datos y metricas.

### Entregables
- Unificar schema de ordenes.
- Revisar `state`, `close_price/exit_price`, `pnl_usd` y cierres.
- Regenerar metricas de aprendizaje sin contaminacion evidente.

### Criterio de exito
- Las metricas recientes ya se pueden presentar internamente sin contradicciones de schema.

## Fase 3 - 4 a 6 dias

### Meta
- Medir edge por contexto y no solo agregado global.

### Entregables
- Breakdown por ticker, setup, hora y regimen.
- Identificacion de activos o ventanas que destruyen edge.
- Reglas de exclusion o penalizacion.

### Criterio de exito
- El sistema sabe donde gana, donde pierde y cuando debe bajar agresividad.

## Fase 4 - 3 a 4 dias

### Meta
- Robustez operativa y auditabilidad.

### Entregables
- Escrituras mas seguras.
- Menos errores silenciados.
- Watchdogs y estados mas claros.
- Trazas mas utiles para operacion y venta institucional.

### Criterio de exito
- Incidencias reproducibles y recuperables sin improvisacion.

## Fase 5 - 5 a 7 dias

### Meta
- Revalidar si LSTM aporta edge real.

### Entregables
- Walk-forward mas serio.
- Comparativa incremental sobre baseline.
- Decision clara: promover, mantener auxiliar o congelar.

### Criterio de exito
- El ML se mantiene solo si mejora resultados o timing de manera medible.

## Orden de ejecucion recomendado

1. Riesgo adaptativo y configuracion.
2. Limpieza de metricas y schema.
3. Analitica de edge.
4. Robustez operativa.
5. Validacion final de ML.

## Estado actual

- Fase activa: Fase 1.
- Accion en curso: introducir modo defensivo y centralizar parametros de riesgo.
