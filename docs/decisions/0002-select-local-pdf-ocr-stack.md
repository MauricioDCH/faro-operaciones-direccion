# ADR-0002 — Selección de la pila local para PDF y OCR

**Estado:** accepted
**Fecha:** 2026-07-31
**Decisores:** equipo Faro
**Afecta:** extracción PDF, OCR, configuración, pruebas y reproducibilidad

## Contexto

ADR-0001 aprobó el soporte para facturas y cotizaciones PDF sintéticas con texto nativo, páginas escaneadas o contenido mixto. Faltaba seleccionar una pila que funcionara localmente en Ubuntu, preservara procedencia por página y no acoplara las reglas del negocio a un proveedor de IA.

El repositorio utiliza Python 3.12 y `uv`. La línea base sintética no requiere paquetes Python externos. Agregar una biblioteca PDF pesada solo para esta primera ruta aumentaría el bloqueo de dependencias y no resolvería por sí sola el OCR del sistema.

## Decisión

Faro utilizará una pila local basada en comandos del sistema:

- **Poppler**:
  - `pdfinfo` para validar el documento y contar páginas;
  - `pdftotext` para recuperar texto nativo por página;
  - `pdftoppm` para renderizar únicamente páginas que necesitan OCR.
- **Tesseract OCR**:
  - idioma `spa`;
  - salida TSV para recuperar texto, confianza y regiones de evidencia;
  - modo de segmentación configurable, con valor inicial `6`.
- **Python estándar**:
  - orquestación mediante `subprocess` sin shell;
  - hashes SHA-256;
  - modelos inmutables;
  - clasificación determinística inicial de factura, cotización o documento no soportado.

No se agregan dependencias Python al `pyproject.toml` en esta decisión. Las dependencias del sistema se verifican con:

```bash
make check-ocr-runtime
```

Instalación de referencia en Ubuntu:

```bash
sudo apt update
sudo apt install -y poppler-utils tesseract-ocr tesseract-ocr-spa
```

Cada ejecución registra la versión detectada de Tesseract. El comando de diagnóstico registra también la versión de Poppler.

## Interfaces

La lógica de aplicación depende de estas interfaces o límites:

- `PdfInspector`;
- `PdfPageReader`;
- `OcrEngine`;
- `DocumentClassifier`;
- `PdfExtractionService`.

La aplicación no invoca una shell ni modifica el PDF original.

## Configuración inicial

```text
PDF_EXTRACTION_MODE=auto
PDF_MAX_PAGES=3
PDF_NATIVE_TEXT_MIN_CHARACTERS=40
PDF_NATIVE_TEXT_MIN_WORDS=5
OCR_ENABLED=true
OCR_COMMAND=tesseract
OCR_LANGUAGE=spa
OCR_RENDER_DPI=300
OCR_MIN_CONFIDENCE=0.75
```

## Alternativas consideradas

### PyMuPDF más una envoltura Python para Tesseract

Pospuesta. Ofrece una API cómoda, pero agrega paquetes Python y no elimina la dependencia externa de Tesseract. Podrá reconsiderarse mediante otro ADR si Poppler limita el MVP.

### OCRmyPDF

Pospuesta. Es adecuada para producir PDF buscables, pero el flujo de Faro necesita evidencia por página y palabra antes de crear un documento derivado. También agrega más dependencias del sistema.

### Servicio OCR en la nube

Rechazado para el MVP. Introduce credenciales, costo, transferencia externa y menor reproducibilidad. Durante la Maratón solo se utilizan datos sintéticos, pero la ruta local sigue siendo más auditable.

### Modelo multimodal como única extracción

Rechazado. No proporciona una base determinística suficiente para recuperar texto, confianza y regiones, y mezclaría interpretación con validación.

## Consecuencias

Positivas:

- no se agregan paquetes Python;
- operación local y sin credenciales;
- selección por página entre texto nativo y OCR;
- evidencia OCR por palabra y región;
- versiones observables;
- separación entre recuperación de texto, clasificación y reglas de negocio.

Costos y riesgos:

- Poppler y Tesseract deben instalarse fuera de `uv`;
- la salida OCR puede variar entre versiones del sistema;
- el idioma `spa` debe estar disponible;
- Windows y macOS no están garantizados en el MVP;
- la reproducibilidad estricta del motor del sistema requerirá posteriormente una imagen de ejecución fijada.

## Plan de validación

La decisión se valida mediante:

1. diagnóstico exitoso de Poppler y Tesseract;
2. PDF con texto procesado mediante `native_text`;
3. PDF escaneado procesado mediante `ocr`;
4. PDF mixto con decisión independiente por página;
5. preservación del hash del archivo raw;
6. registro de motor, versión, idioma, confianza y regiones;
7. clasificación determinística de factura y cotización;
8. degradación segura cuando falta Tesseract o el OCR está deshabilitado;
9. rechazo de documentos con más páginas que el límite aprobado;
10. pruebas unitarias y de integración.

## Plan de reversión

`OCR_ENABLED=false` o `PDF_EXTRACTION_MODE=native_only` deshabilitan la ruta OCR sin eliminar la extracción nativa. Si Poppler resulta insuficiente, un ADR posterior podrá sustituir su implementación detrás de las mismas interfaces.
