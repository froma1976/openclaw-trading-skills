# Research experiment execution

- Generated at: 2026-03-12T06:57:58Z
- Items executed: 3

| Experiment | Module | Status | Decision | Delta |
|---|---|---|---|---|
| Liquidity Monitoring with Real-time Data | L-Scanner | completed | discard | signal_completeness=0, latency_gain_s=10.76 |
| Real-time Insider Buying Validation | I-Watcher | completed | promote | filtered_symbols_gain=6, quality_ratio=0.353 |
| Technical Analysis with Real-time Data | T-Analyst | completed | discard | quality_setups=0, quality_vs_ready_gap=0 |

## Notes
- Liquidity Monitoring with Real-time Data: Baseline automatica para evaluar si merece aumentar cadencia/frescura del bloque macro-liquidez.
- Real-time Insider Buying Validation: Baseline automatica del bloque insider para decidir si conviene invertir en feed mas rapido o limpieza de eventos.
- Technical Analysis with Real-time Data: Baseline automatica del bloque tecnico antes de introducir feeds mas rapidos o nuevos indicadores.