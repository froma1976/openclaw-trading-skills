# Checklist operativa diaria

## Arranque

- `http://127.0.0.1:8080/health` devuelve `200`.
- El gateway responde en el puerto esperado.
- `data/crypto_stream_status.json` tiene `stream_active: true` y latencia razonable.
- `data/crypto_snapshot_free.json` se actualiza sin stale prolongado.

## Trading y riesgo

- `config/risk.yaml` sigue en `execution_mode: sim_only`.
- `data/learning_status.json` no empeora de forma brusca.
- No hay explosion de `timeout` ni drawdown anormal en logs.
- El universo no mete activos excluidos o basura.

## ML

- `scripts/walkforward_eval.py` ejecuta sin error.
- `models/registry.json` refleja champion y rechazos de forma coherente.
- No hay OOM en `logs/train_lstm_daily.log`.
- Las metricas del LSTM no empeoran de forma persistente.

## Scheduler

- `OpenClaw-Crypto-Ingest-2m` corre.
- `OpenClaw-Autopilot-15m` corre.
- `OpenClaw-Crypto-Watchdog-10m` corre.
- Los jobs LSTM terminan con `EXITCODE=0` o fallo explicado.

## Comercial

- No vender senales como rentables mientras `learning_status` siga en rojo.
- Vender antes contexto, alertas y research; despues automatizacion.
