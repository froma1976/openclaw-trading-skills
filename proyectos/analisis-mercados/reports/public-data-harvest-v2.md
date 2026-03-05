# Public Data Harvest v2

Fecha: 2026-03-05

## Resumen
- Catálogo ampliado de fuentes públicas: `data/public_sources_catalog_v2.csv`
- Dataset agregado MQL5 ya disponible:
  - `data/public_trader_histories_mql5_bulk.csv`
  - `data/public_trader_histories_mql5_bulk_ok.csv`
- Dataset clone-friendly derivado:
  - `data/trades_for_clone.csv`

## Observaciones clave
1. Las fuentes públicas más abundantes dan métricas **agregadas** por señal/trader.
2. El detalle **trade-by-trade** de terceros casi siempre requiere login/autorización.
3. Para entrenar robusto LSTM, conviene combinar:
   - OHLCV público masivo (CryptoDataDownload/Kaggle/GitHub)
   - + trade history propio por API (Binance/Blofin)

## Próximo paso recomendado
- Mantener este catálogo como índice vivo.
- Priorizar ingesta diaria de OHLCV + historial propio.
- Usar públicos agregados como features de contexto/ranking, no como verdad trade-by-trade.
