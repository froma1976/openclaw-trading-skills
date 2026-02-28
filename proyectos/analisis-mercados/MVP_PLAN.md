# MVP Plan — Alpha Scout (USA/NASDAQ)

## Objetivo del MVP (fase 1 simulada)
Detectar señales pre-boom con fuentes gratuitas y generar decisiones trazables en formato CLAW CARD.

## Capital y marco inicial
- Capital simulado inicial: **1000 USD**
- Enfoque: **dinámico por régimen de mercado**, con límites de seguridad

## Límites de seguridad (hard caps)
- Riesgo máximo por operación: **1.0% del capital**
- Exposición total máxima inicial: **70%**
- Stop/invalidación obligatorio en cada idea
- No abrir operación sin catalizador + confirmación

## Capa dinámica (se ajusta según mercado)
Variables que ajusta el agente:
- Número de posiciones simultáneas
- Tamaño por posición
- Nivel de cash
- Agresividad de entradas

Señales para ajuste:
- Volatilidad (VIX)
- Tendencia de QQQ/SPY
- Calidad de convergencia (macro + flujo + técnico)
- Correlación entre ideas activas

## Arquitectura mínima
1. Macro Scanner (FRED + calendario)
2. News/Catalyst Scanner (RSS + earnings/free endpoints)
3. Social Scanner (Reddit base)
4. Technical Scanner (RSI/EMA/Bollinger/volumen)
5. Alpha Scout Orquestador (CLAW CARD final)

## Entregables del MVP
- Watchlist inicial USA/NASDAQ
- Plantilla CLAW CARD
- Rutina diaria (pre-market / intradía / cierre)
- Dashboard Brain con:
  - tareas/agentes
  - estado de ejecución
  - cartera simulada
  - alta manual de tareas
