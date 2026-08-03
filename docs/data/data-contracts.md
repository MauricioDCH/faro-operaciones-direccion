# Contratos de datos

**Estado:** línea base aprobada para implementación
**Versión:** 1.11.0
**Producto:** Faro
**Alcance:** datos sintéticos para desarrollo; fuentes reales solo después de controles de seguridad y privacidad

---

## 1. Objetivo

Este documento define los contratos de entrada y las garantías mínimas de salida de Faro.

La versión actual implementa Excel, PDF, CSV/TSV, JSON/NDJSON, imágenes documentales y XML UBL 2.1. La expansión aprobada conserva como planificados correo exportado, archivos comprimidos y documentos ofimáticos controlados.

---

## 2. Principios

1. Los archivos en `data/raw/` son inmutables.
2. Toda transformación conserva procedencia.
3. Los importes usan decimal o entero en COP; nunca `float`.
4. Las fechas siguen reglas explícitas.
5. Las anomalías se registran en `expected_anomalies.json`.
6. Los registros inválidos no se eliminan silenciosamente.
7. Los resultados asistidos por IA conservan confianza y revisión.
8. Los cambios incompatibles requieren una decisión aprobada.

---

## 3. Estructura de fuentes

```text
data/
├── raw/
│   ├── catalogos.xlsx
│   ├── ventas.xlsx
│   ├── inventario.xlsx
│   ├── pedidos.xlsx
│   └── facturas/
│       └── *.pdf
├── imports/
│   └── plugins/
│       └── email/
│           └── plugin-email-batch.json
├── samples/
│   └── plugin-email-batch.example.json
├── processed/
└── expected/
    └── expected_anomalies.json
```

---

## 4. Convenciones globales

| Elemento | Convención |
|---|---|
| Formato tabular implementado | Excel `.xlsx` |
| Formatos tabulares planificados | CSV `.csv` y TSV `.tsv` |
| Codificación preferida | UTF-8; otras codificaciones requieren perfil explícito |
| Encabezados | obligatorios en la primera fila |
| Fecha | `YYYY-MM-DD` |
| Fecha y hora | ISO 8601 con zona |
| Zona horaria | `America/Bogota` |
| Moneda | `COP` |
| Importes | `decimal(18,2)` |
| Cantidades | `decimal(18,3)` |
| Booleanos | `true` / `false` |
| Valores nulos | celda vacía |
| Idioma | español |
| Fórmulas en archivos raw | no permitidas en campos canónicos |
| Celdas combinadas | no permitidas dentro de las tablas |

Las tablas deben comenzar en `A1`, tener una sola fila de encabezados y no contener subtotales manuales.

---

## 5. Severidad y estado

### Severidad

- `error`: bloquea consolidación;
- `warning`: permite continuar con observación;
- `info`: registra una normalización no bloqueante.

### Estado

- `accepted`;
- `observed`;
- `rejected`;
- `pending_review`.

---

## 6. Catálogo de contratos

| ID | Fuente | Ruta | Hoja | Entidad |
|---|---|---|---|---|
| DC-001 | Catálogo de productos | `catalogos.xlsx` | `productos` | `product` |
| DC-002 | Catálogo de clientes | `catalogos.xlsx` | `clientes` | `customer` |
| DC-003 | Catálogo de proveedores | `catalogos.xlsx` | `proveedores` | `supplier` |
| DC-004 | Ventas | `ventas.xlsx` | `ventas` | `sale_line` |
| DC-005 | Inventario | `inventario.xlsx` | `inventario` | `inventory_snapshot` |
| DC-006 | Pedidos | `pedidos.xlsx` | `pedidos` | `purchase_order_line` |
| DC-007 | Facturas y cotizaciones PDF | `documentos/*.pdf` | no aplica | `document`, `document_page`, `invoice`, `invoice_line`, `quotation`, `quotation_line`, `extraction_result` |
| DC-008 | Lote de correo producido por plugin | `plugin-email-batch.json` | no aplica | `plugin_run`, `email_message`, `extraction_result` |
| DC-009 | Verdad de referencia | `expected_anomalies.json` | no aplica | `expected_anomaly` |
| DC-010 | Archivos delimitados | `tabular/*.{csv,tsv}` | perfil declarado | entidades tabulares aprobadas |
| DC-011 | Documentos electrónicos UBL | `electronic_documents/*.xml` | no aplica | `document`, `invoice`, `invoice_line`, `extraction_result` |
| DC-012 | Imágenes documentales | `document_images/*.{jpg,jpeg,png,tif,tiff,webp}` | no aplica | `document`, `document_page`, `invoice`, `quotation`, `extraction_result` |
| DC-013 | JSON y NDJSON versionados | `imports/structured/*.{json,ndjson,jsonl}` | no aplica | lote o evento según esquema |
| DC-014 | Correo exportado | `imports/email/*.{eml,mbox}` | no aplica | `email_message`, `extraction_result` |
| DC-015 | Lote comprimido | `imports/batches/*.zip` | manifiesto | fuentes contenidas permitidas |
| DC-016 | Documento administrativo | `documents/*.{docx,odt}` | no aplica | `document`, `document_page`, `extraction_result` |
| DC-017 | Almacén operacional unificado | `data/processed/faro.db` | no aplica | entidades canónicas, observaciones, procedencia, hallazgos y transformaciones |

---

## 6.1 Implementación tabular actual

La ingesta Excel está implementada mediante un lector determinístico de archivos `.xlsx` basado en la biblioteca estándar. No ejecuta macros ni fórmulas y no modifica las fuentes.

Garantías de la implementación:

- valida la presencia de los cuatro libros y seis hojas aprobadas;
- valida encabezados obligatorios y duplicados;
- convierte cadenas, booleanos, decimales y fechas de Excel;
- registra archivo, hoja, fila, columna y referencia de celda;
- valida claves únicas, rangos, fórmulas de línea e integridad referencial;
- conserva el valor raw junto al valor tipado;
- compara el hash SHA-256 antes y después de la ingesta;
- produce hallazgos estructurados con código, regla, severidad y ubicación.

La salida técnica de esta etapa es `ExcelIngestionBatch`, compuesto por `TabularRecord`, `SpreadsheetSourceLocation` e `IngestionFinding`. Los registros aceptados pueden ingresar al almacén operacional DC-017.

---

## 7. DC-001 — Productos

**Libro:** `data/raw/catalogos.xlsx`
**Hoja:** `productos`
**Granularidad:** una fila por producto.

| Campo | Regla |
|---|---|
| `product_id` | único y obligatorio |
| `sku` | único y obligatorio |
| `product_name` | no vacío |
| `category` | catálogo aprobado |
| `unit` | catálogo aprobado |
| `unit_cost_cop` | mayor o igual a cero |
| `sale_price_cop` | mayor o igual a cero |
| `active` | booleano |

Un identificador duplicado genera `error`. Un precio inferior al costo genera `warning`.

---

## 8. DC-002 — Clientes

**Libro:** `data/raw/catalogos.xlsx`
**Hoja:** `clientes`
**Granularidad:** una fila por cliente.

Campos obligatorios:

- `customer_id`;
- `customer_name`;
- `customer_type`;
- `city`;
- `active`.

Campos opcionales:

- `tax_id`;
- `email`;
- `phone`.

Un identificador duplicado genera `error`. Los contactos son sintéticos.

---

## 9. DC-003 — Proveedores

**Libro:** `data/raw/catalogos.xlsx`
**Hoja:** `proveedores`
**Granularidad:** una fila por proveedor.

Campos obligatorios:

- `supplier_id`;
- `supplier_name`;
- `city`;
- `active`.

Campos opcionales:

- `tax_id`;
- `email`;
- `phone`.

Las variantes deliberadas de nombre se conservan en raw y se registran como anomalías.

---

## 10. DC-004 — Ventas

**Libro:** `data/raw/ventas.xlsx`
**Hoja:** `ventas`
**Granularidad:** una fila por línea de venta.

Campos obligatorios:

- `sale_id`;
- `sale_line_id`;
- `sale_date`;
- `customer_id`;
- `product_id`;
- `quantity`;
- `unit_price_cop`;
- `discount_cop`;
- `line_total_cop`;
- `channel`.

Fórmula:

```text
line_total_cop = quantity * unit_price_cop - discount_cop
```

Reglas:

- `sale_line_id` es único;
- `sale_id` puede repetirse en ventas multilínea;
- cliente y producto deben existir;
- cantidad debe ser mayor que cero;
- el total debe coincidir dentro de la tolerancia configurada.

---

## 11. DC-005 — Inventario

**Libro:** `data/raw/inventario.xlsx`
**Hoja:** `inventario`
**Granularidad:** una fila por producto y fecha de corte.

Campos obligatorios:

- `snapshot_date`;
- `product_id`;
- `stock_on_hand`;
- `committed_quantity`;
- `reorder_point`.

Campo derivado:

```text
available_quantity = stock_on_hand - committed_quantity
```

Clave lógica:

```text
(snapshot_date, product_id)
```

El riesgo de inventario se calcula de forma determinística.

---

## 12. DC-006 — Pedidos

**Libro:** `data/raw/pedidos.xlsx`
**Hoja:** `pedidos`
**Granularidad:** una fila por línea de pedido.

Campos obligatorios:

- `order_id`;
- `order_line_id`;
- `order_date`;
- `supplier_id`;
- `product_id`;
- `ordered_quantity`;
- `expected_unit_cost_cop`;
- `status`.

Campos opcionales:

- `expected_delivery_date`;
- `source_message_id`;
- `notes`.

Proveedor y producto deben existir. La fecha esperada no puede ser anterior a la fecha del pedido.

---

## 13. DC-007 — Facturas y cotizaciones PDF

**Directorio canónico:** `data/raw/documentos/`
**Compatibilidad temporal:** `data/raw/facturas/` se acepta mientras se migra el generador sintético.

**Implementación actual:** Poppler y Tesseract recuperan texto; un parser determinístico versionado extrae los campos aprobados y valida líneas y totales. El contrato permanece independiente de esas herramientas.

### Tipos documentales

- `invoice`;
- `quotation`;
- `unsupported`.

### Variantes de entrada

- PDF con texto nativo;
- PDF completamente escaneado;
- PDF mixto con páginas nativas y escaneadas.

### Límites del MVP

- documentos sintéticos;
- idioma español;
- una a tres páginas;
- texto impreso legible;
- plantillas conocidas o variaciones controladas;
- sin contraseña;
- sin manuscritos complejos.

### Selección de método por página

Cada página debe registrar una de estas rutas:

- `native_text`;
- `ocr`;
- `unsupported`.

La extracción nativa tiene prioridad cuando produce texto suficiente. El umbral de suficiencia debe ser determinístico y configurable.

Cuando se utilice OCR deben registrarse:

- `ocr_engine`;
- `ocr_engine_version`;
- `ocr_language`;
- `ocr_confidence` cuando esté disponible;
- `render_dpi`;
- `page_text`;
- región o fragmento de evidencia;
- estado de revisión.

### Campos comunes del documento

- `document_id`;
- `document_type`;
- `source_file_id`;
- `page_count`;
- `processing_status`;
- `classification_method`;
- `classification_confidence`;
- `record_status`.

### Factura

Campos de cabecera:

- `invoice_id`;
- `invoice_number`;
- `supplier_name_raw`;
- `supplier_id`;
- `issue_date`;
- `related_order_id`;
- `currency`;
- `subtotal_cop`;
- `tax_cop`;
- `total_cop`.

Campos por línea:

- `invoice_line_id`;
- `product_name_raw`;
- `product_id`;
- `quantity`;
- `unit_price_cop`;
- `line_total_cop`.

Reglas:

- `total_cop` debe coincidir con `subtotal_cop + tax_cop` dentro de la tolerancia;
- cada línea debe conservar página y evidencia;
- las correspondencias inciertas requieren revisión;
- el duplicado se evalúa, como mínimo, con proveedor, número y fecha.

### Cotización

Campos de cabecera:

- `quotation_id`;
- `quotation_number`;
- `supplier_name_raw`;
- `supplier_id`;
- `issue_date`;
- `valid_until`;
- `currency`;
- `subtotal_cop`;
- `tax_cop`;
- `total_cop`.

Campos por línea:

- `quotation_line_id`;
- `product_name_raw`;
- `product_id`;
- `quantity`;
- `unit_price_cop`;
- `line_total_cop`.

Reglas:

- `valid_until`, cuando exista, no puede ser anterior a `issue_date`;
- los totales deben validarse determinísticamente;
- una cotización no se trata como factura ni modifica inventario o cuentas;
- toda correspondencia incierta requiere revisión.

### Manejo de fallos

- documento no soportado: `rejected`;
- página ilegible: `pending_review`;
- clasificación incierta: `pending_review`;
- campo sin evidencia: no se consolida;
- OCR sin versión identificable: `error`;
- fuente original: inmutable.

### Salida

Entidades lógicas `document`, `document_page`, `invoice`, `invoice_line`, `quotation`, `quotation_line` y `extraction_result`.

---

## 14. DC-008 — Lote de correo producido por plugin

**Archivo importado:** `data/imports/plugins/email/plugin-email-batch.json`
**Esquema:** `schemas/plugin-email-batch.schema.json`
**Ejemplo:** `data/samples/plugin-email-batch.example.json`

### Propósito

El lote es la frontera portable entre ChatGPT o Claude y el núcleo local de Faro. El plugin consulta Gmail; la IA clasifica y extrae; Faro valida y consolida.

### Reglas globales

- El usuario no carga `.eml`.
- La cuenta fuente contiene únicamente datos sintéticos.
- La ejecución es de solo lectura.
- El archivo debe contener JSON puro, sin Markdown.
- `schema_version` debe ser compatible.
- El artefacto importado es inmutable.
- Cada mensaje debe conservar una referencia verificable.
- Los campos desconocidos se representan con `null`.
- La IA no debe inventar identificadores, cantidades ni fechas.
- La confianza debe estar entre 0 y 1.
- Las extracciones inciertas quedan `pending`.

### Cabecera obligatoria

- `schema_version`;
- `batch_id`;
- `platform`;
- `plugin_name`;
- `source_app`;
- `account_label`;
- `query`;
- `prompt_version`;
- `generated_at`;
- `messages`;
- `limitations`.

### Plataformas admitidas

- `chatgpt`;
- `claude`.

### Aplicación fuente del MVP

- `gmail`.

### Mensaje

Cada elemento de `messages` debe incluir:

- `source_reference`;
- `from_address`;
- `to_addresses`;
- `subject`;
- `sent_at`;
- `body_excerpt`;
- `event_type`;
- `extractions`.

Son opcionales:

- `provider_message_id`;
- `thread_id`;
- `source_url`.

### Extracción

Cada extracción debe incluir:

- `field`;
- `raw_value`;
- `proposed_value`;
- `confidence`;
- `evidence_excerpt`;
- `review_status`.

### Referencia de origen

`source_reference` debe ser una cita, enlace o localizador proporcionado por la integración. Cuando la plataforma no exponga un identificador estable, se acepta un localizador compuesto por fecha, remitente y asunto, y debe registrarse la limitación correspondiente.

### Validaciones de Faro

Faro debe:

1. validar JSON y versión;
2. comprobar valores enumerados;
3. detectar mensajes repetidos dentro del lote y entre lotes;
4. verificar pedidos, productos y proveedores contra el modelo canónico;
5. bloquear campos sin evidencia;
6. enviar a revisión las propuestas de baja confianza;
7. preservar el lote y registrar su hash;
8. diferenciar una ejecución real de un fixture.

### Salida

Entidades lógicas `plugin_run`, `email_message`, `extraction_result` y, después de validación, eventos operativos asociados.

---

## 15. DC-009 — Verdad de referencia

**Archivo:** `data/expected/expected_anomalies.json`

Estructura mínima:

```json
{
  "schema_version": "1.0.0",
  "dataset_version": "0.1.0",
  "seed": 20260731,
  "anomalies": [
    {
      "anomaly_id": "ANOM-001",
      "type": "duplicate_invoice",
      "severity": "error",
      "source_file": "facturas/factura_008.pdf",
      "source_record_ids": ["INV-000004", "INV-000008"],
      "expected_rule_id": "RULE-DUP-INVOICE-001",
      "expected_detected": true
    }
  ]
}
```

---

## 16. Procedencia

### Excel

```json
{
  "source_type": "xlsx",
  "file_path": "data/raw/ventas.xlsx",
  "sheet": "ventas",
  "row": 12,
  "column": "product_id",
  "cell_reference": "E12",
  "raw_value": "PRD-0008"
}
```

### PDF nativo u OCR

```json
{
  "source_type": "pdf",
  "file_path": "data/raw/facturas/factura_008.pdf",
  "page": 1,
  "extraction_method": "ocr",
  "ocr_engine": "configured-engine",
  "ocr_engine_version": "pinned-version",
  "field": "invoice_number",
  "text_excerpt": "Factura No. FV-1008"
}
```

### Correo consultado mediante plugin

```json
{
  "source_type": "ai_plugin",
  "plugin_run_id": "PLGRUN-000001",
  "platform": "chatgpt",
  "plugin_name": "gmail",
  "source_reference": "gmail-citation:message-004",
  "source_url": null,
  "section": "body",
  "text_excerpt": "Por favor envíen solamente 20 unidades."
}
```

---

## 17. Garantías de salida

La capa procesada debe garantizar:

1. nombres canónicos;
2. tipos normalizados;
3. identificadores estables;
4. procedencia;
5. transformaciones registradas;
6. cálculos determinísticos;
7. separación entre valor original, propuesto y aprobado;
8. estado de validación;
9. archivos raw inmutables;
10. compatibilidad con indicadores y alertas.

---

## 18. Criterios de aceptación

Los contratos quedan listos cuando:

1. todos los campos aparecen en el diccionario;
2. cada libro tiene hojas, columnas y reglas definidas;
3. las claves y relaciones son verificables;
4. la procedencia puede representarse;
5. la confianza y revisión están modeladas;
6. la verdad de referencia es estable;
7. pueden construirse fixtures válidos e inválidos;
8. no existen contradicciones con alcance, requisitos o casos de uso;
9. el lote del plugin valida contra el JSON Schema;
10. la salida real y el fixture usan exactamente el mismo contrato;
11. los documentos nativos, escaneados y mixtos pueden representarse por página;
12. factura y cotización tienen contratos separados;
13. los metadatos OCR permiten reproducir y auditar la extracción;
14. los cuatro libros y seis hojas Excel se validan con tipos y reglas determinísticas;
15. cada campo tabular conserva archivo, hoja, fila, columna, celda y valor raw;
16. los hashes de los archivos Excel permanecen sin cambios durante la ingesta;
17. CSV y TSV validan perfil, contenido, límites y configuración efectiva;
18. cada campo delimitado conserva registro, fila, columna, valor raw y valor tipado;
19. los hashes de CSV y TSV permanecen sin cambios durante la ingesta;
20. JSON y NDJSON validan perfil, versión, límites y tipos;
21. cada campo JSON conserva JSON Pointer y cada registro NDJSON conserva línea;
22. los hashes JSON y NDJSON permanecen sin cambios durante la ingesta.

---

## 19. DC-010 — CSV y TSV

**Estado:** `implemented`

**Ruta recomendada:** `data/raw/tabular/*.{csv,tsv}`

**Adaptador:** `delimited`

### Perfiles aprobados

- `products` → DC-001 / `product`;
- `customers` → DC-002 / `customer`;
- `suppliers` → DC-003 / `supplier`;
- `sales` → DC-004 / `sale_line`;
- `inventory` → DC-005 / `inventory_snapshot`;
- `orders` → DC-006 / `purchase_order_line`.

### Configuración explícita

Cada fuente declara o resuelve en un perfil materializado:

- formato `csv` o `tsv`;
- codificación `utf-8` o `utf-8-sig`;
- delimitador `,`, `;`, tabulador o `|`;
- modo `auto` únicamente para detectar el delimitador desde un encabezado no ambiguo;
- separador decimal `.` o `,`;
- separador de miles opcional;
- formato de fecha;
- entidad objetivo y contrato.

No se aceptan silenciosamente UTF-16, codificaciones heredadas, perfiles desconocidos, encabezados ambiguos ni extensiones que contradigan el perfil.

### Validación

El adaptador valida:

- contenido UTF-8 real y ausencia de bytes NUL;
- tamaño máximo del archivo;
- máximo de registros, columnas y caracteres por campo;
- encabezados obligatorios, únicos y adicionales;
- ancho de cada registro;
- conversión de cadenas, booleanos, fechas y decimales;
- mínimos y catálogos permitidos;
- duplicados, fórmulas operativas e integridad referencial cuando el lote incluye o exige catálogos;
- hash SHA-256 antes y después de la ingesta.

### Procedencia

Cada registro conserva `source_file_id`, `record_number`, fila física, `source_location_id` y estado. Cada campo conserva columna, valor raw, valor tipado y ubicación determinística. La configuración efectiva queda en `source_file.format_metadata`.

### Comportamiento de error

Un error de fuente produce un hallazgo estructurado y no altera el archivo raw. Un registro mal formado o con error de datos queda `rejected`; los demás registros del lote pueden continuar. La validación de referencias puede omitirse explícitamente cuando los catálogos todavía no formen parte del lote, pero nunca se omite de manera implícita en una consolidación estricta.

## 20. DC-011 — XML UBL

**Estado:** `implemented`
**Ruta canónica:** `data/raw/electronic_documents/*.xml`
**Versión soportada:** UBL `2.1`

### Documentos admitidos

- `Invoice` como raíz;
- `AttachedDocument` con un único `Invoice` embebido como XML escapado, elemento XML o contenido base64 XML.

Notas crédito, notas débito, respuestas de aplicación y otros documentos UBL permanecen fuera del alcance.

### Seguridad y límites

- rechazo de `DOCTYPE` y declaraciones `ENTITY`;
- ausencia de resolución de entidades o recursos externos;
- límites configurables de tamaño, elementos, profundidad y texto;
- raíz y `UBLVersionID` obligatorios y permitidos;
- contenido real validado, no solo extensión `.xml`;
- hash SHA-256 antes y después.

### Mapeo canónico

La factura produce `document`, `invoice` e `invoice_line`. Se extraen número, fecha, moneda, referencia de pedido, proveedor, cliente, líneas, impuestos, subtotal y total pagadero. Los identificadores externos se conservan como aparecen y su homologación con catálogos internos queda a cargo de normalización.

### Procedencia

Cada campo conserva `source_file_id`, `source_location_id`, XPath lógico, nombre canónico y valor raw. En `AttachedDocument`, el XPath incluye la ubicación del contenedor y el segmento `embedded-document`.

### Validación determinística

- campos obligatorios;
- fechas ISO;
- decimales finitos;
- cantidad positiva;
- total por línea;
- suma de líneas frente a subtotal;
- subtotal más impuestos frente al total;
- coherencia entre `DocumentCurrencyCode` y `currencyID`;
- moneda `COP` para los campos monetarios canónicos actuales.

La validación jurídica, firma digital, CUFE, consulta DIAN y XSD oficial completo están fuera del alcance.


## 21. DC-012 — Imágenes documentales

**Estado:** `implemented`
**Ruta canónica:** `data/raw/document_images/*.{jpg,jpeg,png,tif,tiff,webp}`

### Formatos y límites

- JPG/JPEG, PNG, TIFF y WebP;
- una imagen o frame por archivo;
- firma binaria coherente con la extensión;
- orientación estándar `1`;
- tamaño, ancho, alto y cantidad de píxeles configurables;
- archivo raw inmutable y hash SHA-256 antes y después.

### Metadatos obligatorios

- `source_type=image`;
- `detected_format`;
- `media_type_detected`;
- ancho, alto, píxeles, frames y orientación;
- adaptador `image_document`;
- motor, versión, idioma y confianza OCR;
- región de evidencia en coordenadas de imagen.

### Procesamiento

Cada archivo produce una página virtual `document_page` con `page_number=1` y `extraction_method=ocr`. Después del OCR se reutilizan clasificación, extracción de factura/cotización, validación de líneas y totales, y revisión humana por baja confianza.

### Rechazos controlados

- firma y extensión inconsistentes;
- formato desconocido;
- archivo vacío;
- dimensiones o píxeles fuera de límites;
- TIFF con múltiples frames;
- orientación distinta de `1`;
- OCR deshabilitado o no disponible;
- texto vacío o confianza insuficiente.

Ningún rechazo modifica el archivo original ni inventa campos.


## 22. DC-013 — JSON y NDJSON

**Estado:** `implemented`

**Ruta recomendada:** `data/raw/imports/structured/*.{json,ndjson,jsonl}`
**Adaptador:** `json_records`
**Versión soportada:** `1.0.0`

### Perfiles aprobados

- `products` → DC-001 / `product`;
- `customers` → DC-002 / `customer`;
- `suppliers` → DC-003 / `supplier`;
- `sales` → DC-004 / `sale_line`;
- `inventory` → DC-005 / `inventory_snapshot`;
- `orders` → DC-006 / `purchase_order_line`.

### Formas JSON aceptadas

1. objeto único, con perfil y versión declarados por la ejecución;
2. arreglo de objetos, con perfil y versión declarados por la ejecución;
3. lote versionado:

```json
{
  "schema_version": "1.0.0",
  "profile_id": "products",
  "records": []
}
```

Un registro puede declarar `_schema_version` y `_profile_id`; cuando aparecen deben coincidir con el perfil de la ejecución.

### NDJSON

Cada línea no vacía contiene exactamente un objeto JSON. Una línea inválida produce un hallazgo localizable y no impide procesar las demás líneas. Se conservan número de registro y número de línea.

### Validaciones y límites

- UTF-8 o UTF-8 con BOM;
- rechazo de claves duplicadas;
- rechazo de `NaN`, `Infinity` y valores no finitos;
- límite de tamaño, registros, profundidad, campos y longitud de cadenas;
- objeto por registro;
- campos canónicos escalares;
- campos inesperados rechazados;
- versión y perfil compatibles;
- tipos, campos obligatorios, rangos, catálogos e integridad referencial;
- hashes raw verificados antes y después.

### Procedencia

Cada registro y campo conserva:

- `source_file_id`;
- `record_number`;
- `line` para NDJSON;
- `json_pointer` conforme a RFC 6901;
- nombre de campo;
- valor raw estable;
- valor tipado;
- perfil y versión efectivos.

### Comportamiento de error

Un JSON sintácticamente inválido, una versión incompatible o un límite global excedido produce estado `failed`. En NDJSON, una línea inválida queda registrada como error del registro y las demás líneas pueden continuar. Ningún caso modifica el archivo de origen.

## 23. DC-014 — EML y MBOX

**Estado:** `planned`

Se conservan `Message-ID`, remitente, destinatarios, asunto, fecha, cuerpo, adjuntos y ubicación dentro del buzón. Los adjuntos siguen su propio contrato y hash.

## 24. DC-015 — ZIP controlado

**Estado:** `planned`

El lote requiere límites de miembros, profundidad y tamaño expandido. Se rechazan rutas absolutas, traversal, enlaces y formatos no permitidos. Cada miembro conserva hash y ruta relativa dentro del archivo.

## 25. DC-016 — DOCX y ODT

**Estado:** `planned`

Solo se extrae contenido textual y estructural controlado. No se ejecutan macros, scripts, enlaces externos ni contenido activo. La procedencia usa sección, párrafo, tabla y celda cuando estén disponibles.

## 26. Garantías comunes para nuevos adaptadores

1. La extensión no es prueba suficiente del formato.
2. El archivo raw permanece inmutable.
3. El adaptador y su versión quedan registrados.
4. La procedencia debe ser específica al formato.
5. Los límites de tamaño y recursos son obligatorios.
6. Los errores son estructurados y localizables.
7. Las capacidades `planned` no se aceptan como implementadas.

---

## 22. DC-017 — Almacén operacional unificado

**Ruta:** `data/processed/faro.db`
**Motor:** SQLite
**Versión del esquema:** `1.0.0`

### Garantías

- se construye en un archivo temporal y se reemplaza de forma atómica;
- solo observaciones `accepted` pueden poblar tablas canónicas;
- observaciones rechazadas o pendientes permanecen fuera de las tablas operativas;
- cada registro canónico conserva `source_file_id` y `source_location_id`;
- cada observación conserva formato, prioridad, payload y hash;
- cada selección canónica genera `transformation_event`;
- los conflictos entre fuentes producen `quality_finding`;
- se ejecutan claves foráneas e `integrity_check`;
- el archivo SQLite no se versiona; se reconstruye desde fuentes inmutables;
- la reproducibilidad se compara mediante `logical_content_hash`.

### Tablas de auditoría

- `metadata`;
- `source_file`;
- `source_location`;
- `record_observation`;
- `quality_finding`;
- `transformation_event`;
- `extraction_result`.

### Tablas canónicas

- `product`;
- `customer`;
- `supplier`;
- `sale_line`;
- `inventory_snapshot`;
- `purchase_order_line`;
- `document`;
- `document_page`;
- `invoice`;
- `invoice_line`;
- `quotation`;
- `quotation_line`.

### Reglas de consolidación

1. La clave de negocio identifica observaciones equivalentes.
2. Se elige la observación aceptada con mayor prioridad de fuente.
3. Un duplicado equivalente genera una advertencia.
4. Un desacuerdo genera un error trazable, pero no elimina la observación alternativa.
5. Una reconstrucción fallida no reemplaza la base válida anterior.
---

## 23. DC-018 — Configuración y resultados de indicadores

**Configuración:** `config/indicators.yaml`
**Esquema de configuración:** `1.0.0`
**Estado:** `implemented`

### Configuración

- la empresa selecciona un `active_preset` o utiliza `--preset`;
- cada preset contiene indicadores de un catálogo aprobado;
- solo se aceptan parámetros conocidos, tipados y limitados;
- no se permite SQL, código ni expresiones arbitrarias;
- el archivo usa sintaxis JSON compatible con YAML y se valida sin dependencias externas.

### Resultados

Las tablas `indicator_run` e `indicator_result` conservan preset, hash de configuración, hash lógico de la base, fecha de corte, versión de fórmula, valor, unidad, registros y ubicaciones fuente.

El valor numérico se calcula con `Decimal` y lógica determinística. Los resultados derivados no alteran el `logical_content_hash` del almacén operacional.
