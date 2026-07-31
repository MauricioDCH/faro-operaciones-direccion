# Plan de validación

**Estado:** línea base sintética validada; validación integral del MVP pendiente.

## Categorías de evidencia

- pruebas unitarias determinísticas para generación, fórmulas y reglas;
- pruebas de integración desde las fuentes hasta los hallazgos;
- pruebas de extremo a extremo para el flujo de demostración;
- verdad de referencia de anomalías para medir detección y falsos positivos;
- comprobación de procedencia para alertas y respuestas numéricas;
- pruebas de rechazo cuando la evidencia sea insuficiente;
- comandos reproducibles de instalación, generación, validación, pruebas y ejecución.

## Objetivos del MVP

- procesar al menos 95 % de las entradas sintéticas válidas;
- detectar al menos 90 % de las anomalías sembradas;
- proporcionar procedencia identificable para 100 % de las alertas;
- respaldar 100 % de las respuestas numéricas con resultados estructurados;
- responder al menos cinco preguntas operativas priorizadas.

Los objetivos que todavía dependen de ingesta, consolidación, indicadores, alertas o interfaz no se consideran cumplidos por la línea base sintética.

## Resultado de la línea base sintética

**Fecha:** 31 de julio de 2026  
**Semilla:** `20260731`  
**Dataset:** `0.1.0`

| Evidencia | Resultado |
|---|---:|
| Anomalías esperadas | 11 |
| Anomalías detectadas | 11 |
| Coincidencias con la verdad de referencia | 11 |
| Anomalías faltantes | 0 |
| Hallazgos inesperados | 0 |
| Pruebas automatizadas ejecutadas | 10 |
| Pruebas aprobadas | 10 |

Comandos ejecutados:

```bash
uv sync --locked
make check
make generate-data
make validate-data
```

El resultado anterior valida únicamente la generación, reproducibilidad, integridad del manifiesto, contrato del lote del plugin y detección de anomalías sembradas. No valida todavía el flujo completo del producto.
