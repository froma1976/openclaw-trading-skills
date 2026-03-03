---
name: binance-hunter-safe
description: "Análisis Binance en modo solo lectura (sin ejecución de órdenes)."
metadata:
  openclaw:
    emoji: "🛡️"
    always: false
    requires:
      bins: ["curl", "jq", "python3"]
---

# 🛡️ Binance Hunter SAFE (solo lectura)

Versión endurecida para análisis. **No ejecuta compras/ventas**, no cambia leverage y no usa endpoints de trading.

## Qué hace
- Consulta precio actual
- Consulta velas (klines)
- Consulta volumen y cambios
- Genera lectura rápida de momentum

## Qué NO hace
- ❌ Crear órdenes spot/futuros
- ❌ Cerrar posiciones
- ❌ Cambiar apalancamiento
- ❌ Cancelar órdenes

## Uso

```bash
python3 scripts/analyze.py BTCUSDT
python3 scripts/analyze.py ETHUSDT
```

## Seguridad
- No requiere API key para análisis público.
- Si alguna vez se añade clave, mantenerla en `.env` y nunca en texto plano.
- Esta skill está diseñada para no tocar dinero real.
