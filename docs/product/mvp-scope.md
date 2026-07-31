# Alcance del MVP

**Estado:** línea base aprobada para implementación  
**Producto:** Faro  
**Reto:** R4 — Operaciones / Dirección  
**Versión del alcance:** 1.3

---

## 1. Objetivo

Construir un MVP local y reproducible que permita a una micro o pequeña empresa comercializadora o distribuidora consolidar información operativa sintética proveniente de libros de Excel, facturas PDF y correos consultados mediante plugins o integraciones de IA; validar su calidad; calcular indicadores; detectar anomalías; generar alertas trazables; y responder preguntas empresariales mediante evidencia verificable.

---

## 2. Segmento inicial

El MVP se diseñará para una:

> **Micro o pequeña empresa comercializadora o distribuidora de alimentos, bebidas, productos de aseo o insumos empresariales ubicada en Medellín.**

El escenario de demostración representará una sola empresa sintética y utilizará una cuenta de correo dedicada exclusivamente al proyecto.

---

## 3. Fuentes aprobadas

| Fuente | Formato o canal | Uso |
|---|---|---|
| Catálogos maestros | `catalogos.xlsx` | Productos, clientes y proveedores |
| Ventas | `ventas.xlsx` | Transacciones y líneas de venta |
| Inventario | `inventario.xlsx` | Existencias y puntos de reposición |
| Pedidos | `pedidos.xlsx` | Pedidos realizados a proveedores |
| Facturas | `*.pdf` | Facturas sintéticas de proveedores |
| Correo | plugin o integración de Gmail | Pedidos, cambios, cancelaciones y novedades |
| Transferencia plugin → Faro | `plugin-email-batch.json` | Lote estructurado producido por la IA |
| Verdad de referencia | `expected_anomalies.json` | Evaluación automatizada interna |

Los archivos CSV y la carga manual de `.eml` no forman parte de la experiencia del usuario.

---

## 4. Arquitectura de correo asistida por plugins

El plugin o integración consulta una cuenta Gmail con mensajes 100 % sintéticos. La IA interpreta los mensajes y produce un lote JSON conforme al contrato versionado de Faro.

```text
Gmail sintético
    ↓ plugin o integración
ChatGPT o Claude
    ↓ extracción estructurada
plugin-email-batch.json
    ↓ validación de esquema
Faro
    ↓ reglas determinísticas
indicadores, alertas, evidencia y dashboard
```

El plugin conecta la fuente y la IA interpreta el lenguaje. El núcleo de Faro valida identificadores, cantidades, relaciones, duplicados y reglas empresariales.

La transferencia obligatoria del MVP es un artefacto JSON. La escritura directa desde un plugin hacia el backend local mediante una app personalizada o MCP queda fuera del alcance inicial.

---

## 5. Capacidades obligatorias (`MUST`)

### MUST-001 — Ingesta de libros de Excel

Faro debe ingerir los libros sintéticos aprobados en formato `.xlsx`.

La ingesta debe:

- registrar metadatos del archivo;
- validar el nombre y las hojas requeridas;
- conservar el archivo original;
- identificar la hoja y fila procesadas;
- reportar errores de lectura de forma estructurada.

---

### MUST-002 — Procesamiento de facturas PDF

Faro debe extraer de facturas PDF sintéticas:

- número de factura;
- proveedor;
- fecha de emisión;
- productos;
- cantidades;
- subtotal;
- impuestos;
- total.

Cada campo extraído debe conservar archivo, página, evidencia, método, confianza cuando intervenga IA y estado de revisión humana.

Las facturas sintéticas deben contener texto extraíble. OCR general queda fuera del MVP.

---

### MUST-003 — Consulta de correo mediante plugin o integración de IA

El flujo de correo debe usar una cuenta Gmail dedicada con datos sintéticos y una integración disponible en ChatGPT o Claude.

La IA debe:

- recuperar únicamente mensajes dentro de una consulta delimitada;
- clasificar pedidos, cambios, cancelaciones y novedades;
- extraer identificadores, productos, cantidades y fechas;
- conservar evidencia y referencias a los mensajes;
- producir el contrato `plugin-email-batch`;
- registrar plataforma, plugin, aplicación fuente, consulta y versión del prompt.

El flujo es de solo lectura. Enviar, modificar, archivar o eliminar correos queda fuera del MVP.

---

### MUST-004 — Importación del lote producido por el plugin

Faro debe importar `plugin-email-batch.json` y:

- validar el archivo contra `schemas/plugin-email-batch.schema.json`;
- rechazar lotes incompatibles;
- impedir mensajes duplicados;
- preservar el artefacto importado sin modificarlo;
- registrar el origen de cada mensaje y extracción;
- enviar a revisión humana los campos inciertos.

---

### MUST-005 — Validación de calidad

Faro debe validar:

- estructura y hojas requeridas;
- campos obligatorios;
- tipos de datos;
- fechas y rangos;
- valores faltantes;
- duplicados;
- integridad referencial;
- cantidades negativas;
- inconsistencias entre fuentes;
- referencias de correo insuficientes o inventadas.

Los resultados deben compararse con una verdad de referencia versionada.

---

### MUST-006 — Normalización determinística

Faro debe normalizar identificadores, fechas, unidades, nombres de productos, proveedores y clientes, y valores monetarios.

Las reglas determinísticas tienen prioridad sobre las propuestas de IA. Los datos originales nunca se sobrescriben.

---

### MUST-007 — Consolidación operativa

Los registros válidos deben consolidarse en un modelo común que relacione productos, clientes, proveedores, ventas, inventario, pedidos, facturas, mensajes, ejecuciones de plugins, transformaciones, anomalías y alertas.

Cada registro consolidado debe conservar procedencia hasta su fuente original o referencia del plugin.

---

### MUST-008 — Indicadores operativos

El MVP debe calcular mediante código o SQL:

1. ventas totales del periodo;
2. variación frente al periodo anterior;
3. productos más vendidos;
4. productos con bajo inventario;
5. pedidos con diferencias;
6. facturas posiblemente duplicadas;
7. proveedores o productos con nombres inconsistentes.

Los modelos generativos no deben calcular estos valores.

---

### MUST-009 — Alertas trazables

Faro debe producir entre cuatro y seis reglas prioritarias. Cada alerta debe mostrar identificador, tipo, severidad, regla, entradas, valor observado, umbral, fuentes, registros relacionados, fecha y estado de revisión.

---

### MUST-010 — Preguntas empresariales verificables

Faro debe responder:

1. ¿Cuáles fueron las ventas totales del periodo?
2. ¿Cómo variaron las ventas frente al periodo anterior?
3. ¿Qué productos presentan bajo inventario?
4. ¿Qué facturas o registros podrían estar duplicados?
5. ¿Qué pedidos presentan diferencias frente a lo facturado?
6. ¿Qué proveedores o productos presentan nombres inconsistentes?

Toda respuesta numérica debe provenir de resultados estructurados. Cuando la evidencia sea insuficiente, Faro debe indicarlo explícitamente.

---

### MUST-011 — Metadatos de confianza

Toda extracción, clasificación o correspondencia asistida por IA debe registrar:

- plataforma y plugin o integración;
- proveedor y modelo cuando sean visibles;
- versión del prompt;
- fecha de ejecución;
- nivel de confianza;
- evidencia de entrada;
- resultado propuesto;
- estado de revisión;
- corrección humana cuando exista.

Las reglas determinísticas no requieren una confianza probabilística artificial.

---

### MUST-012 — Revisión humana

El usuario debe poder aceptar, corregir o rechazar propuestas inciertas, consultar su evidencia e identificar el método que las produjo. La revisión no debe modificar la fuente ni el artefacto importado.

---

### MUST-013 — Dashboard operativo

Faro debe incluir una interfaz concisa para:

- cargar libros y facturas;
- importar el lote del plugin;
- visualizar el estado de la ingesta;
- consultar calidad, indicadores y alertas;
- inspeccionar evidencia;
- revisar propuestas inciertas;
- formular preguntas priorizadas.

No se requiere un constructor general de dashboards, personalización avanzada ni múltiples roles.

---

### MUST-014 — Contingencia reproducible sin plugin

La demostración principal no debe fallar si el plugin, Gmail o internet no están disponibles.

Faro debe poder importar un fixture versionado:

```text
data/samples/plugin-email-batch.example.json
```

El fixture debe cumplir exactamente el mismo esquema que la salida real del plugin. La contingencia no simula una conexión activa; reproduce un lote previamente validado y debe declararse como tal.

---

### MUST-015 — Separación entre plugin y proveedor local de IA

La ingesta de correo y las funciones locales de IA son configuraciones independientes:

```text
EMAIL_INGESTION_MODE=plugin_artifact
AI_PLUGIN_PLATFORM=chatgpt
AI_PLUGIN_APP=gmail

AI_PROVIDER=none
AI_PROVIDER=openai
AI_PROVIDER=gemini
```

`AI_PROVIDER` controla funciones locales como explicación o mapeo. No representa la conexión de Gmail disponible dentro de ChatGPT o Claude.

---

### MUST-016 — Reproducibilidad local

El proyecto debe ejecutarse en Ubuntu con dependencias versionadas, `.env.example`, datos sintéticos, semilla fija, verdad de referencia, comandos de instalación, generación, pruebas y ejecución, resultados esperados y contingencia sin servicios externos.

---

## 6. Límites cuantitativos

| Elemento | Límite inicial |
|---|---:|
| Empresas sintéticas | 1 |
| Cuentas de correo sintéticas | 1 |
| Libros de Excel | 4 |
| Facturas PDF | conjunto reducido |
| Plataformas de plugin obligatorias | 1 |
| Aplicaciones fuente de correo | Gmail |
| Esquemas de transferencia | 1 |
| Indicadores | 5 a 7 |
| Reglas de alerta | 4 a 6 |
| Preguntas garantizadas | 6 |
| Dashboard | 1 |
| Flujo de revisión humana | 1 |
| Fixture de contingencia | 1 |

---

## 7. Fuera de alcance

- carga manual de correos `.eml`;
- archivos CSV como entrada del usuario;
- lectura de correos personales o empresariales reales;
- envío, respuesta, modificación, archivo o eliminación de mensajes;
- integración directa del backend con Gmail API;
- app personalizada o servidor MCP con escritura directa hacia Faro;
- ERP, CRM o plataforma contable completa;
- facturación electrónica ante la DIAN;
- conciliación bancaria o automatización de pagos;
- decisiones empresariales autónomas;
- modificación automática de datos originales;
- pronósticos avanzados;
- aplicación móvil;
- arquitectura multiempresa de producción;
- entrenamiento de modelos propios.

---

## 8. Estados

| Estado | Significado |
|---|---|
| `planned` | Aprobada, pero no implementada |
| `implemented` | Implementada, probada, documentada y reproducible |
| `simulated` | Representada únicamente para la demostración |
| `out of scope` | Excluida explícitamente del MVP |

La conexión ChatGPT/Claude–Gmail solo puede marcarse como `implemented` después de verificarla en la cuenta utilizada durante la Maratón.

---

## 9. Criterio de terminación

El MVP se considera terminado cuando:

1. los cuatro libros de Excel pueden procesarse;
2. las facturas PDF pueden procesarse;
3. un plugin o integración consulta Gmail sintético y genera un lote válido;
4. Faro valida e importa el lote sin modificarlo;
5. la contingencia reproduce el mismo contrato sin conexión externa;
6. los datos crudos permanecen sin cambios;
7. las anomalías se comparan con la verdad de referencia;
8. los indicadores se calculan determinísticamente;
9. las alertas conservan procedencia;
10. las seis preguntas pueden responderse;
11. la confianza y revisión humana están disponibles;
12. el dashboard ejecuta el flujo completo;
13. las pruebas pasan;
14. la documentación coincide con la implementación;
15. un evaluador puede reproducir el escenario desde un clon limpio.
