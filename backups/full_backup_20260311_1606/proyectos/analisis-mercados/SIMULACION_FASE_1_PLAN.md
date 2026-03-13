# Fase de Simulación — Semana 1 a 4

## Objetivo
Validar si el sistema multiagente tiene ventaja real antes de pasar a capital real.

## Reglas activas
- Capital simulado: 1000 USD
- Riesgo por operación: 2-3% (máx 5%)
- Máx posiciones simultáneas: 2
- Mercado foco: NASDAQ (QQQ + tech)
- Entrada solo con convergencia mínima

## Rutina
- Diario 22:15: reporte Telegram automático
- Ingesta señales: continua (cron)
- Autopilot: continuo
- Backup estado: cada 10 minutos

## KPIs semanales
- Win rate
- Expectancy (R)
- Max Drawdown (R)
- Nº operaciones cerradas
- % señales WATCH→READY→TRIGGERED

## Criterio mínimo al final de semana 4
- Expectancy (R) > 0
- Drawdown controlado
- Disciplina (sin entradas fuera de reglas)

## Revisión semanal (domingo)
1. Qué funcionó
2. Qué setups fallaron
3. Ajustes de umbrales
4. Mantener o descartar reglas
