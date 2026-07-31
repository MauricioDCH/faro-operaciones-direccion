# Contratos de datos

**Estado:** línea base aprobada para implementación  
**Versión:** 1.3.0  
**Producto:** Faro  
**Alcance:** datos 100 % sintéticos

---

## 1. Objetivo

Este documento define los contratos de entrada y las garantías mínimas de salida de Faro.

El MVP utiliza libros de Excel como formato tabular visible. El correo se consulta mediante plugins o integraciones de IA y se transfiere a Faro mediante un artefacto JSON versionado.

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
| Formato tabular | Excel `.xlsx` |
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
| DC-007 | Facturas | `facturas/*.pdf` | no aplica | `invoice`, `invoice_line` |
| DC-008 | Lote de correo producido por plugin | `plugin-email-batch.json` | no aplica | `plugin_run`, `email_message`, `extraction_result` |
| DC-009 | Verdad de referencia | `expected_anomalies.json` | no aplica | `expected_anomaly` |

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

## 13. DC-007 — Facturas PDF

**Directorio:** `data/raw/facturas/`

Restricciones:

- PDF sintético;
- texto extraíble;
- una factura por archivo;
- moneda COP;
- OCR general fuera de alcance.

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

Cada campo conserva página, evidencia, método, confianza y revisión cuando corresponda.

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
  "column": "product_id"
}
```

### PDF

```json
{
  "source_type": "pdf",
  "file_path": "data/raw/facturas/factura_008.pdf",
  "page": 1,
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
10. la salida real y el fixture usan exactamente el mismo contrato.
