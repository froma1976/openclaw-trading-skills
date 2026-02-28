# Revisión de seguridad — last30days-skill (mvanhorn/last30days-skill)

Fecha: 2026-02-28
Commit auditado: `27b4865`
Estado: **REVISADA, NO INSTALAR AÚN**

## Qué hace
Investiga temas recientes (30 días) en Reddit, X, YouTube, Hacker News, Polymarket y web; luego sintetiza hallazgos.

## Hallazgos críticos

1. **Fuente financiera/crypto integrada (Polymarket)**
   - Detectado en `scripts/lib/polymarket.py` y flujo principal (`scripts/last30days.py`).
   - Choca con tu política: evitar skills de finanzas/crypto.

2. **Lectura de cookies de navegador para X**
   - Detectado en `scripts/lib/bird_x.py` + vendorizado `bird-search`/`sweet-cookie`.
   - Riesgo alto por acceso a sesión/autenticación local.

3. **Ejecución de procesos externos**
   - Uso de `subprocess` en múltiples módulos (`watchlist.py`, `bird_x.py`).
   - No se detectó payload malicioso explícito, pero aumenta superficie de ataque.

4. **Persistencia local (SQLite)**
   - `scripts/store.py` y `watchlist.py` guardan histórico.
   - Riesgo medio (acumulación de datos y metadatos).

## Permisos/capacidades que solicita el skill original
- `Bash`, `Read`, `Write`, `WebSearch`
- Variables/API: `OPENAI_API_KEY` (+ opcionales XAI/Brave/OpenRouter/Parallel)
- Acceso red saliente a múltiples servicios

## Recomendación
**No instalar la versión original.**

## Variante segura propuesta (pendiente de aprobación)
- Sin Polymarket
- Sin X por cookies (ni bird-search)
- Sin watchlist/scheduler (sin persistencia automática)
- Modo investigación solo con fuentes permitidas (Reddit/HN/Web/YouTube opcional)
- Herramientas y permisos mínimos

## Decisión actual
Pendiente de tu aprobación explícita para construir e instalar la variante endurecida.
