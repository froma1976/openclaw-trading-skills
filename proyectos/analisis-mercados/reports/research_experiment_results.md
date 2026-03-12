# Research experiment execution

- Generated at: 2026-03-12T06:38:09Z
- Items executed: 3

| Experiment | Module | Status | Metrics |
|---|---|---|---|
| Liquidity Monitoring with Real-time Data | L-Scanner | completed | macro_adj=0, vix=None, dxy=None, latency_s=138.66 |
| Real-time Insider Buying Validation | I-Watcher | completed | symbols_with_insider_buys=17, max_insider_buys_per_symbol=10, latency_s=134.32 |
| Technical Analysis with Real-time Data | T-Analyst | completed | top5_avg_score_tech=78.4, ready_or_triggered=0, latency_s=116.39 |

## Notes
- Liquidity Monitoring with Real-time Data: Baseline automatica para evaluar si merece aumentar cadencia/frescura del bloque macro-liquidez.
- Real-time Insider Buying Validation: Baseline automatica del bloque insider para decidir si conviene invertir en feed mas rapido o limpieza de eventos.
- Technical Analysis with Real-time Data: Baseline automatica del bloque tecnico antes de introducir feeds mas rapidos o nuevos indicadores.