# Portfolio Schema (USD)

## Objetivo
Modelo mínimo para visualizar cartera simulada en dashboard.

## Campos por posición
- id
- ticker
- market
- sector
- side (long/short)
- status (watch/active/closed/invalidated)
- conviction (1-5)
- entry_price
- stop_price
- target_1
- target_2
- qty
- notional_usd
- opened_at
- closed_at
- thesis_ref (CLAW CARD)

## KPIs derivados
- market_value_usd
- unrealized_pnl_usd
- realized_pnl_usd
- pnl_pct
- portfolio_exposure_pct
- max_risk_usd
- drawdown_pct

## Reglas MVP
- Divisa fija: USD
- Riesgo por operación: hard cap 1%
- Exposición total inicial: <= 70%
- Convicción obligatoria (1-5)
