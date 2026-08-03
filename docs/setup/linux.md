
# Instalación en Linux

## Requisitos

- Python 3.12 o superior;
- `uv`;
- Tesseract OCR con idioma español;
- Poppler para PDF.

En Ubuntu o Debian:

```bash
sudo apt update
sudo apt install -y poppler-utils tesseract-ocr tesseract-ocr-spa
uv sync --locked
```

## Diagnóstico

```bash
PYTHONPATH=src uv run python scripts/check_ocr_runtime.py
PYTHONPATH=src uv run python -m unittest discover -s tests -p 'test_*.py' -v
```

## Procesar una imagen

```bash
PYTHONPATH=src uv run python scripts/extract_image.py       data/raw/document_images/factura.png
```

El archivo original no se modifica. Faro registra hash, formato detectado, dimensiones, confianza OCR y regiones de evidencia.

## XML UBL

El adaptador UBL no necesita paquetes del sistema adicionales. Ejecución portable:

```text
PYTHONPATH=src uv run python scripts/ingest_ubl_xml.py data/samples/ubl-invoice.example.xml
```

En PowerShell establezca `$env:PYTHONPATH = "src"` y utilice separadores de ruta de Windows. Los límites se configuran con `UBL_MAX_FILE_SIZE_MB`, `UBL_MAX_ELEMENTS`, `UBL_MAX_DEPTH` y `UBL_MAX_TEXT_CHARACTERS`.
