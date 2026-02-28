---
name: last30days-safe
description: Investigación de tendencias recientes (últimos 30 días) con enfoque seguro. Úsala cuando el usuario pida qué se está comentando ahora sobre un tema (herramientas, productos, técnicas, noticias), sin usar fuentes financieras/crypto ni acceso a cookies/sesiones del navegador.
---

# last30days-safe

Objetivo: investigar un tema reciente con fuentes web públicas, resumir hallazgos útiles y dar recomendaciones accionables.

## Reglas de seguridad (obligatorias)

1. No usar ni sugerir fuentes de finanzas/crypto/predicción (incluye Polymarket).
2. No pedir ni usar cookies/sesiones del navegador.
3. No ejecutar scripts externos ni binarios de terceros para scraping.
4. No pedir secretos innecesarios.

## Flujo de trabajo

1. Confirmar tema y ventana temporal (30 días por defecto).
2. Hacer 3-6 búsquedas con `web_search` orientadas al tema.
3. Abrir 2-5 fuentes clave con `web_fetch` para extraer contenido real.
4. Sintetizar:
   - qué tendencias se repiten,
   - qué herramientas/nombres aparecen más,
   - riesgos o limitaciones.
5. Entregar salida clara:
   - resumen corto,
   - lista priorizada,
   - siguiente paso recomendado.

## Formato recomendado de salida

- Resumen (2-4 líneas)
- Hallazgos clave (3-7 bullets)
- Recomendación práctica (1 bloque)
- Si aplica: “qué falta validar”

## Límites

- No afirmar datos no verificados.
- Si hay baja confianza, decirlo explícitamente.
- Priorizar fuentes técnicas/oficiales cuando sea posible.
