# Notas de runtime de riesgo

## Modos operativos

- `normal`: operativa completa dentro de limites.
- `defensive`: el sistema sigue operando, pero con menos tamano, menos posiciones y mas filtro.
- `paused`: no abre nuevas operaciones.

## Intencion

El objetivo es evitar que el bot pase de rentable a bloqueado sin una capa intermedia. Cuando el entorno se deteriora, primero reduce agresividad. Solo pausa si el dano continua o se rompe un limite duro.

## Exclusiones de universo

- `excluded_symbols`: lista de tickers que no deben entrar en runtime ni contaminar la lectura comercial de edge.
- Uso actual: sacar del circuito activos que distorsionan metricas o no encajan en el universo defendible.
