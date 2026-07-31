# Diseño del sistema

**Estado:** conceptual; las interfaces y las decisiones tecnológicas permanecen en `planned`.

## Regla arquitectónica

La IA interpreta, extrae, clasifica, recupera y explica. El código determinístico o SQL valida registros, calcula indicadores, aplica las reglas definitivas de duplicados y evalúa restricciones de negocio.

## Flujo lógico

`fuentes sin procesar -> ingesta/extracción -> calidad/normalización -> persistencia -> indicadores/alertas -> API/interfaz`

La procedencia se registra en todas las etapas del flujo y no se agrega únicamente al presentar los resultados.

## Límites de los módulos

- `domain`: entidades, objetos de valor y reglas de negocio sin dependencias de frameworks.
- `ingestion`: adquisición de fuentes y registro de metadatos.
- `extraction`: obtención de campos estructurados desde fuentes semiestructuradas.
- `quality`: hallazgos determinísticos de calidad de datos.
- `normalization`: correspondencias controladas y formatos normalizados.
- `persistence`: repositorios y límites transaccionales.
- `provenance`: ubicaciones de origen, transformaciones y ejecución de reglas.
- `indicators`: cálculo determinístico de indicadores.
- `alerts`: condiciones explícitas y niveles de severidad.
- `ai`: interpretación y explicación restringidas por evidencia.
- `api` y `ui`: mecanismos de entrega, sin lógica de negocio crítica.

## Decisiones pendientes

Deben crearse registros ADR antes de seleccionar la base de datos, el framework web, el framework de interfaz, la estrategia de extracción de PDF o el proveedor de modelos de IA.
