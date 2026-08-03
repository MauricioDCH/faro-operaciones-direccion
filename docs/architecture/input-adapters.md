# Arquitectura de adaptadores de entrada

**Estado:** approved design  
**Fecha:** 2026-08-02

## Principio

Cada formato se procesa mediante un adaptador especializado. El adaptador interpreta la estructura de la fuente, pero entrega registros y evidencia en modelos canónicos compartidos.

```text
archivo raw
  ↓
registro de fuente y hash
  ↓
detección de formato
  ↓
validación estructural
  ↓
adaptador específico
  ↓
modelo canónico + procedencia
  ↓
calidad / normalización / persistencia
```

## Registro de capacidades

`src/faro/ingestion/formats.py` es la fuente ejecutable para conocer:

- identificador del formato;
- extensiones reconocidas;
- tipo MIME esperado;
- fase;
- estado `implemented`, `planned` u `out_of_scope`;
- nombre del adaptador.

El registro no implementa los parsers. Su responsabilidad es evitar listas de extensiones duplicadas y rechazar formatos desconocidos de manera uniforme.

## Interfaz prevista

```python
class InputAdapter(Protocol):
    format_id: str

    def inspect(self, source: SourceFile) -> InspectionResult: ...
    def ingest(self, source: SourceFile) -> IngestionResult: ...
```

## Reglas transversales

- No confiar únicamente en la extensión.
- No modificar el archivo raw.
- Aplicar límites de tamaño, filas, páginas, registros y miembros.
- No ejecutar macros, scripts ni contenido activo.
- XML debe procesarse con configuración segura.
- ZIP debe prevenir traversal, bombas de compresión y anidamiento ilimitado.
- JSON y NDJSON exigen un perfil y versión de contrato explícitos cuando alimentan entidades operativas.
- Toda salida debe conservar ubicación específica de la fuente.
- Los adaptadores deben ser independientes del sistema operativo.


## Adaptador `delimited` implementado

`src/faro/ingestion/delimited.py` implementa CSV y TSV mediante perfiles explícitos. El adaptador valida extensión y contenido, decodifica únicamente UTF-8, detecta o aplica un delimitador aprobado, convierte valores con reglas determinísticas y entrega `TabularRecord`, `IngestionFinding`, `SourceFile` y ubicaciones por registro/campo.

La detección automática solo se permite cuando el encabezado produce un único delimitador plausible. Los límites de archivo, registros, columnas y campo se cargan desde `Settings`. La misma implementación usa `pathlib`, `csv` y APIs estándar de Python, sin rutas específicas de Linux. La ejecución real en Windows seguirá sin marcarse como validada hasta que la matriz de CI correspondiente apruebe.

## Adaptador `json_records` implementado

`src/faro/ingestion/json_records.py` procesa JSON y NDJSON mediante los mismos perfiles canónicos usados por Excel y CSV/TSV. JSON acepta un objeto, un arreglo o un lote con `schema_version`, `profile_id` y `records`. NDJSON procesa un objeto por línea y puede continuar después de una línea inválida.

El adaptador rechaza claves duplicadas, números no finitos, estructuras demasiado profundas, campos inesperados, valores anidados en campos operativos, versiones incompatibles y límites excedidos. Cada campo conserva archivo, número de registro, línea cuando aplica, JSON Pointer, valor original y valor tipado. Los archivos raw se verifican mediante SHA-256 antes y después de la ingesta.

La implementación utiliza únicamente `json`, `pathlib` y otras APIs estándar de Python, por lo que no contiene rutas específicas de Linux o Windows. La compatibilidad oficial de Windows permanece pendiente de la matriz de CI.


## Adaptador `image_document` implementado

`src/faro/ingestion/image_document.py` procesa JPG/JPEG, PNG, TIFF y WebP mediante una página virtual. `src/faro/extraction/image.py` inspecciona firmas y cabeceras sin decodificar ni modificar la fuente. La inspección registra formato, tipo MIME, ancho, alto, píxeles, frames, orientación y tamaño.

El adaptador aplica límites antes del OCR, verifica SHA-256 antes y después y reutiliza `TesseractOcrEngine`, `DocumentClassifier` y `StructuredDocumentExtractor`. La salida usa `DocumentExtraction`, `DocumentPage`, `SourceFile`, `SourceLocation`, `ExtractionResult` y `QualityFinding`.

El MVP acepta solo imágenes de un frame y orientación estándar. Esta restricción evita rotaciones o selección de páginas implícitas que puedan alterar evidencia. La ejecución usa rutas `pathlib` y comandos Python equivalentes en Linux y Windows.
