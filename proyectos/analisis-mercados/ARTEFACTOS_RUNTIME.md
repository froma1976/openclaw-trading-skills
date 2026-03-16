# Artefactos runtime

## Codigo fuente

- `scripts/`
- `config/`
- `models/architecture.py`
- documentacion `.md` estructural

## Artefactos generados

- `logs/`
- `data/history/`
- snapshots y estados en `data/`
- modelos `.pt`
- reportes en `reports/`
- cartas en `claw_cards/`

## Rutas concretas que hoy deben tratarse como runtime

- `AGENTS_RUNTIME_LOCAL.json`
- `claw_cards/`
- `data/core_market_research.json`
- `data/crypto_orders_sim.json`
- `data/daily_report_latest.txt`
- `data/data_quality_report.json`
- `data/gpt53_budget.json`
- `data/history/`
- `data/learning_status.json`
- `data/research_agents_latest.json`
- `data/research_alert_state.json`
- `data/research_experiment_queue.json`
- `data/research_experiment_registry.jsonl`
- `data/research_experiment_results.json`
- `data/research_memory.json`
- `data/trade_edge_model.json`
- `data/trades_clean.csv`
- `data/universe_status.json`
- `data/locks/`
- `models/lstm_*.pt`
- `models/lstm_*_meta.json`
- `models/registry.json`
- `reports/`
- `scripts/__pycache__/`
- `scripts/output.json`

## Rutas que si son fuente

- `config/risk.yaml`
- `requirements.txt`
- `scripts/*.py`
- `scripts/*.ps1`
- `models/architecture.py`
- documentacion operativa y tecnica `.md`

## Regla practica

- si cambia en cada ciclo, no debe tratarse como codigo fuente
- si se puede regenerar, debe vivir como artefacto runtime
- si define comportamiento, se versiona como fuente

## Validacion rapida

- antes de tocar estrategia: revisar fuente
- antes de revisar resultados: revisar artefactos
- antes de commitear: evitar mezclar ambos mundos

## Limpieza git recomendada

- aplicar `git rm --cached` a artefactos ya versionados para sacarlos del indice sin borrarlos del disco
- dejar `.gitignore` alineado con los patrones anteriores
- commitear por separado: primero limpieza de runtime, luego cambios de codigo
