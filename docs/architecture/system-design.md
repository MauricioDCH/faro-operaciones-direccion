# Diseño del sistema

**Estado:** pila local PDF/OCR seleccionada e implementada para recuperación de texto y clasificación; extracción estructurada de campos pendiente.
**Versión:** 1.1

## Regla arquitectónica

La IA interpreta, clasifica, extrae, recupera y explica. El código determinístico o SQL valida registros, calcula indicadores, aplica reglas finales de duplicados y evalúa restricciones empresariales.

El OCR recupera texto de imágenes; no valida reglas de negocio ni produce cifras finales por sí solo.

## Flujo lógico

```text
fuentes raw
  ↓
ingesta / adquisición
  ↓
extracción documental
  ├── PDF con texto → parser nativo
  ├── PDF escaneado → renderizado + OCR
  └── PDF mixto → decisión por página
  ↓
clasificación y extracción asistida por IA
  ↓
calidad / normalización
  ↓
persistencia y procedencia
  ↓
indicadores / alertas
  ↓
API / dashboard
```

La procedencia se captura en todas las etapas.

## Subsistema documental

### Inspección

Cada página se inspecciona antes de extraer campos. La decisión entre texto nativo y OCR debe ser determinística y configurable.

### Recuperación de texto

- `native_text`: Poppler `pdftotext` recupera el texto embebido por página;
- `ocr`: Poppler `pdftoppm` renderiza la página y Tesseract recupera texto, confianza y regiones;
- `unsupported`: registra por qué no puede procesarse.

### Clasificación e interpretación

La IA clasifica el documento como `invoice`, `quotation` o `unsupported`, y propone campos conforme al contrato.

### Validación

El código verifica campos obligatorios, fechas, cantidades, subtotales, impuestos, totales, identificadores, relaciones, duplicados, evidencia y confianza.

### Revisión humana

Los campos con baja confianza, OCR ilegible, clasificación incierta o evidencia insuficiente quedan `pending_review`.

## Límites de módulos

- `domain`: entidades, objetos de valor y reglas sin dependencias de frameworks.
- `ingestion`: adquisición de fuentes y registro de metadatos.
- `extraction`: PDF, inspección de páginas, texto nativo, OCR, clasificación y campos.
- `quality`: validaciones determinísticas.
- `normalization`: correspondencias controladas y formatos estándar.
- `persistence`: repositorios y límites transaccionales.
- `provenance`: archivos, páginas, regiones, transformaciones y ejecuciones.
- `indicators`: catálogo cerrado, presets configurables y cálculos determinísticos con `Decimal`.
- `alerts`: presets validados, operadores cerrados, evaluación determinística, persistencia y evidencia.
- `ai`: interpretación restringida por evidencia.
- `api` y `ui`: mecanismos de entrega.

## Interfaces previstas

```text
PdfInspector
NativePdfTextExtractor
OcrEngine
DocumentClassifier
DocumentFieldExtractor
DocumentValidator
```

La lógica de negocio no debe depender directamente de una biblioteca OCR o proveedor de IA.

## Configuración prevista

```text
PDF_EXTRACTION_MODE=auto
OCR_ENABLED=true
OCR_LANGUAGE=spa
OCR_RENDER_DPI=300
OCR_MIN_CONFIDENCE=<configured-threshold>
```

Los valores iniciales están versionados en `.env.example`. `make check-ocr-runtime` verifica comandos, idioma y versiones observadas.

## Reproducibilidad

La ruta OCR debe fijar dependencia Python, dependencia del sistema, versión del motor, datos de idioma, resolución, preprocesamiento, fixtures y tolerancias.

Las imágenes intermedias son artefactos derivados y no sustituyen al PDF raw.


## Configuración de indicadores

La empresa selecciona un preset versionado desde `config/indicators.yaml`. El archivo habilita indicadores y parámetros aprobados, pero no contiene SQL ni fórmulas ejecutables. El motor valida la configuración, calcula sobre SQLite, persiste resultados derivados y conserva evidencia. Un nuevo tipo de indicador requiere implementación, versión de fórmula y pruebas.


## Configuración de alertas

La empresa selecciona un preset versionado desde `config/alerts.yaml`. Cada regla consume resultados de indicadores o hallazgos de calidad, aplica una agregación y un operador aprobados y persiste la evaluación completa. No se acepta SQL, Python ni expresiones arbitrarias.

El motor conserva tres estados: `triggered`, `clear` y `not_evaluated`. Solo `triggered` materializa una fila en `alert`. Los canales externos permanecen desacoplados; la implementación actual registra `delivery_status=not_configured`.

## Seguridad y privacidad

Durante la Maratón se procesan únicamente documentos sintéticos. Los archivos raw son inmutables y no se envían a servicios externos salvo que una capacidad aprobada lo requiera y quede documentada.

## Decisiones pendientes

Permanecen pendientes decisiones para almacenamiento físico, framework web, UI, proveedor local de IA y una imagen de ejecución que fije las versiones del sistema.

La inclusión de OCR está registrada en `docs/decisions/0001-support-scanned-pdf-ocr.md`. La pila Poppler/Tesseract está registrada en `docs/decisions/0002-select-local-pdf-ocr-stack.md`.

## Persistencia operacional SQLite

La consolidación mantiene dos capas:

1. `record_observation`: conserva cada representación de una entidad y su fuente;
2. tablas canónicas: contienen únicamente el registro aceptado seleccionado.

La prioridad de fuentes y los conflictos se resuelven en `normalization`; `persistence` solo ejecuta la escritura transaccional. La base temporal pasa `PRAGMA integrity_check` antes de reemplazar `faro.db`.

El hash de reproducibilidad es lógico y se calcula sobre filas ordenadas. No se exige igualdad binaria entre sistemas operativos.
