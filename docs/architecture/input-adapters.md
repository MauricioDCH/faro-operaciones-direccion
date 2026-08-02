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
- JSON y NDJSON deben exigir versión de contrato cuando alimenten entidades operativas.
- Toda salida debe conservar ubicación específica de la fuente.
- Los adaptadores deben ser independientes del sistema operativo.
