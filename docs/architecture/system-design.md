# Diseño del sistema

**Estado:** arquitectura lógica aprobada; selección e implementación del motor OCR pendientes.  
**Versión:** 1.0

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

- `native_text`: utiliza el texto embebido en el PDF;
- `ocr`: renderiza la página y aplica un motor OCR con versiones fijadas;
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
- `indicators`: cálculos determinísticos.
- `alerts`: condiciones explícitas y severidad.
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

Los valores finales y la tecnología elegida deben quedar versionados antes de implementar.

## Reproducibilidad

La ruta OCR debe fijar dependencia Python, dependencia del sistema, versión del motor, datos de idioma, resolución, preprocesamiento, fixtures y tolerancias.

Las imágenes intermedias son artefactos derivados y no sustituyen al PDF raw.

## Seguridad y privacidad

Durante la Maratón se procesan únicamente documentos sintéticos. Los archivos raw son inmutables y no se envían a servicios externos salvo que una capacidad aprobada lo requiera y quede documentada.

## Decisiones pendientes

Antes de implementar deben cerrarse criterios para motor OCR, renderizado PDF, umbral de texto suficiente, umbral de confianza, almacenamiento físico, framework web, UI y proveedor local de IA.

La decisión de incluir OCR está registrada en `docs/decisions/0001-support-scanned-pdf-ocr.md`.
