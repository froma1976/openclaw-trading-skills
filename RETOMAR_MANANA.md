# Retomar mañana — NASDAQ multiagente / Agents Dashboard

## Contexto
- Dashboard: Agents Ops Dashboard (FastAPI) + pipeline proyectos/analisis-mercados.
- URL local dashboard: http://127.0.0.1:8080

## Estado modelos (OpenClaw/Ollama)
- Ollama instalado: %LOCALAPPDATA%\Programs\Ollama\ollama.exe
- Modelos Ollama vistos: qwen2.5:7b, qwen3:8b, deepseek-r1:8b, gemma3:4b, phi4-mini, nomic-embed-text.
- En OpenClaw: ollama/qwen2.5:7b daba "not allowed" (allowlist del gateway).
- Se pudo cambiar a modelos locales permitidos: gemma3:4b / phi4-mini.
- Problema recurrente gateway: puerto 18789 ocupado por node.exe (gateway colgado).

## Agents Dashboard (app.py)
- Endpoint: /health y /api/summary.
- Home / hace probes a APIs externas (FINNHUB/FMP/AV/FRED/NEWSAPI/Coingecko) con timeouts.
- Autopilot ejecuta scripts Python vía subprocess (puede bloquear el server).

## Entrenamiento LSTM (analisis-mercados)
- Log: C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados\logs\train_lstm_daily.log
- Último: ok=true, modelo lstm_SOLUSDT.pt, val_mse ~ 0.00087553, exitcodes 0.
- ALERTA: dataset quality: rows_raw=99 pero rows_clean=0 (dropped_nulls=99). Revisar ETL/limpieza y trades_clean.csv.

## Checklist mañana
1) Dashboard health:
   - curl http://127.0.0.1:8080/health
   - curl http://127.0.0.1:8080/api/summary
2) Autopilot:
   - Ver frescura de latest_snapshot_free.json y autopilot_log.json
3) LSTM/ETL:
   - Revisar trades_clean.csv (no debe estar vacío)
   - Ver por qué se dropean todas las filas (nulls)
4) OpenClaw gateway:
   - Ver proceso que escucha 18789, parar si está colgado y reiniciar gateway
   - Confirmar allowlist incluye ollama/qwen2.5:7b si se quiere usar
