# Plan de hardening (propuesto)

## Objetivo
Crear `last30days-safe` para uso operativo con menor riesgo.

## Cambios obligatorios
1. Eliminar Polymarket del flujo.
2. Eliminar integración X por cookies (bird-search).
3. Desactivar watchlist y ejecución periódica por defecto.
4. Reducir permisos del skill al mínimo necesario.
5. Mantener salida enfocada en investigación y resumen.

## Implementación técnica propuesta
- Copiar skill a carpeta nueva: `skills/last30days-safe` (solo tras aprobación final).
- Editar `SKILL.md`:
  - Quitar menciones de Polymarket y X cookie auth.
  - Quitar instrucciones de watchlist.
  - Limitar herramientas a las estrictamente necesarias.
- Editar `scripts/last30days.py`:
  - Forzar `do_polymarket = False`.
  - Forzar `run_x = False` salvo API explícita segura (opcional).
- Excluir carpetas vendorizadas no usadas para X.
- Añadir nota de seguridad y límites de uso en el SKILL.md seguro.

## Validación antes de instalar
- Test 1: consulta general sin errores.
- Test 2: verificar que no hay llamadas a Polymarket.
- Test 3: verificar que no intenta leer cookies de navegador.
- Test 4: confirmar que solo usa fuentes permitidas.

## Estado
Pendiente de aprobación de Fernando para ejecutar hardening + instalación.
