# ADR-0007 — Presets configurables de alertas determinísticas

**Estado:** accepted  
**Fecha:** 2026-08-03  
**Decisores:** equipo Faro

## Contexto

Las empresas pueden priorizar riesgos diferentes y utilizar umbrales distintos. Una distribuidora puede considerar crítico cualquier producto bajo el punto de reorden, mientras otra puede priorizar caídas de ventas o errores de calidad.

Permitir SQL, Python o fórmulas libres dentro de un archivo de configuración comprometería la seguridad, la reproducibilidad y la exactitud de las alertas.

## Decisión

Faro utilizará presets versionados en `config/alerts.yaml`.

Cada regla seleccionará una fuente aprobada:

- un resultado de indicador persistido;
- un código o severidad de `quality_finding`.

La regla podrá configurar únicamente:

- fuente y agregación aprobadas;
- filtros de dimensión controlados;
- operador;
- umbral y unidad;
- severidad;
- activación;
- tiempo de enfriamiento para una futura notificación.

El motor evaluará todas las reglas y persistirá tanto las condiciones activadas como las condiciones claras o no evaluables. Las alertas numéricas conservarán evidencia hasta los resultados, registros y ubicaciones fuente.

Los canales externos de entrega no forman parte de esta decisión. Las alertas se almacenan localmente con `delivery_status=not_configured`.

## Alternativas consideradas

### Reglas fijas para todas las empresas

Rechazada porque no representa prioridades ni umbrales empresariales diferentes.

### SQL configurable por el usuario

Rechazada por riesgo de seguridad, consultas no reproducibles y acceso no controlado a la base.

### Expresiones dinámicas evaluadas por Python

Rechazada porque permitiría ejecución arbitraria y dificultaría las pruebas.

### Generación de alertas por un modelo de IA

Rechazada como mecanismo de decisión numérica. La IA puede explicar una alerta, pero no decide si el umbral se cumple.

## Consecuencias

Positivas:

- configuración por tipo de empresa;
- reglas determinísticas y auditables;
- trazabilidad completa;
- ejecución local sin servicios externos;
- base preparada para futuros canales de notificación.

Costos y límites:

- un nuevo tipo de fuente u operador requiere código;
- los presets deben validarse antes de ejecutarse;
- los canales de entrega y su control de saturación permanecen pendientes.

## Plan de validación

La implementación debe demostrar:

1. carga de presets válidos;
2. rechazo de operadores, fuentes o campos no aprobados;
3. evaluación de indicadores y hallazgos;
4. resultados `triggered`, `clear` y `not_evaluated`;
5. identificadores reproducibles;
6. persistencia idempotente;
7. evidencia por resultados, registros y ubicaciones;
8. cambio de reglas y umbrales al seleccionar otro preset;
9. ausencia de SQL o código arbitrario;
10. ejecución mediante CLI en rutas portables.

## Plan de reversión

Si la configuración produce un comportamiento no confiable, Faro puede deshabilitar el preset afectado y conservar los indicadores y hallazgos sin generar alertas. Las tablas derivadas pueden reconstruirse desde la base operacional y las configuraciones versionadas.
