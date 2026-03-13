# Fuentes públicas de históricos (avance inicial)

Fecha: 2026-03-05

## Resultado rápido
- Se creó CSV inicial: `data/public_trader_histories_mql5.csv`
- Registros procesados: 9 URLs de señales MQL5
- Accesibles sin login: 4
- Bloqueadas/404 (según región/estado señal): 5

## Qué contiene el CSV ahora
- URL de señal pública
- Nombre de señal
- Estado de extracción
- Conteo de operaciones BTC/SOL cuando está visible en la tabla pública (ej. `btc_deals`)

## Nota importante
MQL5 sí expone estadísticas históricas agregadas públicas, pero el detalle trade-by-trade en tiempo real suele pedir login.

## Siguiente paso recomendado
1. Repetir extracción sobre más señales BTC/SOL activas (ampliar de 9 a 50+).
2. Completar con Bybit/Binance leaderboard público (cuando no bloquea región).
3. Al recibir API Binance, mezclar con histórico propio para llegar a 100-200 operaciones limpias y accionables.
