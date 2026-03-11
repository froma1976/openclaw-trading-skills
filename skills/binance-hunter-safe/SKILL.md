---
name: binance-hunter-safe
description: "Análisis Cuantitativo Matemático de Binance en modo solo lectura (sin ejecución de órdenes)."
metadata:
  openclaw:
    emoji: "🛡️"
    always: false
    requires:
      bins: ["node"]
---

# 🛡️ Binance Hunter SAFE (Quant Edition)

Versión mejorada y rigurosa para análisis matemático institucional. **No ejecuta compras/ventas**, no cambia leverage y no usa endpoints de trading. 
A diferencia de un LLM que intuye gráficas, esta Skill calcula al milímetro indicadores clásicos usando datos reales.

## Qué hace y cómo calcula
- Consulta Klines (Velas) históricas de `15m`, `1h`, `4h`, y `1d`.
- **SMA y EMA:** Math preciso para Medias Móviles Exponenciales (9, 21, 50, 200).
- **RSI (Relative Strength Index):** Suavizado de 14 periodos estilo TradingView.
- **Bollinger Bands:** 20 SMA + 2 Standard Deviations.
- **MACD:** Fast 12, Slow 26, Signal 9, calculado con EMA y diferencias de Histograma para momentum real.

## Qué NO hace
- ❌ Crear órdenes spot/futuros
- ❌ Cerrar posiciones
- ❌ Cambiar apalancamiento
- ❌ Cancelar órdenes

## Uso (Cómo invocar la herramienta)
El Asistente (OpenClaw) debe invocar el script (usando comillas en la ruta del binario de Node si está en Windows) pasando el activo y el timeframe:

```bash
# Analizar marco de corto y largo
& "C:\Program Files\nodejs\node.exe" scripts\quant_analyzer.mjs BTCUSDT 15m
& "C:\Program Files\nodejs\node.exe" scripts\quant_analyzer.mjs ETHUSDT 1d
```

## Ejecucion segura en Windows PowerShell
Si la ruta de Node contiene espacios, usa siempre comillas en ambas rutas. Para el colector de precios:

```powershell
& "C:\Program Files\nodejs\node.exe" "C:\Users\Fernando\.openclaw\workspace\skills\binance-hunter-safe\scripts\price_collector.mjs"
```

O usa el wrapper listo para PowerShell:

```powershell
& "C:\Users\Fernando\.openclaw\workspace\skills\binance-hunter-safe\scripts\run_price_collector.ps1"
```

En tareas programadas, usa este formato para evitar errores de sintaxis:

- `Program/script`: `powershell.exe`
- `Add arguments`: `-ExecutionPolicy Bypass -File "C:\Users\Fernando\.openclaw\workspace\skills\binance-hunter-safe\scripts\run_price_collector.ps1"`

## Formato del JSON de Salida
El script devolverá un JSON estricto con `asset`, `timeframe`, `trend_analysis` (cruce de EMAs), `momentum_oscillators` (RSI, MACD) y un `summary` pre-generado por el algoritmo matemático libre de alucinaciones LLM. Pasa estos datos al usuario.
