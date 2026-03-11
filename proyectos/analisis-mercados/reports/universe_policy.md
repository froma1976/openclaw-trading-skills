# Universe policy

- `core`: activos con muestra suficiente y edge positivo defendible.
- `watch`: activos en observacion; no se expulsan, pero tampoco se promocionan todavia.
- `excluded`: activos manualmente bloqueados o con deterioro claro en la ventana reciente.

Regla de trabajo:

- el sistema empieza con un nucleo pequeno y defendible;
- los activos de `watch` pueden volver a `core` cuando mejoren sus metricas;
- los activos `excluded` no quedan fuera para siempre: se reevalúan en cada clasificacion.
