# Cierre tecnico minimo

## Objetivo

- dejar `proyectos/analisis-mercados` en un estado reproducible, revisable y sin mezclar codigo con salidas runtime

## Hecho en este bloque

- separacion explicita entre fuente y runtime en `.gitignore`
- documentacion de operativa diaria y saneamiento
- alineacion del flujo LSTM con `EnhancedLSTM` en inferencia y walk-forward
- ajuste del autopilot y del arranque operativo

## Falta para darlo por cerrado

1. Mantener `execution_mode: sim_only` en `config/risk.yaml` mientras `learning_status.json` siga en rojo.
2. Sacar del control de versiones los artefactos runtime ya trackeados.
3. Validar salud operativa con `scripts/check_scheduler_health.ps1` y `http://127.0.0.1:8080/health`.
4. Confirmar credenciales reales en dashboard y gateway; evitar defaults en produccion.
5. Ejecutar el circuito ML completo y revisar `reports/walkforward_report.md` junto con `data/learning_status.json`.
6. Separar commits de limpieza repo vs cambios funcionales.

## Criterio de salida de este bloque

- `git status` muestra solo codigo y documentacion relevantes
- no quedan `csv`, `json`, `jsonl`, `pt`, `md` generados ni `pyc` como cambios pendientes del proyecto
- dashboard, gateway y scheduler responden
- el sistema sigue en simulacion hasta que las metricas salgan de rojo

## Riesgos abiertos

- edge economico insuficiente segun `data/learning_status.json`
- credenciales por defecto como fallback operativo
- demasiada variacion runtime entrando en el repo
