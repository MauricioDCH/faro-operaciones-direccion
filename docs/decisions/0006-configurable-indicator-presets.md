# ADR-0006 — Indicadores configurables mediante presets aprobados

**Estado:** accepted
**Fecha:** 2026-08-02
**Decisores:** equipo Faro

## Contexto

Las empresas no necesitan exactamente los mismos indicadores. Permitir SQL o fórmulas arbitrarias desde configuración debilitaría la seguridad, la trazabilidad y la reproducibilidad del producto.

## Decisión

Faro ofrecerá un catálogo cerrado de indicadores implementados y probados. La empresa seleccionará un preset y podrá ajustar únicamente parámetros aprobados, como límite de productos, métrica, severidades o inclusión del punto de reorden.

`config/indicators.yaml` contiene presets versionados y usa sintaxis JSON compatible con YAML para evitar una dependencia adicional. El CLI permite seleccionar otro preset mediante `--preset`.

Las fórmulas permanecen en código determinístico. La configuración no puede introducir SQL ni expresiones ejecutables.

## Alternativas consideradas

- Indicadores fijos para todas las empresas: rechazada por baja adaptabilidad.
- SQL libre en configuración: rechazado por seguridad y falta de control.
- Fórmulas generadas por IA: rechazadas para resultados numéricos oficiales.

## Consecuencias

- Una empresa puede iniciar desde una preconfiguración y adaptarla de manera controlada.
- Cada nuevo tipo de indicador exige código, pruebas y versión de fórmula.
- Los presets pueden evolucionar sin acoplar el motor a un sector único.

## Validación y reversión

La configuración se valida antes de consultar la base. Indicadores o parámetros desconocidos se rechazan. El motor conserva preset, hash de configuración, versión de fórmula, registros y ubicaciones fuente. Si un preset falla, puede seleccionarse otro sin modificar la base operacional.
