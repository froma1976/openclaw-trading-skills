# Saneamiento de produccion

## Estado real hoy

- El stack ya levanta dashboard y evaluacion LSTM, pero no tiene edge economico suficiente para operar en real.
- La operativa debe mantenerse en `sim_only` hasta mejorar metricas de `learning_status.json`.
- Hay deuda tecnica en seguridad, scheduler, gateway y separacion entre codigo y datos generados.

## Bloque 1 - Seguridad

- Rotar todos los secretos expuestos en configuracion local: Telegram, gateway token, Brave API y cualquier credencial persistida.
- Mover credenciales operativas a variables de entorno o a un `.env` local no versionado.
- Sustituir credenciales por defecto del dashboard por credenciales propias.
- Revisar `openclaw.json` para dejar solo configuracion, nunca secretos de larga vida.

## Bloque 2 - Estabilidad operativa

- Mantener `execution_mode: sim_only` en `config/risk.yaml` hasta salir de semaforo rojo.
- Verificar cada arranque: gateway, dashboard, ingesta, freshness y scheduler.
- Separar mejor los flujos:
  - research e ingesta,
  - scoring y simulacion,
  - entrenamiento y walk-forward,
  - dashboard y control.
- Evitar que tareas largas bloqueen endpoints HTTP del dashboard.
- Mantener la evaluacion LSTM alineada con la arquitectura real del modelo.

## Bloque 3 - Sostenibilidad tecnica

- Tratar `proyectos/analisis-mercados` como proyecto reproducible con `requirements.txt` y checklist de bootstrap.
- No mezclar artefactos runtime con codigo fuente en commits normales.
- Conservar logs y reportes como salidas de sistema, no como fuente de verdad.
- Limpiar backlog de archivos temporales y scripts duplicados antes de nuevas features.

## Bloque 4 - Monetizacion realista

- Fase 1: alertas premium por Telegram con scoring, riesgo y contexto.
- Fase 2: dashboard de suscripcion con watchlists, reportes y ranking de setups.
- Fase 3: research-as-a-service para small traders o desks pequenos.
- Fase 4: paper-trading auditado con track record verificable antes de vender automatizacion.

## KPI minimos antes de tocar dinero real

- `learning_status.json` fuera de ROJO durante varias semanas.
- Profit factor > 1.2.
- Expectancy positiva y drawdown controlado.
- Walk-forward sin errores y mejor que baseline en varias ventanas.
- Scheduler estable sin huecos largos de freshness.

## Orden recomendado de ejecucion

1. Rotacion de secretos.
2. Credenciales reales del dashboard y gateway.
3. Validacion de tareas programadas.
4. Limpieza de repo y separacion de artefactos.
5. Recalibracion de scoring y riesgo.
6. Solo despues, empaquetado comercial.
