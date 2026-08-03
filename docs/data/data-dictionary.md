# Diccionario de datos

**Estado:** línea base aprobada para implementación
**Versión:** 1.11.0
**Producto:** Faro
**Alcance:** modelo lógico canónico para datos sintéticos

---

## 1. Objetivo

Este documento define las entidades y campos canónicos utilizados por Faro.

Los formatos de archivo, rutas, granularidad y políticas de compatibilidad se especifican en [`data-contracts.md`](data-contracts.md).

---

## 2. Convenciones

### 2.1 Nombres

- Los nombres técnicos de entidades y campos se escriben en inglés.
- Las fuentes tabulares implementadas utilizan Excel `.xlsx`, CSV `.csv` y TSV `.tsv`.
- Se utiliza `snake_case`.
- Los identificadores terminan en `_id`.
- Los importes en pesos terminan en `_cop`.
- Las fechas terminan en `_date`.
- Las fechas con hora terminan en `_at`.
- Los valores originales de una fuente terminan en `_raw` cuando coexisten con un valor normalizado.

### 2.2 Tipos lógicos

| Tipo | Descripción |
|---|---|
| `string` | texto UTF-8 |
| `integer` | entero |
| `decimal(p,s)` | número decimal exacto |
| `boolean` | `true` o `false` |
| `date` | fecha ISO `YYYY-MM-DD` |
| `datetime` | fecha y hora ISO con zona |
| `enum` | valor perteneciente a un catálogo |
| `json` | estructura JSON válida |
| `list[string]` | lista de textos |

### 2.3 Nulabilidad

- **No:** campo obligatorio.
- **Sí:** campo opcional o no disponible en todas las fuentes.
- Un valor vacío no equivale automáticamente a cero.
- Los valores desconocidos deben ser `null`, no textos como `"N/A"`.

### 2.4 Clasificación de sensibilidad

Todos los datos del MVP son sintéticos.

| Clasificación | Uso |
|---|---|
| `synthetic_non_sensitive` | datos operativos sintéticos |
| `synthetic_contact` | correos, teléfonos o contactos ficticios |
| `technical_metadata` | rutas, hashes, versiones y marcas de tiempo |

---

## 3. Catálogos controlados

### 3.1 `record_status`

- `accepted`
- `observed`
- `rejected`
- `pending_review`

### 3.2 `review_status`

- `not_required`
- `pending`
- `accepted`
- `corrected`
- `rejected`

### 3.3 `severity`

- `info`
- `warning`
- `error`

### 3.4 `order_status`

- `draft`
- `sent`
- `confirmed`
- `partially_received`
- `received`
- `cancelled`

### 3.5 `sales_channel`

- `store`
- `phone`
- `email`
- `whatsapp`
- `web`
- `other`

### 3.6 `email_event_type`

- `new_order`
- `quantity_change`
- `cancellation`
- `delivery_update`
- `supplier_notice`
- `unknown`

### 3.7 `source_type`

- `xlsx`
- `csv`
- `tsv`
- `pdf`
- `image`
- `xml_ubl`
- `json`
- `ndjson`
- `ai_plugin`
- `email_archive`
- `archive`
- `office_document`
- `bank_statement`
- `parquet`

### 3.8 `ai_platform`

- `chatgpt`
- `claude`

### 3.9 `plugin_source_app`

- `gmail`

### 3.10 `document_type`

- `invoice`
- `quotation`
- `unsupported`

### 3.11 `page_extraction_method`

- `native_text`
- `ocr`
- `unsupported`

### 3.12 `document_processing_status`

- `pending`
- `processed`
- `pending_review`
- `rejected`
- `error`

---

## 4. Entidad `source_file`

Representa un archivo o artefacto de entrada registrado por Faro.

| Campo | Tipo | Nulo | Definición y reglas | Clasificación | Ejemplo |
|---|---|---:|---|---|---|
| `source_file_id` | `string` | No | Identificador interno único | `technical_metadata` | `SRC-000001` |
| `file_path` | `string` | No | Ruta relativa del libro, PDF, imagen, artefacto de plugin o JSON | `technical_metadata` | `data/raw/sales.xlsx` |
| `file_name` | `string` | No | Nombre base del archivo | `technical_metadata` | `sales.xlsx` |
| `media_type_declared` | `string` | Sí | Tipo MIME informado por la fuente | `technical_metadata` | `text/csv` |
| `media_type_detected` | `string` | Sí | Tipo MIME detectado o validado | `technical_metadata` | `text/csv` |
| `detected_format` | `string` | Sí | Identificador estable del registro de formatos | `technical_metadata` | `csv` |
| `format_version` | `string` | Sí | Versión del estándar o perfil | `technical_metadata` | `UBL-2.1` |
| `ingestion_adapter` | `string` | Sí | Adaptador responsable | `technical_metadata` | `delimited` |
| `file_size_bytes` | `integer` | Sí | Tamaño raw para límites y auditoría | `technical_metadata` | `18420` |
| `format_metadata` | `json` | Sí | Metadatos específicos: codificación o dimensiones, píxeles, frames y orientación | `technical_metadata` | `{"width":2480,"height":3508,"orientation":1}` |
| `source_type` | `enum` | No | Tipo de fuente aprobado | `technical_metadata` | `xlsx` |
| `contract_id` | `string` | No | Contrato aplicado | `technical_metadata` | `DC-004` |
| `contract_version` | `string` | No | Versión semántica del contrato | `technical_metadata` | `1.0.0` |
| `dataset_version` | `string` | No | Versión del dataset sintético | `technical_metadata` | `0.1.0` |
| `seed` | `integer` | Sí | Semilla de generación | `technical_metadata` | `20260731` |
| `file_hash` | `string` | Sí | Huella criptográfica cuando esté implementada | `technical_metadata` | `sha256:...` |
| `ingested_at` | `datetime` | No | Fecha de registro | `technical_metadata` | `2026-07-31T09:00:00-05:00` |
| `record_status` | `enum` | No | Resultado general de la fuente | `technical_metadata` | `accepted` |

**Consumidores:** ingesta, procedencia, auditoría, dashboard.

---

## 5. Entidad `source_location`

Describe la ubicación exacta de un dato dentro de una fuente.

| Campo | Tipo | Nulo | Definición y reglas | Clasificación | Ejemplo |
|---|---|---:|---|---|---|
| `source_location_id` | `string` | No | Identificador único | `technical_metadata` | `LOC-000001` |
| `source_file_id` | `string` | No | FK a `source_file` o artefacto importado | `technical_metadata` | `SRC-000001` |
| `plugin_run_id` | `string` | Sí | FK a la ejecución del plugin | `technical_metadata` | `PLGRUN-000001` |
| `source_reference` | `string` | Sí | Cita, enlace o localizador del mensaje | `technical_metadata` | `gmail-citation:message-004` |
| `source_url` | `string` | Sí | Enlace expuesto por la integración | `technical_metadata` | `null` |
| `sheet` | `string` | Sí | Hoja de Excel | `technical_metadata` | `sales` |
| `row` | `integer` | Sí | Número de fila visible | `technical_metadata` | `12` |
| `column` | `string` | Sí | Nombre canónico de columna | `technical_metadata` | `product_id` |
| `cell_reference` | `string` | Sí | Referencia visible de celda | `technical_metadata` | `E12` |
| `raw_value` | `string` | Sí | Valor original antes de conversión | `synthetic_non_sensitive` | `PRD-0008` |
| `page` | `integer` | Sí | Página PDF, base 1 | `technical_metadata` | `1` |
| `section` | `string` | Sí | Encabezado, cuerpo u otra sección | `technical_metadata` | `body` |
| `line` | `integer` | Sí | Línea dentro de texto | `technical_metadata` | `3` |
| `field` | `string` | Sí | Campo documental asociado | `technical_metadata` | `invoice_number` |
| `text_excerpt` | `string` | Sí | Fragmento breve de evidencia | `synthetic_non_sensitive` | `Factura No. FV-1008` |
| `bounding_box` | `json` | Sí | Región de evidencia en coordenadas de página | `technical_metadata` | `{"x":120,"y":80,"w":240,"h":40}` |
| `record_number` | `integer` | Sí | Número de registro en CSV, TSV o NDJSON | `technical_metadata` | `18` |
| `line` | `integer` | Sí | Línea física para fuentes NDJSON | `technical_metadata` | `21` |
| `json_pointer` | `string` | Sí | Ubicación RFC 6901 dentro de JSON | `technical_metadata` | `/records/17/amount` |
| `xml_xpath` | `string` | Sí | Ruta lógica dentro de XML | `technical_metadata` | `/Invoice/LegalMonetaryTotal/PayableAmount` |
| `message_id` | `string` | Sí | Identificador del mensaje EML/MBOX | `technical_metadata` | `<msg-001@example.test>` |
| `archive_member` | `string` | Sí | Ruta relativa dentro de ZIP | `technical_metadata` | `invoices/fv-1001.xml` |
| `paragraph` | `integer` | Sí | Párrafo en documento ofimático | `technical_metadata` | `7` |

**Regla:** debe informarse únicamente la ubicación que la fuente permita determinar.

### Ubicación XML UBL

Para `DC-011`, `xml_xpath` es obligatorio en cada campo extraído. `field` contiene el nombre canónico y `raw_value` conserva el texto original. Una factura embebida utiliza una ruta lógica como:

```text
/AttachedDocument/Attachment/ExternalReference/Description/embedded-document/Invoice/LegalMonetaryTotal/PayableAmount
```

La ausencia de número de línea físico no se sustituye con un valor inventado.

**Consumidores:** validación, extracción, alertas, respuestas y auditoría.

---

## 5.1 Resultado técnico de ingesta Excel

`TabularRecord` representa una fila tipada antes de la persistencia consolidada. Conserva:

- `contract_id`;
- `entity_type`;
- `record_id`;
- `source_file_id`;
- `source_location_id` de fila;
- `row_number`;
- `values` tipados;
- `raw_values`;
- `field_locations` por celda;
- `record_status`: `accepted` o `rejected`.

`IngestionFinding` conserva `finding_id`, `rule_id`, `code`, `category`, `severity`, `message`, ubicación, entidad, registro, campo, valor observado y valor esperado.

Estas estructuras son salidas técnicas de la ingesta y no reemplazan las entidades canónicas de las secciones siguientes.

### 5.2 Resultado técnico de ingesta CSV/TSV

`DelimitedIngestionBatch` reutiliza `TabularRecord` e `IngestionFinding` y agrega los perfiles efectivos por fuente. En ubicaciones delimitadas, `record_number` identifica el registro lógico, `row` la fila física observada, `column` el encabezado canónico y `raw_value` el texto previo a conversión. `source_file.format_metadata` conserva perfil, codificación, BOM, delimitador, separadores numéricos y formato de fecha.


### 5.3 Resultado técnico de ingesta JSON/NDJSON

`JsonIngestionBatch` reutiliza los registros canónicos y conserva perfil, versión, número de registro, línea para NDJSON, JSON Pointer, valor raw y valor tipado. Los identificadores de ubicación derivan del hash, registro, línea y pointer.

### 5.4 Resultado técnico de imágenes documentales

`ImageDocumentIngestionService` produce `DocumentExtraction` y una página virtual. `source_file.format_metadata` conserva `width`, `height`, `pixel_count`, `frame_count`, `orientation` y `file_size_bytes`. La evidencia OCR usa `BoundingBox` en coordenadas del archivo original. `document_page_id`, `source_location_id` y `document_id` se derivan del hash y no dependen del sistema operativo.

---

## 6. Entidad `product`

Representa un producto comercializado.

| Campo | Tipo | Nulo | Definición y reglas | Alias de fuente | Ejemplo |
|---|---|---:|---|---|---|
| `product_id` | `string` | No | Identificador único | `id_producto`, `producto_id` | `PRD-0001` |
| `sku` | `string` | No | Código comercial único | `codigo`, `referencia` | `CAF-500` |
| `product_name` | `string` | No | Nombre canónico aprobado | `producto`, `nombre_producto` | `Café molido 500 g` |
| `product_name_raw` | `string` | Sí | Nombre exacto de la fuente | — | `Cafe Molido x500gr` |
| `category` | `string` | No | Categoría aprobada | `categoria` | `Bebidas` |
| `unit` | `enum` | No | Unidad operativa | `unidad`, `unidad_medida` | `unit` |
| `unit_cost_cop` | `decimal(18,2)` | No | Costo unitario no negativo | `costo`, `costo_unitario` | `12500.00` |
| `sale_price_cop` | `decimal(18,2)` | No | Precio de venta no negativo | `precio`, `precio_venta` | `16900.00` |
| `active` | `boolean` | No | Estado del producto | `activo` | `true` |
| `record_status` | `enum` | No | Estado de validación | — | `accepted` |
| `source_location_id` | `string` | No | FK de procedencia | — | `LOC-000010` |

**Clasificación:** `synthetic_non_sensitive`.
**Consumidores:** ventas, inventario, pedidos, facturas, indicadores y alertas.

---

## 7. Entidad `customer`

Representa un cliente sintético.

| Campo | Tipo | Nulo | Definición y reglas | Alias de fuente | Ejemplo |
|---|---|---:|---|---|---|
| `customer_id` | `string` | No | Identificador único | `id_cliente`, `cliente_id` | `CUS-0001` |
| `customer_name` | `string` | No | Nombre sintético | `cliente`, `nombre_cliente` | `Tienda Laureles` |
| `customer_type` | `enum` | No | `retail`, `business` o `internal` | `tipo_cliente` | `business` |
| `tax_id` | `string` | Sí | Identificador tributario ficticio | `nit`, `documento` | `900000001-1` |
| `city` | `string` | No | Ciudad | `ciudad` | `Medellín` |
| `email` | `string` | Sí | Correo sintético válido | `correo` | `compras@tiendalaureles.example` |
| `phone` | `string` | Sí | Teléfono ficticio | `telefono` | `3000000001` |
| `active` | `boolean` | No | Estado del cliente | `activo` | `true` |
| `record_status` | `enum` | No | Estado de validación | — | `accepted` |
| `source_location_id` | `string` | No | FK de procedencia | — | `LOC-000020` |

**Clasificación:** campos de contacto `synthetic_contact`; demás campos `synthetic_non_sensitive`.
**Consumidores:** ventas, indicadores y trazabilidad.

---

## 8. Entidad `supplier`

Representa un proveedor sintético.

| Campo | Tipo | Nulo | Definición y reglas | Alias de fuente | Ejemplo |
|---|---|---:|---|---|---|
| `supplier_id` | `string` | No | Identificador único | `id_proveedor`, `proveedor_id` | `SUP-0001` |
| `supplier_name` | `string` | No | Nombre canónico aprobado | `proveedor`, `razon_social` | `Distribuciones Andinas SAS` |
| `supplier_name_raw` | `string` | Sí | Nombre exacto de la fuente | — | `Distribuciones Andinas S.A.S.` |
| `tax_id` | `string` | Sí | Identificador tributario ficticio | `nit` | `900100001-1` |
| `city` | `string` | No | Ciudad | `ciudad` | `Medellín` |
| `email` | `string` | Sí | Correo sintético | `correo` | `ventas@andinas.example` |
| `phone` | `string` | Sí | Teléfono ficticio | `telefono` | `6040000001` |
| `active` | `boolean` | No | Estado del proveedor | `activo` | `true` |
| `record_status` | `enum` | No | Estado de validación | — | `observed` |
| `source_location_id` | `string` | No | FK de procedencia | — | `LOC-000030` |

**Clasificación:** campos de contacto `synthetic_contact`; demás campos `synthetic_non_sensitive`.
**Consumidores:** pedidos, facturas, normalización, indicadores y alertas.

---

## 9. Entidad `sale_line`

Representa una línea de venta.

| Campo | Tipo | Nulo | Definición y reglas | Alias de fuente | Ejemplo |
|---|---|---:|---|---|---|
| `sale_id` | `string` | No | Identificador de transacción | `venta_id`, `factura_venta` | `SAL-000001` |
| `sale_line_id` | `string` | No | Identificador único de línea | `linea_id` | `SALL-000001` |
| `sale_date` | `date` | No | Fecha de venta | `fecha`, `fecha_venta` | `2026-07-01` |
| `customer_id` | `string` | No | FK a cliente | `cliente_id` | `CUS-0001` |
| `product_id` | `string` | No | FK a producto | `producto_id`, `sku` | `PRD-0001` |
| `quantity` | `decimal(18,3)` | No | Cantidad vendida, normalmente mayor que cero | `cantidad` | `3.000` |
| `unit_price_cop` | `decimal(18,2)` | No | Precio unitario | `precio_unitario` | `16900.00` |
| `discount_cop` | `decimal(18,2)` | No | Descuento no negativo | `descuento` | `0.00` |
| `line_total_cop` | `decimal(18,2)` | No | `quantity * unit_price_cop - discount_cop` | `total`, `valor_total` | `50700.00` |
| `channel` | `enum` | No | Canal de venta | `canal` | `store` |
| `record_status` | `enum` | No | Estado de validación | — | `accepted` |
| `source_location_id` | `string` | No | FK de procedencia | — | `LOC-000100` |

**Clasificación:** `synthetic_non_sensitive`.
**Consumidores:** indicadores de ventas, inventario, anomalías y preguntas empresariales.

---

## 10. Entidad `inventory_snapshot`

Representa el inventario de un producto en una fecha.

| Campo | Tipo | Nulo | Definición y reglas | Alias de fuente | Ejemplo |
|---|---|---:|---|---|---|
| `snapshot_date` | `date` | No | Fecha de corte | `fecha`, `fecha_corte` | `2026-07-31` |
| `product_id` | `string` | No | FK a producto | `producto_id`, `sku` | `PRD-0001` |
| `stock_on_hand` | `decimal(18,3)` | No | Existencia física | `existencia`, `stock` | `25.000` |
| `committed_quantity` | `decimal(18,3)` | No | Cantidad comprometida | `reservado`, `comprometido` | `5.000` |
| `available_quantity` | `decimal(18,3)` | No | `stock_on_hand - committed_quantity` | `disponible` | `20.000` |
| `reorder_point` | `decimal(18,3)` | No | Umbral de reposición | `punto_reorden`, `minimo` | `30.000` |
| `record_status` | `enum` | No | Estado de validación | — | `accepted` |
| `source_location_id` | `string` | No | FK de procedencia | — | `LOC-000200` |

**Clave lógica:** `(snapshot_date, product_id)`.
**Clasificación:** `synthetic_non_sensitive`.
**Consumidores:** alertas de inventario, dashboard y preguntas empresariales.

---

## 11. Entidad `purchase_order_line`

Representa una línea de pedido a proveedor.

| Campo | Tipo | Nulo | Definición y reglas | Alias de fuente | Ejemplo |
|---|---|---:|---|---|---|
| `order_id` | `string` | No | Identificador del pedido | `pedido_id` | `ORD-000001` |
| `order_line_id` | `string` | No | Identificador único de línea | `linea_id` | `ORDL-000001` |
| `order_date` | `date` | No | Fecha del pedido | `fecha_pedido` | `2026-07-20` |
| `supplier_id` | `string` | No | FK a proveedor | `proveedor_id` | `SUP-0001` |
| `product_id` | `string` | No | FK a producto | `producto_id`, `sku` | `PRD-0001` |
| `ordered_quantity` | `decimal(18,3)` | No | Cantidad solicitada | `cantidad` | `50.000` |
| `expected_unit_cost_cop` | `decimal(18,2)` | No | Costo esperado | `costo_unitario` | `12500.00` |
| `expected_delivery_date` | `date` | Sí | Fecha prevista | `fecha_entrega` | `2026-07-25` |
| `status` | `enum` | No | Estado del pedido | `estado` | `confirmed` |
| `source_message_id` | `string` | Sí | FK a correo que originó o modificó el pedido | `mensaje_id` | `MSG-000001` |
| `notes` | `string` | Sí | Observación sintética | `observaciones` | `Entrega en la mañana` |
| `record_status` | `enum` | No | Estado de validación | — | `accepted` |
| `source_location_id` | `string` | No | FK de procedencia | — | `LOC-000300` |

**Clasificación:** `synthetic_non_sensitive`.
**Consumidores:** comparación pedido-factura, correos, alertas y dashboard.

---

## 12. Entidad `document`

Representa un PDF o imagen de proveedor antes de materializarlo como factura o cotización.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `document_id` | `string` | No | Identificador interno único | `DOC-000001` |
| `source_file_id` | `string` | No | FK al PDF o imagen original | `SRC-000400` |
| `document_type` | `enum` | No | `invoice`, `quotation` o `unsupported` | `invoice` |
| `page_count` | `integer` | No | Número de páginas, entre 1 y 3 para el MVP | `2` |
| `classification_method` | `string` | No | Regla, heurística o IA | `llm_classification` |
| `classification_confidence` | `decimal(5,4)` | Sí | Confianza entre 0 y 1 | `0.9600` |
| `processing_status` | `enum` | No | Estado del procesamiento documental | `processed` |
| `record_status` | `enum` | No | Estado de validación | `accepted` |

**Consumidores:** extracción, revisión humana, procedencia y dashboard.

---

## 13. Entidad `document_page`

Representa el resultado de inspección y recuperación de texto de una página PDF o página virtual de imagen.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `document_page_id` | `string` | No | Identificador único | `DOCP-000001` |
| `document_id` | `string` | No | FK a `document` | `DOC-000001` |
| `page_number` | `integer` | No | Página base 1 | `1` |
| `extraction_method` | `enum` | No | `native_text`, `ocr` o `unsupported` | `ocr` |
| `native_text_length` | `integer` | No | Longitud detectada antes del OCR | `0` |
| `render_dpi` | `integer` | Sí | Resolución utilizada para OCR | `300` |
| `ocr_engine` | `string` | Sí | Motor de OCR | `configured-engine` |
| `ocr_engine_version` | `string` | Sí | Versión fijada | `pinned-version` |
| `ocr_language` | `string` | Sí | Idioma configurado | `spa` |
| `ocr_confidence` | `decimal(5,4)` | Sí | Confianza agregada cuando esté disponible | `0.9100` |
| `page_text` | `string` | Sí | Texto recuperado | `Factura No. FV-1001...` |
| `processing_status` | `enum` | No | Estado de la página | `processed` |
| `source_location_id` | `string` | No | Procedencia de la página | `LOC-000400` |

**Reglas:**

- el OCR solo se ejecuta cuando el texto nativo es insuficiente;
- motor y versión son obligatorios cuando `extraction_method=ocr`;
- una página ilegible queda `pending_review`;
- el texto recuperado no reemplaza el PDF original.

**Consumidores:** clasificación, extracción, auditoría y revisión humana.

---

## 14. Entidad `invoice`


Representa la cabecera de una factura de proveedor.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `invoice_id` | `string` | No | Identificador interno único | `INV-000001` |
| `document_id` | `string` | No | FK a `document` | `DOC-000001` |
| `invoice_number` | `string` | No | Número visible en el documento | `FV-1001` |
| `supplier_name_raw` | `string` | No | Nombre exacto extraído | `Distribuciones Andinas S.A.S.` |
| `supplier_id` | `string` | Sí | FK resuelta a proveedor | `SUP-0001` |
| `issue_date` | `date` | No | Fecha de emisión | `2026-07-25` |
| `related_order_id` | `string` | Sí | Pedido relacionado | `ORD-000001` |
| `currency` | `enum` | No | Moneda; `COP` para el MVP | `COP` |
| `subtotal_cop` | `decimal(18,2)` | No | Subtotal | `625000.00` |
| `tax_cop` | `decimal(18,2)` | No | Impuestos | `118750.00` |
| `total_cop` | `decimal(18,2)` | No | Total del documento | `743750.00` |
| `record_status` | `enum` | No | Estado de validación | `pending_review` |
| `source_location_id` | `string` | No | Ubicación de la cabecera | `LOC-000400` |

**Regla de duplicado:** proveedor, número de factura y fecha; puede ampliarse mediante decisión.
**Clasificación:** `synthetic_non_sensitive`.
**Consumidores:** duplicados, comparación con pedidos, alertas y trazabilidad.

---

## 15. Entidad `invoice_line`

Representa una línea de factura.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `invoice_line_id` | `string` | No | Identificador único | `INVL-000001` |
| `invoice_id` | `string` | No | FK a factura | `INV-000001` |
| `product_name_raw` | `string` | No | Nombre exacto extraído | `Cafe molido x500` |
| `product_id` | `string` | Sí | FK resuelta a producto | `PRD-0001` |
| `quantity` | `decimal(18,3)` | No | Cantidad facturada | `50.000` |
| `unit_price_cop` | `decimal(18,2)` | No | Precio unitario | `12500.00` |
| `line_total_cop` | `decimal(18,2)` | No | Total de línea | `625000.00` |
| `record_status` | `enum` | No | Estado de validación | `pending_review` |
| `source_location_id` | `string` | No | Página y evidencia | `LOC-000401` |

**Clasificación:** `synthetic_non_sensitive`.
**Consumidores:** comparación pedido-factura, normalización, alertas y trazabilidad.

---

## 16. Entidad `quotation`

Representa la cabecera de una cotización de proveedor.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `quotation_id` | `string` | No | Identificador interno único | `QUO-000001` |
| `document_id` | `string` | No | FK a `document` | `DOC-000002` |
| `quotation_number` | `string` | No | Número visible del documento | `COT-2026-041` |
| `supplier_name_raw` | `string` | No | Nombre exacto extraído | `Distribuciones Andinas S.A.S.` |
| `supplier_id` | `string` | Sí | FK resuelta a proveedor | `SUP-0001` |
| `issue_date` | `date` | No | Fecha de emisión | `2026-07-25` |
| `valid_until` | `date` | Sí | Fecha límite de vigencia | `2026-08-08` |
| `currency` | `enum` | No | `COP` para el MVP | `COP` |
| `subtotal_cop` | `decimal(18,2)` | No | Subtotal | `625000.00` |
| `tax_cop` | `decimal(18,2)` | No | Impuestos | `118750.00` |
| `total_cop` | `decimal(18,2)` | No | Total cotizado | `743750.00` |
| `record_status` | `enum` | No | Estado de validación | `pending_review` |
| `source_location_id` | `string` | No | Evidencia de cabecera | `LOC-000420` |

**Regla:** una cotización informa condiciones propuestas; no se trata como factura ni como movimiento confirmado.

**Consumidores:** comparación de ofertas, revisión humana y trazabilidad.

---

## 17. Entidad `quotation_line`

Representa una línea de cotización.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `quotation_line_id` | `string` | No | Identificador único | `QUOL-000001` |
| `quotation_id` | `string` | No | FK a cotización | `QUO-000001` |
| `product_name_raw` | `string` | No | Nombre exacto extraído | `Cafe molido x500` |
| `product_id` | `string` | Sí | FK resuelta a producto | `PRD-0001` |
| `quantity` | `decimal(18,3)` | No | Cantidad cotizada | `50.000` |
| `unit_price_cop` | `decimal(18,2)` | No | Precio unitario cotizado | `12500.00` |
| `line_total_cop` | `decimal(18,2)` | No | Total de línea | `625000.00` |
| `record_status` | `enum` | No | Estado de validación | `pending_review` |
| `source_location_id` | `string` | No | Página y evidencia | `LOC-000421` |

**Consumidores:** normalización, comparación de ofertas, revisión humana y trazabilidad.

---

## 18. Entidad `plugin_run`

Representa una ejecución delimitada de un plugin o integración de IA sobre Gmail.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `plugin_run_id` | `string` | No | Identificador único de ejecución | `PLGRUN-000001` |
| `batch_id` | `string` | No | Identificador del lote importado | `PLGMAIL-20260731-001` |
| `platform` | `enum` | No | `chatgpt` o `claude` | `chatgpt` |
| `plugin_name` | `string` | No | Plugin o integración utilizada | `gmail` |
| `source_app` | `enum` | No | Aplicación fuente | `gmail` |
| `account_label` | `string` | No | Alias no sensible de la cuenta sintética | `faro-demo-synthetic` |
| `query` | `string` | No | Consulta delimitada ejecutada | `after:2026/07/01 before:2026/08/01` |
| `prompt_version` | `string` | No | Versión del prompt canónico | `1.0.0` |
| `schema_version` | `string` | No | Versión del contrato de salida | `1.0.0` |
| `generated_at` | `datetime` | No | Momento declarado por la ejecución | `2026-07-31T04:00:00-05:00` |
| `imported_at` | `datetime` | No | Momento de importación a Faro | `2026-07-31T04:05:00-05:00` |
| `artifact_hash` | `string` | No | SHA-256 del lote preservado | `sha256:...` |
| `is_fixture` | `boolean` | No | Indica si es contingencia reproducida | `false` |
| `limitations` | `list[string]` | No | Limitaciones declaradas | `[]` |
| `record_status` | `enum` | No | Resultado de validación | `accepted` |

**Consumidores:** auditoría, importación, procedencia, dashboard y evaluación.

---

## 19. Entidad `email_message`

Representa un mensaje sintético consultado mediante un plugin o integración de IA.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `email_message_id` | `string` | No | Identificador interno de Faro | `MSG-000001` |
| `plugin_run_id` | `string` | No | FK a `plugin_run` | `PLGRUN-000001` |
| `provider_message_id` | `string` | Sí | Identificador expuesto por Gmail o la integración | `18f3c1a7` |
| `thread_id` | `string` | Sí | Identificador de hilo cuando esté disponible | `thread-001` |
| `source_reference` | `string` | No | Cita, enlace o localizador verificable | `gmail-citation:message-004` |
| `source_url` | `string` | Sí | Enlace al mensaje cuando la integración lo exponga | `null` |
| `from_address` | `string` | No | Remitente sintético | `ventas@proveedor.example` |
| `to_addresses` | `list[string]` | No | Destinatarios sintéticos | `["compras@faro-demo.example"]` |
| `subject` | `string` | No | Asunto original | `Cambio pedido ORD-000001` |
| `sent_at` | `datetime` | No | Fecha y hora del mensaje | `2026-07-21T08:15:00-05:00` |
| `body_excerpt` | `string` | No | Fragmento mínimo suficiente para evidencia | `Enviar solamente 20 unidades.` |
| `event_type` | `enum` | No | Tipo de evento o `unknown` | `quantity_change` |
| `record_status` | `enum` | No | Estado de validación | `observed` |
| `source_location_id` | `string` | No | FK de procedencia | `LOC-000500` |

**Reglas:**

- el correo completo no es obligatorio en el artefacto;
- no se inventan identificadores ni URLs;
- una referencia insuficiente deja el mensaje `observed`;
- los datos son exclusivamente sintéticos.

**Consumidores:** pedidos, extracción, revisión humana, alertas y trazabilidad.

---

## 20. Entidad `extraction_result`

Representa un campo propuesto por parser, heurística o IA.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `extraction_id` | `string` | No | Identificador único | `EXT-000001` |
| `plugin_run_id` | `string` | Sí | Ejecución del plugin cuando corresponda | `PLGRUN-000001` |
| `source_location_id` | `string` | No | Evidencia de origen | `LOC-000401` |
| `target_entity` | `string` | No | Entidad destino | `invoice_line` |
| `target_field` | `string` | No | Campo destino | `product_id` |
| `raw_value` | `string` | Sí | Valor original | `Cafe molido x500` |
| `proposed_value` | `string` | Sí | Valor propuesto | `PRD-0001` |
| `method` | `string` | No | Parser, OCR, regla, heurística o IA | `llm_mapping` |
| `document_page_id` | `string` | Sí | Página documental cuando corresponda | `DOCP-000001` |
| `ocr_engine` | `string` | Sí | Motor usado para recuperar el texto | `configured-engine` |
| `ocr_engine_version` | `string` | Sí | Versión fijada del motor | `pinned-version` |
| `ocr_confidence` | `decimal(5,4)` | Sí | Confianza OCR del campo o región | `0.9100` |
| `provider` | `string` | Sí | Proveedor de IA | `gemini` |
| `model` | `string` | Sí | Modelo utilizado | `model-name` |
| `confidence` | `decimal(5,4)` | Sí | Valor entre 0 y 1 | `0.8200` |
| `review_status` | `enum` | No | Estado de revisión | `pending` |
| `created_at` | `datetime` | No | Fecha de creación | `2026-07-31T09:10:00-05:00` |

**Reglas:**

- `confidence` es nulo para reglas determinísticas.
- `ocr_engine`, `ocr_engine_version` y `document_page_id` son obligatorios cuando el valor depende de OCR.
- Un resultado pendiente no reemplaza el valor original.
- El modelo real solo se registra después de ejecutar la integración.

**Consumidores:** revisión humana, consolidación, auditoría.

---

## 21. Entidad `review_decision`

Registra la decisión humana sobre una propuesta.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `review_id` | `string` | No | Identificador único | `REV-000001` |
| `extraction_id` | `string` | No | FK a extracción | `EXT-000001` |
| `decision` | `enum` | No | `accepted`, `corrected` o `rejected` | `corrected` |
| `corrected_value` | `string` | Sí | Valor corregido | `PRD-0002` |
| `reviewed_by` | `string` | No | Usuario sintético o rol | `demo-admin` |
| `reviewed_at` | `datetime` | No | Fecha de decisión | `2026-07-31T09:15:00-05:00` |
| `comment` | `string` | Sí | Justificación breve | `El empaque corresponde a 250 g` |

**Clasificación:** `technical_metadata`.
**Consumidores:** consolidación, auditoría y dashboard.

---

## 22. Entidad `quality_finding`

Representa un hallazgo de calidad.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `finding_id` | `string` | No | Identificador único | `DQ-000001` |
| `rule_id` | `string` | No | Regla que produjo el hallazgo | `RULE-DUP-SALE-001` |
| `finding_type` | `string` | No | Tipo de anomalía | `duplicate_sale_line` |
| `severity` | `enum` | No | Severidad | `error` |
| `message` | `string` | No | Explicación comprensible | `Línea de venta duplicada` |
| `source_location_id` | `string` | No | Evidencia principal | `LOC-000110` |
| `related_record_ids` | `list[string]` | Sí | Registros vinculados | `["SALL-000010","SALL-000011"]` |
| `observed_value` | `string` | Sí | Valor observado | `SALL-000010` |
| `expected_value` | `string` | Sí | Valor o condición esperada | `unique` |
| `detected_at` | `datetime` | No | Fecha de detección | `2026-07-31T09:20:00-05:00` |
| `record_status` | `enum` | No | Estado del hallazgo | `observed` |

**Clasificación:** `technical_metadata`.
**Consumidores:** validación, verdad de referencia, dashboard y métricas de detección.

---

## 23. Entidad `transformation_event`

Registra una transformación aplicada.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `transformation_id` | `string` | No | Identificador único | `TRF-000001` |
| `rule_id` | `string` | No | Regla aplicada | `NORM-SUPPLIER-001` |
| `source_location_id` | `string` | No | Origen del valor | `LOC-000030` |
| `target_entity` | `string` | No | Entidad afectada | `supplier` |
| `target_record_id` | `string` | No | Registro resultante | `SUP-0001` |
| `target_field` | `string` | No | Campo afectado | `supplier_name` |
| `input_value` | `string` | Sí | Valor de entrada | `Distribuciones Andinas S.A.S.` |
| `output_value` | `string` | Sí | Valor normalizado | `Distribuciones Andinas SAS` |
| `method` | `string` | No | Método determinístico o aprobado | `deterministic_rule` |
| `applied_at` | `datetime` | No | Fecha de aplicación | `2026-07-31T09:25:00-05:00` |

**Consumidores:** procedencia, auditoría, alertas y respuestas.

---

## 24. Entidad `indicator_run`

Representa una ejecución reproducible de un preset de indicadores.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `run_id` | `string` | No | Identificador estable de ejecución | `KPIRUN-000001` |
| `preset_id` | `string` | No | Preset seleccionado | `retail_distribution` |
| `preset_label` | `string` | No | Nombre legible | `Comercializadora o distribuidora` |
| `config_hash` | `string` | No | Hash de la configuración validada | `sha256...` |
| `database_logical_hash` | `string` | No | Hash lógico de los datos operativos | `sha256...` |
| `as_of_date` | `date` | No | Fecha de corte | `2026-07-31` |
| `calculated_at` | `datetime` | No | Fecha reproducible de cálculo | `2026-07-31T09:00:00+00:00` |
| `result_count` | `integer` | No | Cantidad de resultados | `18` |

---

## 25. Entidad `indicator_result`

Representa un resultado determinístico de indicador.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `indicator_result_id` | `string` | No | Identificador único y estable para la ejecución | `KPI-000001` |
| `run_id` | `string` | No | Ejecución determinística del preset | `KPIRUN-000001` |
| `preset_id` | `string` | No | Preconfiguración seleccionada | `retail_distribution` |
| `indicator_id` | `string` | No | Indicador configurado | `KPI-SALES-TOTAL` |
| `period_start` | `date` | Sí | Inicio del periodo | `2026-07-01` |
| `period_end` | `date` | Sí | Fin del periodo | `2026-07-31` |
| `dimension` | `string` | Sí | Dimensión opcional | `category` |
| `dimension_value` | `string` | Sí | Valor de dimensión | `Bebidas` |
| `numeric_value` | `decimal(18,4)` | Sí | Resultado numérico | `15250000.0000` |
| `unit` | `string` | No | Unidad del resultado | `COP` |
| `formula_version` | `string` | No | Versión de fórmula | `1.0.0` |
| `source_record_ids` | `list[string]` | No | Registros utilizados | `["SALL-000001"]` |
| `source_location_ids` | `list[string]` | No | Ubicaciones de evidencia | `["LOC-000100"]` |
| `details` | `json` | No | Entradas, fórmula y contexto complementario | `{"sale_count": 15}` |
| `calculated_at` | `datetime` | No | Fecha de cálculo de la ejecución | `2026-07-31T09:30:00-05:00` |

**Reglas:** los modelos generativos no producen `numeric_value`; la configuración selecciona fórmulas aprobadas y no acepta SQL arbitrario.
**Consumidores:** dashboard, alertas y respuestas empresariales.

---

## 26. Entidad `alert`

Representa una condición operativa detectada por una regla.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `alert_id` | `string` | No | Identificador único | `ALT-000001` |
| `rule_id` | `string` | No | Regla activada | `RULE-LOW-STOCK-001` |
| `alert_type` | `string` | No | Tipo de alerta | `low_inventory` |
| `severity` | `enum` | No | Severidad | `warning` |
| `title` | `string` | No | Título breve | `Inventario bajo` |
| `description` | `string` | No | Explicación basada en datos | `El producto está por debajo del punto de reorden.` |
| `observed_value` | `decimal(18,4)` | Sí | Valor observado | `20.0000` |
| `threshold_value` | `decimal(18,4)` | Sí | Umbral aplicado | `30.0000` |
| `unit` | `string` | Sí | Unidad | `unit` |
| `related_record_ids` | `list[string]` | No | Registros que sustentan la alerta | `["PRD-0001"]` |
| `source_location_ids` | `list[string]` | No | Evidencias | `["LOC-000200"]` |
| `generated_at` | `datetime` | No | Fecha de generación | `2026-07-31T09:35:00-05:00` |
| `review_status` | `enum` | No | Estado de revisión | `pending` |

**Consumidores:** dashboard, trazabilidad, Demo Day y preguntas empresariales.

---

## 27. Entidad `business_answer`

Representa una respuesta a una pregunta priorizada.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `answer_id` | `string` | No | Identificador único | `ANS-000001` |
| `question_id` | `string` | No | Pregunta aprobada | `BQ-001` |
| `question_text` | `string` | No | Pregunta formulada | `¿Cuáles fueron las ventas totales?` |
| `answer_text` | `string` | No | Respuesta concisa | `Las ventas del periodo fueron COP 15.250.000.` |
| `indicator_result_ids` | `list[string]` | Sí | Resultados estructurados utilizados | `["KPI-000001"]` |
| `source_location_ids` | `list[string]` | Sí | Evidencias relacionadas | `["LOC-000100"]` |
| `evidence_status` | `enum` | No | `sufficient` o `insufficient` | `sufficient` |
| `provider` | `string` | Sí | Proveedor generativo, si se utilizó | `none` |
| `created_at` | `datetime` | No | Fecha de respuesta | `2026-07-31T09:40:00-05:00` |

**Regla:** con evidencia insuficiente, `answer_text` debe comunicar la limitación y no inventar cifras.
**Consumidores:** dashboard, auditoría y Demo Day.

---

## 28. Entidad `expected_anomaly`

Representa una anomalía sembrada en la verdad de referencia.

| Campo | Tipo | Nulo | Definición y reglas | Ejemplo |
|---|---|---:|---|---|
| `anomaly_id` | `string` | No | Identificador único | `ANOM-001` |
| `type` | `string` | No | Tipo esperado | `duplicate_invoice` |
| `severity` | `enum` | No | Severidad esperada | `error` |
| `source_file` | `string` | No | Archivo afectado | `invoices/invoice_008.pdf` |
| `source_record_ids` | `list[string]` | No | Registros afectados | `["INV-000004","INV-000008"]` |
| `expected_rule_id` | `string` | No | Regla que debe detectarla | `RULE-DUP-INVOICE-001` |
| `expected_detected` | `boolean` | No | Debe detectarse o no | `true` |

**Consumidores:** pruebas, auditoría de calidad y métricas de falsos positivos/negativos.

---

## 29. Relaciones principales

```text
customer 1 ─── * sale_line * ─── 1 product
product  1 ─── * inventory_snapshot
supplier 1 ─── * purchase_order_line * ─── 1 product
source_file 1 ─── * document 1 ─── * document_page
supplier 1 ─── * invoice 1 ─── * invoice_line
supplier 1 ─── * quotation 1 ─── * quotation_line
product  1 ─── * invoice_line
product  1 ─── * quotation_line
plugin_run 1 ─── * email_message
plugin_run 1 ─── * extraction_result
email_message 1 ─── * extraction_result
extraction_result 1 ─── 0..1 review_decision
source_file 1 ─── * source_location
source_location 1 ─── * quality_finding
source_location 1 ─── * transformation_event
indicator_result * ─── * source records
alert * ─── * source_location
business_answer * ─── * indicator_result
```

---

## 30. Reglas transversales

1. Todo registro procesado conserva `source_location_id` o una colección equivalente.
2. Los valores monetarios no utilizan punto flotante binario.
3. Los datos crudos nunca se reemplazan.
4. Los resultados de IA se almacenan como propuestas hasta su aprobación.
5. Las cifras de indicadores provienen de código o SQL determinístico.
6. Los identificadores no se reutilizan entre entidades.
7. Las fechas se interpretan en `America/Bogota`.
8. Los campos de contacto son sintéticos.
9. Los campos no disponibles se representan con `null`.
10. Los consumidores no deben depender de alias de las fuentes.
11. Una página OCR debe registrar motor y versión.
12. Una cotización no se convierte en factura sin una fuente posterior que lo demuestre.
13. Ningún campo documental se consolida sin evidencia de página.

---

## 30. Ubicación JSON/NDJSON

La ubicación `JsonSourceLocation` especializa `source_location` con `record_number`, `line`, `json_pointer`, `field` y `raw_value`. `line` es obligatorio para NDJSON y nulo para JSON convencional. `json_pointer` siempre comienza con `/` y permite ubicar el valor dentro del documento o registro.

---


## 31. Almacén físico SQLite

`data/processed/faro.db` materializa el modelo lógico sin sustituir las fuentes raw.

| Tabla | Propósito |
|---|---|
| `source_file` | Archivo, contrato, hash, formato y adaptador |
| `source_location` | Celda, fila, página, región, JSON Pointer o XPath |
| `record_observation` | Todas las observaciones con payload y prioridad |
| tablas canónicas | Registros aceptados seleccionados |
| `quality_finding` | Errores, advertencias y conflictos |
| `transformation_event` | Regla y hashes de cada selección canónica |
| `metadata` | Esquema, digest de entradas y hash lógico |

La fecha de consolidación se configura mediante `FARO_CONSOLIDATION_TIMESTAMP`. El dataset sintético utiliza un valor fijo para garantizar reproducibilidad.

---

## 32. Criterios de aceptación del diccionario

El diccionario se considera listo para implementación cuando:

1. todos los campos de los contratos están definidos;
2. los tipos y la nulabilidad permiten construir fixtures;
3. las claves y relaciones pueden validarse;
4. los indicadores y alertas tienen campos de procedencia;
5. la confianza y la revisión humana están representadas;
6. las preguntas empresariales pueden vincularse con resultados estructurados;
7. no existen campos ambiguos o con semántica duplicada;
8. los cambios posteriores siguen el control de versiones;
9. `plugin_run`, `email_message` y `extraction_result` permiten reconstruir la ejecución;
10. el fixture y una ejecución real comparten el mismo modelo;
11. `document` y `document_page` representan PDF nativos, escaneados, mixtos e imágenes documentales;
12. facturas y cotizaciones tienen entidades separadas;
13. los campos OCR conservan motor, versión, confianza y procedencia;
14. JSON y NDJSON conservan perfil, versión, registro y JSON Pointer;
15. NDJSON conserva número de línea para cada registro procesado.
