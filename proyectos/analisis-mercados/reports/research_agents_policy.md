# Research agents policy

- `research-auditor`: lee el sistema real y detecta limites, huecos y riesgos.
- `experiment-designer`: propone experimentos falsables y automatizables.
- `experiment-judge`: prioriza con LLM ligero y scoring matematico.

## Modelos actuales

- Auditor: `phi4-mini:latest`
- Designer: `phi4-mini:latest`
- Judge: `phi4-mini:latest`

## Criterio

- coste controlado;
- ejecucion local via Ollama;
- salidas estructuradas para no depender de texto libre;
- prioridad a experimentos que puedan validarse por backtesting automatico.
