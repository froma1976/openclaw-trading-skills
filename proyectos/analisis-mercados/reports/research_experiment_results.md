# Research experiment execution

- Generated at: 2026-03-14T14:17:22Z
- Items executed: 3

| Experiment | Module | Status | Decision | Delta |
|---|---|---|---|---|
| Real-time Insider Buying Validation | I-Watcher | completed | hold | filtered_symbols_gain=0, quality_ratio=0.0, min_buys=2 |
| Liquidity Monitoring with Real-time Data | L-Scanner | completed | discard | signal_completeness=0, latency_gain_s=7.01 |
| Technical Analysis with Real-time Data | T-Analyst | completed | discard | quality_setups=0, quality_vs_ready_gap=0, min_score_tech=72, min_rel_volume=0.8 |

## Notes
- Real-time Insider Buying Validation: Baseline automatica del bloque insider para decidir si conviene invertir en feed mas rapido o limpieza de eventos.
- Liquidity Monitoring with Real-time Data: Baseline automatica para evaluar si merece aumentar cadencia/frescura del bloque macro-liquidez.
- Technical Analysis with Real-time Data: Baseline automatica del bloque tecnico antes de introducir feeds mas rapidos o nuevos indicadores.