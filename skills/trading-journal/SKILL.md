---
name: trading-journal-rag
description: "Poderosa base de datos vectorial local para el Diario de Trading y Tesis Macro (RAG). Utiliza Ollama/Nomic para crear embeddings semánticos."
metadata:
  openclaw:
    emoji: "🧠"
    always: false
    requires:
      bins: ["node"]
---

# 🧠 Trading Journal Vectorial (RAG - Retrieval-Augmented Generation)

Este es tu "Cerebro de Trading Institucional". No te olvides de las cosas; cuando leas una noticia importante de la FED, cuando veas un cambio de directiva en Tesla, o cuando tomes una decisión de mercado, **GÚARDALA AQUÍ**. Cuando te pregunten sobre un activo, **BUSCA AQUÍ ANTES** para recordar tus apuntes, decisiones pasadas y el contexto macro.

## Qué hace esta herramienta
- Convierte tus apuntes en texto a **vectores matemáticos (Embeddings)** usando tu modelo local `ollama/nomic-embed-text`.
- Guarda tus memorias en una base de datos local `journal_db.json`.
- Te permite buscar semánticamente: Si buscas "Inflación", no solo busca esa palabra exacta, te traerá notas sobre "CPI, tipos de interés o IPC" porque el modelo vectorial entiende el concepto matemático.

## Uso (Cómo invocar la herramienta)

### 1. Guardar una nueva memoria/tesis de trading:
Usa esto cuando aprendas algo valioso, quieras justificar por qué NO compraste algo hoy, o guardes reportes clave.
```bash
& "C:\Program Files\nodejs\node.exe" scripts\journal.mjs add "Hoy 09/03/2026, la inflación (CPI) salió por encima y el mercado rebotó un 3%. Decidimos vender TSLA por estar sobrecomprada y haber divergencia bajista en MACD semanal."
```

### 2. Buscar memorias históricas (RAG):
Usa esto ANTES de emitir juicios rápidos sobre activos o cuando el usuario te pregunte "qué opinas de...".
```bash
# Busca las 3 memorias históricas más relevantes sobre tu tema (el 3 es el límite de resultados devueltos).
& "C:\Program Files\nodejs\node.exe" scripts\journal.mjs search "Por qué vendí Tesla y situación de inflación" 3
```

El script buscará matemáticamente y te devolverá el contexto que escribiste en el pasado, junto a un "Score" (Cuanto más se acerque a 1.0, más relevante es). Úsalo para dar respuestas fundamentadas en un registro histórico real.
