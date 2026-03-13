# LSTM en cristiano (versión Fernando)

## Qué es
Un "entrenador matemático" que mira muchas velas seguidas y aprende patrones de subida/bajada a corto plazo.

## Qué NO es
- No es magia.
- No adivina siempre.
- No sustituye al sistema de riesgo.

## Cómo lo usamos aquí
1. Durante el día, tus espías detectan señales (noticias, flujo, euforia, velas, breakout...).
2. El LSTM añade un voto extra: **¿confirma BUY o pide AVOID?**
3. La decisión final sigue siendo de la orquesta completa (espías + riesgo + límites).

## Flujo simple
- `train_lstm.py`: entrena modelo por ticker (ej. BTCUSDT).
- `predict_lstm.py`: da score rápido de confirmación.

## Regla de seguridad
El LSTM es un **confirmador**, no un jefe. Si el riesgo dice NO, no se entra.

## Comandos rápidos
```powershell
cd C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados
py -3 scripts\train_lstm.py --ticker BTCUSDT
py -3 scripts\predict_lstm.py --ticker BTCUSDT
```

Si sale "torch no instalado", lo instalamos y listo.
