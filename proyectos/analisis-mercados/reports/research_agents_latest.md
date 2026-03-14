# Research agents report

- Generated at: 2026-03-14T13:15:01Z
- Auditor model: phi4-mini:latest
- Designer model: phi4-mini:latest
- Judge model: phi4-mini:latest

## Top priorities
- [high] Macro freshness scoring by indicator health: Puntuar y backtestear variantes de macro_signal_completeness y penalización por timeouts/errores.
- [high] Insider threshold calibration: Comparar automáticamente umbrales de insider_buys y su calidad relativa.
- [high] Technical gate tuning: Buscar rejillas pequeñas de score técnico y volumen relativo para maximizar calidad de setups.

## Ranked experiments
| Rank | Experiment | Score | Why |
|---|---|---:|---|
| 1 | Real-time Insider Buying Validation | 4.740 | Fallback determinista: experimento concreto, automatizable y compatible con el pipeline actual. |
| 2 | Technical Analysis with Real-time Data | 4.560 | Fallback determinista: experimento concreto, automatizable y compatible con el pipeline actual. |
| 3 | Liquidity Monitoring with Real-time Data | 4.300 | Fallback determinista: experimento concreto, automatizable y compatible con el pipeline actual. |

## Execution queue
- [pending] Real-time Insider Buying Validation: I-Watcher -> Desplegar insider_min_buys ganador en research_deployments si supera umbral objetivo.
- [pending] Technical Analysis with Real-time Data: T-Analyst -> Desplegar technical_quality_filter solo si mejora el número y la calidad de setups accionables.
- [pending] Liquidity Monitoring with Real-time Data: L-Scanner -> Evaluar variantes paramétricas dentro del executor y desplegar solo si mejora señal útil.

## Architecture changes
- Separar claramente baseline, candidate, deployment y registry para cada módulo de research.
- Mantener ejecutores paramétricos pequeños por módulo antes de escalar a búsquedas masivas.

## Research lines
- Calibration by regime for insider thresholds.
- Technical gate tuning conditioned on bubble level.