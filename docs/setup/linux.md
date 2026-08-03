
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
