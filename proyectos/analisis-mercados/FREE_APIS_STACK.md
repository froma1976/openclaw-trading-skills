# Stack de APIs Gratis (Fase 1) — USA/NASDAQ

## Objetivo
Mantener coste ~0 mientras validamos señales pre-boom.

## 1) Mercado + Indicadores
### Opción recomendada ahora
- Yahoo Finance (vía endpoint chart) — ya integrado
- Sin API key

### Opción gratis con key (mejor para crecer)
- Alpha Vantage (free tier)
  - Pros: incluye indicadores técnicos, news y series históricas
  - Contras: rate limit bajo en free

## 2) Noticias financieras
### Ya integrado
- RSS Reuters/MarketWatch/Investing (traducido a español)

### Siguiente capa gratis
- Marketaux (free tier)
- Finnhub market news (free tier)

## 3) Earnings calendar
- Finnhub earnings calendar (free tier)
- FMP earnings calendar (free tier limitado)

## 4) Social signal
- Reddit API oficial (OAuth, free con límites)
  - Requiere client_id, client_secret y user_agent

## 5) Macro
- FRED (ya integrado)

## Prioridad de integración (orden)
1. Reddit API
2. Finnhub (earnings + market news)
3. Alpha Vantage (respaldo técnico)
4. Marketaux/FMP (según calidad)

## Credenciales mínimas a pedir
- REDDIT_CLIENT_ID
- REDDIT_CLIENT_SECRET
- REDDIT_USER_AGENT
- FINNHUB_API_KEY (opcional inmediato)
- ALPHAVANTAGE_API_KEY (opcional inmediato)
