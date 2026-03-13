# Plan de Mejoras — Analisis de Mercados

## Objetivo

- Convertir el bot desde una simulacion prometedora pero contaminada a una base fiable, auditable y medible.
- Prioridad real: primero corregir la verdad de los datos, luego el riesgo, luego la estrategia, y al final el ML.

## Fase 1 — Parar la contaminacion de metricas

- Corregir la precision de precios en `scripts/run_crypto_scalp_autopilot.py`; usar precision por simbolo o `Decimal`, no redondeo fijo a 6 decimales.
- Bloquear stablecoins en la ingesta y en ejecucion en `scripts/source_ingest_crypto_free.py` y `scripts/run_crypto_scalp_autopilot.py`.
- Unificar el schema de ordenes en `data/crypto_orders_sim.json`: al cerrar, `state` debe pasar a `CLOSED` o equivalente; usar un unico campo de salida (`close_price` o `exit_price`).
- Arreglar `scripts/dataset_quality.py` para que lea el schema real y deje de producir 0 filas limpias.
- Recalcular `data/learning_status.json` despues de limpiar ordenes historicas contaminadas por `PEPE` y stablecoins.

## Fase 2 — Riesgo y simulacion realista

- Hacer que el bot lea `config/risk.yaml` y eliminar constantes hardcodeadas de `scripts/run_crypto_scalp_autopilot.py`.
- Aplicar comisiones y slippage al PnL en cada cierre; ahora el simulador esta demasiado limpio.
- Anadir filtros de operabilidad: volumen minimo, precio minimo, exclusion de simbolos problematicos y, si conviene, whitelist inicial.
- Restringir horario y simbolos permitidos segun `config/risk.yaml`.
- Revisar `timeout`, `target` y `stop` para que dependan del activo y su volatilidad, no de un unico porcentaje global.

## Fase 3 — Robustez operativa

- Implementar escrituras atomicas para `data/crypto_snapshot_free.json` y `data/crypto_orders_sim.json`.
- Anadir lock file o control de concurrencia entre ingesta, autopilot y watchdog.
- Dejar de silenciar errores en los runners `.ps1`; al menos loggear stderr y exit code.
- Conectar el watchdog con `data/crypto_stream_status.json` y con checks de consistencia mas utiles.
- Separar scripts activos de scripts legado para evitar confusion operativa.

## Fase 4 — Calidad de datos y auditoria

- Crear un contrato de datos simple para ordenes, snapshot y metricas: campos obligatorios, tipos y estados validos.
- Anadir un script de auditoria que detecte anomalias tipo: target igual a stop, stablecoin comprada, pnl imposible, `state: ACTIVE` en trades cerrados.
- Guardar snapshots de metricas auditadas frente a metricas crudas.
- Regenerar `data/trades_clean.csv` desde ordenes ya corregidas y validar que el reporte de calidad deje de fallar.
- Anadir tests minimos sobre schema y calculos criticos.

## Fase 5 — Estrategia y edge real

- Revisar el scoring de `scripts/source_ingest_crypto_free.py` para que no premie solo `volumen/market cap` de forma ciega.
- Separar senales de ranking de senales de entrada; ahora estan demasiado mezcladas.
- Limitar sobreoperacion: cooldown por ticker, maximo de reentrada por ventana y control de repeticion de setups.
- Medir resultados por cohortes: ticker, hora, setup, confluencia y regimen.
- Eliminar o penalizar activos que aporten edge falso o muy concentrado.

## Fase 6 — ML solo si aporta

- No usar el LSTM en produccion hasta que el backtest sea serio.
- Rehacer `scripts/walkforward_eval.py` para evaluar el modelo real, no un proxy.
- Integrar `ETHUSDT` en `scripts/model_registry_update.py`.
- Versionar modelos campeones de verdad, no solo apuntar siempre al mismo archivo en `models/registry.json`.
- Exigir metricas utiles: directional accuracy neta, PnL incremental y estabilidad out-of-sample.

## Orden recomendado

1. Completar Fase 1.
2. Completar Fase 2.
3. Ejecutar una Fase 3 minima de robustez.
4. Recalcular metricas desde cero.
5. Solo entonces revisar estrategia.
6. Dejar ML para el final.

## Resultado esperado

- Las metricas probablemente caeran al principio.
- Pero lo que quede sera mucho mas creible y accionable.
- A partir de ahi ya habra una base seria para optimizar edge.
