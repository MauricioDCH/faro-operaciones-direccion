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
| Delimitados | `.csv`, `.tsv` | fase 1 | `planned` | `delimited` |
| XML UBL | `.xml` | fase 1 | `planned` | `ubl_xml` |
| Imágenes | `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.webp` | fase 1 | `planned` | `image_document` |
| JSON | `.json`, `.ndjson`, `.jsonl` | fase 1 | `planned` | `json_records` |
| Correo exportado | `.eml`, `.mbox` | fase 2 | `planned` | `email_archive` |
| Lotes comprimidos | `.zip` | fase 2 | `planned` | `archive` |
| Documentos ofimáticos | `.docx`, `.odt` | fase 2 | `planned` | `office_document` |
| Movimientos bancarios | `.ofx`, `.qfx`, `.mt940`, `.camt.053.xml` | fase 3 | `out of scope` | `bank_statement` |
| Analítico interno | `.parquet` | fase 3 | `out of scope` | `parquet` |

## Orden de implementación

1. CSV y TSV.
2. JSON y NDJSON.
3. Imágenes documentales reutilizando OCR.
4. XML UBL.
5. EML y MBOX.
6. ZIP con manifiesto.
7. DOCX y ODT.

## Regla de finalización

Un formato solo pasa a `implemented` cuando cuenta con contrato, fixtures, validación de estructura, procedencia, límites de seguridad, pruebas de éxito/error/regresión y documentación reproducible en Linux y Windows cuando aplique.
