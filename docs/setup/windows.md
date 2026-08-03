
# Instalación en Windows

## Requisitos

- Windows 10 u 11 de 64 bits;
- Python 3.12 o superior;
- `uv`;
- Tesseract OCR con datos de idioma español;
- Poppler para la ruta PDF.

Instala Tesseract y Poppler mediante el mecanismo aprobado por tu organización. Agrega sus ejecutables a `PATH` o define rutas explícitas. Ejemplo en PowerShell:

```powershell
$env:OCR_COMMAND = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:OCR_LANGUAGE = "spa"
$env:PYTHONPATH = "src"
uv sync --locked
```

Verifica el ejecutable y los idiomas:

```powershell
& $env:OCR_COMMAND --version
& $env:OCR_COMMAND --list-langs
uv run python scripts/check_ocr_runtime.py
```

## Procesar una imagen

```powershell
$env:PYTHONPATH = "src"
uv run python scripts/extract_image.py `
  data\raw\document_images\factura.png
```

No es necesario instalar `make`. Usa directamente los comandos `uv run python ...`. Las rutas se procesan mediante `pathlib` y pueden ser relativas o absolutas.

## Diagnóstico de errores

- `OCR command not found`: corrige `OCR_COMMAND` o `PATH`.
- `OCR language is not installed: spa`: instala los datos de idioma español.
- `image_format_mismatch`: la extensión no coincide con la firma real.
- `image_limit_exceeded`: revisa dimensiones, cantidad de píxeles o tamaño.

## XML UBL

El adaptador UBL no necesita paquetes del sistema adicionales. Ejecución portable:

```text
PYTHONPATH=src uv run python scripts/ingest_ubl_xml.py data/samples/ubl-invoice.example.xml
```

En PowerShell establezca `$env:PYTHONPATH = "src"` y utilice separadores de ruta de Windows. Los límites se configuran con `UBL_MAX_FILE_SIZE_MB`, `UBL_MAX_ELEMENTS`, `UBL_MAX_DEPTH` y `UBL_MAX_TEXT_CHARACTERS`.

## Consolidación SQLite

```powershell
$env:PYTHONPATH = "src"
uv run python scripts/consolidate_operations.py
```

La base se genera en `data\processed\faro.db`. SQLite forma parte de Python; no requiere instalar un servidor.
