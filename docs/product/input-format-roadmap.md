# Hoja de ruta de formatos de entrada

**Estado:** approved roadmap  
**Fecha:** 2026-08-02

## Objetivo

Ampliar las fuentes aceptadas por Faro sin comprometer exactitud, seguridad, trazabilidad ni portabilidad entre Linux y Windows.

## Matriz de capacidades

| Familia | Extensiones | Prioridad | Estado actual | Adaptador previsto |
|---|---|---:|---|---|
| Excel | `.xlsx` | actual | `implemented` | `excel` |
| PDF | `.pdf` | actual | `implemented` | `pdf` |
| Delimitados | `.csv`, `.tsv` | fase 1 | `implemented` | `delimited` |
| XML UBL | `.xml` | fase 1 | `planned` | `ubl_xml` |
| Imágenes | `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.webp` | fase 1 | `implemented` | `image_document` |
| JSON | `.json`, `.ndjson`, `.jsonl` | fase 1 | `implemented` | `json_records` |
| Correo exportado | `.eml`, `.mbox` | fase 2 | `planned` | `email_archive` |
| Lotes comprimidos | `.zip` | fase 2 | `planned` | `archive` |
| Documentos ofimáticos | `.docx`, `.odt` | fase 2 | `planned` | `office_document` |
| Movimientos bancarios | `.ofx`, `.qfx`, `.mt940`, `.camt.053.xml` | fase 3 | `out of scope` | `bank_statement` |
| Analítico interno | `.parquet` | fase 3 | `out of scope` | `parquet` |

## Orden de implementación

1. CSV y TSV — implementado.
2. JSON y NDJSON — implementado.
3. Imágenes documentales reutilizando OCR — implementado.
4. XML UBL.
5. EML y MBOX.
6. ZIP con manifiesto.
7. DOCX y ODT.

## Regla de finalización

Un formato solo pasa a `implemented` cuando cuenta con contrato, fixtures, validación de estructura, procedencia, límites de seguridad, pruebas de éxito/error/regresión y documentación reproducible en Linux y Windows cuando aplique.


## CSV y TSV implementados

El adaptador exige un perfil explícito de entidad y registra la configuración efectiva. Soporta UTF-8 y UTF-8 con BOM, delimitadores coma, punto y coma, tabulador y barra vertical, fechas configurables, separador decimal configurable, límites de tamaño/filas/columnas/campo y procedencia por registro y columna. No intenta aceptar codificaciones heredadas ni configuraciones ambiguas de manera silenciosa.

## JSON y NDJSON implementados

El adaptador `json_records` exige un perfil de entidad y una versión compatible. JSON admite objeto único, arreglo y lote versionado. NDJSON procesa un objeto por línea, conserva el número de línea y permite aislar registros inválidos. Se rechazan claves duplicadas, números no finitos, estructuras profundas, campos inesperados y límites excedidos. La procedencia usa JSON Pointer, número de registro, línea cuando corresponde, valor raw, hash y metadatos del perfil.


## Imágenes documentales implementadas

El adaptador `image_document` valida la firma real frente a la extensión, tamaño, dimensiones, píxeles, cantidad de frames y orientación. Acepta una sola imagen por archivo en JPG/JPEG, PNG, TIFF o WebP. Reutiliza Tesseract, clasificación documental, extracción estructurada, reglas de totales y procedencia por región. Las imágenes con orientación distinta de 1, múltiples frames o límites excedidos se rechazan de forma explícita en lugar de transformarse silenciosamente.
