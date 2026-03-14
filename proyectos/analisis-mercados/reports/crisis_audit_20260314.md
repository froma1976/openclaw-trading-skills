# Auditoría de Crisis: Análisis de Rentabilidad Post-Reset (14/03/2026)

## 1. El Problema: Pérdida de Rentabilidad
Tras el reinicio del sistema el 13/03/2026, el bot presentó una racha de operaciones fallidas o con beneficios absorbidos por comisiones, contrastando con el éxito previo (Win Rate superior y ganancias consistentes).

## 2. Hallazgos de la Auditoría Técnica
El análisis pormenorizado de los logs (`crypto_orders_sim.json`) y la configuración (`risk.yaml`) revela tres causas críticas:

### A. Dilución de la "Convicción" (Filtro 50 vs 78)
*   **Antes:** Se operaba con un score mínimo de **78**. El bot solo entraba en activos con un momentum muy fuerte, alcanzando el TP del 0.9% rápidamente.
*   **Ahora:** El umbral bajó a **50**. El sistema captó señales de "ruido", activos laterales que no tienen la fuerza necesaria para superar el arrastre de las comisiones.

### B. El "Drag" de Comisiones en Capital Pequeño
*   **Configuración:** Operaciones de **$30 USD**.
*   **Impacto:** Las comisiones de apertura y cierre (~0.20% total) representan ~$0.06. 
*   **Resultado:** Operaciones cerradas por *Timeout* (12 min) con ligeras ganancias brutas terminan en **pérdidas netas**. Se produce una "muerte por mil cortes".

### C. Condición de Mercado (Bearish Intraday)
*   En el momento del análisis, el mercado principal (BTC, ETH, SOL) presenta caídas de entre el 2% y el 4%. Un filtro de score bajo en un mercado bajista aumenta drásticamente la probabilidad de falsos positivos.

## 3. Acciones Tomadas y Recomendaciones
1.  **Reinicio del Bot:** Se ha ejecutado `Arrancar_Bot_Trading.bat` para asegurar la sincronización de agentes.
2.  **Ajuste del Filtro:** Se recomienda volver a un score de **75-78** para priorizar calidad sobre cantidad.
3.  **Análisis de Agentes:** Los agentes "Spy" (Whale, Flow, News) están operativos, pero su efectividad se ve comprometida al procesar señales de score bajo.

## 4. Integración Futura: Hyperspace AGI
Se propone integrar **Hyperspace AGI** para delegar el "Research" y la optimización de parámetros a una red distribuida, liberando a los agentes locales para la ejecución pura de scalping.
