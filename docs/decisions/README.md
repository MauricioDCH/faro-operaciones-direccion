# Registros de decisiones de arquitectura

Este directorio conserva una decisión material por archivo mediante el formato:

```text
NNNN-titulo-breve-de-la-decision.md
```

El archivo `README.md` define la convención y funciona como índice. No reemplaza los ADR individuales.

## Estados permitidos

- `proposed`
- `accepted`
- `superseded`
- `rejected`

## Secciones obligatorias

Cada ADR debe incluir:

- estado;
- fecha;
- decisores;
- contexto;
- decisión;
- alternativas consideradas;
- consecuencias;
- plan de validación o reversión.

## Cuándo crear un ADR

Debe crearse un ADR cuando un cambio afecte:

- arquitectura;
- interfaces públicas;
- contratos de datos;
- fórmulas de indicadores;
- reglas de alertas;
- procedencia;
- proveedores de modelos o servicios;
- tecnologías principales;
- alcance del MVP;
- comportamiento visible durante la demostración.

## Índice

| ADR | Decisión | Estado |
|---|---|---|
| [`0001-support-scanned-pdf-ocr.md`](0001-support-scanned-pdf-ocr.md) | Soporte OCR para documentos PDF escaneados | `accepted` |
| [`0002-select-local-pdf-ocr-stack.md`](0002-select-local-pdf-ocr-stack.md) | Selección de la pila local para PDF y OCR | `accepted` |
| [`0003-support-linux-and-windows.md`](0003-support-linux-and-windows.md) | Soporte oficial para Linux y Windows | `accepted` |
| [`0004-expand-input-formats.md`](0004-expand-input-formats.md) | Expansión por fases de formatos de entrada | `accepted` |
| [`0005-select-secure-stdlib-ubl-parser.md`](0005-select-secure-stdlib-ubl-parser.md) | Parser UBL seguro basado en biblioteca estándar | `accepted` |
| [`0006-select-sqlite-unified-operational-store.md`](0006-select-sqlite-unified-operational-store.md) | SQLite como almacén operacional unificado | `accepted` |
| [`0007-configurable-alert-presets.md`](0007-configurable-alert-presets.md) | Presets configurables de alertas determinísticas | `accepted` |
| [`0008-safe-incremental-dashboard-updates.md`](0008-safe-incremental-dashboard-updates.md) | Actualizaciones incrementales seguras desde el dashboard | `accepted` |

## Reglas de mantenimiento

- No reescribir una decisión histórica después de ser aceptada.
- Una decisión reemplazada debe conservarse con estado `superseded`.
- El ADR sustituto debe referenciar el ADR anterior.
- Los cambios incompatibles deben actualizar también los documentos canónicos afectados.
- Una capacidad aprobada no se marca como `implemented` hasta cumplir sus criterios de aceptación y pruebas.