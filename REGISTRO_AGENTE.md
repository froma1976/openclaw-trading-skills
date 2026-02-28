# Registro centralizado de actividades del agente

## Qué resuelve
- Consumo de tokens
- Tareas cron
- Tareas de múltiples usuarios
- Trazabilidad (quién asignó qué)
- Prevención de duplicados/conflictos

## Script
`agent_activity_registry.py`

## Inicializar
```bash
py -3 agent_activity_registry.py init
```

## Ejemplos rápidos
```bash
# Registrar usuario
py -3 agent_activity_registry.py add-user --user-id fernando --name "Fernando"

# Crear tarea (dedupe automático por fingerprint)
py -3 agent_activity_registry.py add-task --title "Revisar backups" --details "VPS prod" --assigned-by fernando

# Registrar tarea cron
py -3 agent_activity_registry.py add-cron --name backup-nocturno --expr "0 3 * * *" --task-ref "Revisar backups" --owner fernando

# Registrar consumo de tokens
py -3 agent_activity_registry.py add-usage --model openai-codex/gpt-5.3-codex --in 1200 --out 350 --session agent:main:main --by agent

# Ver resumen
py -3 agent_activity_registry.py summary

# Ver dashboard (tabla única)
py -3 agent_activity_registry.py dashboard
```

## Dónde guarda
- Base de datos SQLite: `agent_activity_registry.db`

## Nota
La deduplicación evita crear tareas repetidas si ya existe una pendiente/en curso con el mismo contenido lógico.
