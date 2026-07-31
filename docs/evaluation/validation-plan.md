# Plan de validación

**Estado:** línea base sintética y primera ruta PDF/OCR validadas; validación integral del MVP pendiente.

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

## Validación prevista para PDF y OCR

La línea base actual contiene facturas PDF con texto y no demuestra todavía soporte OCR. La implementación deberá agregar fixtures sintéticos versionados para:

| Caso | Resultado esperado |
|---|---|
| Factura con texto nativo | extracción directa |
| Factura escaneada | OCR y campos verificables |
| Cotización con texto nativo | clasificación `quotation` |
| Cotización escaneada | OCR y campos verificables |
| PDF mixto | decisión correcta por página |
| Página ilegible | `pending_review` |
| Documento no soportado | `rejected` o `unsupported` |
| Campo sin evidencia | no consolidado |
| Total inconsistente | hallazgo de calidad |
| Baja confianza | revisión humana |
| Ejecución repetida | resultados reproducibles dentro de la tolerancia aprobada |
| PDF raw después del proceso | hash sin cambios |

### Objetivos OCR

Estos valores son objetivos, no resultados:

- 100 % de las páginas registran el método utilizado;
- 100 % de los campos documentales conservan archivo y página;
- 100 % de las páginas OCR registran motor y versión;
- 100 % de resultados bajo el umbral pasan a revisión;
- 0 campos inventados cuando no existe evidencia;
- 100 % de documentos no soportados se rechazan de forma estructurada;
- al menos 90 % de exactitud de campos obligatorios en los fixtures escaneados aprobados.

### Pruebas requeridas

- unitarias para decisión `native_text` frente a `ocr`;
- unitarias para clasificación documental;
- unitarias para validación de fechas y totales;
- integración desde PDF hasta entidades y procedencia;
- regresión con versiones fijadas;
- error cuando el motor OCR no esté disponible;
- error cuando falten datos de idioma;
- revisión humana para confianza insuficiente;
- preservación de hashes raw.

Los resultados deberán registrarse después de ejecutar la implementación. No deben presentarse como cumplidos durante esta rama documental.

## Evidencia ejecutada — recuperación PDF/OCR

**Fecha:** 2026-07-31
**Entorno observado:** Python 3.13.5 para validación del parche; objetivo del repositorio Python 3.12 o superior.

Runtimes observados:

- Poppler `25.06.0`;
- Tesseract `5.5.0`;
- idioma `spa` disponible.

Resultados ejecutados:

- compilación de `src`, `tests` y `scripts`: aprobada;
- suite completa disponible en el paquete de trabajo: 25 pruebas aprobadas;
- factura con texto nativo: ruta `native_text`;
- cotización escaneada: ruta `ocr`;
- PDF mixto: selección independiente por página;
- Tesseract inexistente: error estructurado sin texto inventado;
- hash del PDF raw antes y después: sin cambios;
- procedencia OCR: archivo, página, motor, versión, idioma, confianza y regiones presentes;
- inspección visual del fixture escaneado: sin recortes ni solapamientos.

Limitaciones:

- FR-002 permanece `planned`: todavía no se materializan entidades completas de factura, cotización y líneas;
- QR-018 permanece `planned`: las versiones de Poppler y Tesseract se observan, pero aún no están fijadas mediante una imagen reproducible;
- la exactitud del 90 % debe medirse sobre un corpus ampliado, no sobre los fixtures mínimos de esta iteración.
