# Requisitos del producto

**Estado del documento:** línea base aprobada para implementación  
**Producto:** Faro  
**Origen:** R4 — Operaciones / Dirección, conservado como referencia histórica  
**Dirección actual:** producto independiente para uso local en pymes  
**Segmento inicial:** micro o pequeña empresa comercializadora o distribuidora de Medellín  
**Versión:** 1.9

---

## 1. Convenciones

| Estado | Significado |
|---|---|
| `planned` | Aprobado, pero todavía no implementado |
| `implemented` | Implementado, probado, documentado y reproducible |
| `simulated` | Representado únicamente para demostración |
| `out of scope` | Excluido explícitamente del MVP |

Un requisito solo puede marcarse como `implemented` cuando cumple su evidencia, cuenta con pruebas cuando corresponda, conserva procedencia, está documentado y puede reproducirse.

---

## 2. Requisitos funcionales

| ID | Requisito | Evidencia de aceptación | Estado |
|---|---|---|---|
| FR-001 | Ingerir los libros de Excel sintéticos aprobados. | Los cuatro libros y seis hojas válidos se procesan, sus metadatos quedan registrados y los originales conservan sus hashes. | `implemented` |
| FR-002 | Extraer los campos aprobados de facturas y cotizaciones PDF sintéticas. | Los documentos nativos, escaneados y mixtos producen campos con archivo, página, método, evidencia y confianza cuando corresponda. | `implemented` |
| FR-003 | Validar hojas, esquemas, campos obligatorios, tipos, fechas, rangos, duplicados e integridad referencial. | La ingesta tabular detecta las anomalías Excel sembradas y las pruebas verifican estructura, tipos, reglas y relaciones. | `implemented` |
| FR-004 | Normalizar identificadores, fechas, unidades y nombres mediante reglas aprobadas. | Cada correspondencia conserva trazabilidad y las asociaciones inciertas requieren revisión humana. | `planned` |
| FR-005 | Consolidar los registros válidos en un modelo operativo común. | Cada registro puede rastrearse hasta el archivo o referencia de origen. | `planned` |
| FR-006 | Calcular indicadores operativos mediante lógica determinística. | Fórmulas, casos límite y resultados esperados están cubiertos por pruebas. | `planned` |
| FR-007 | Generar alertas trazables mediante reglas explícitas y configurables. | Cada alerta presenta regla, entradas, valor observado, umbral y procedencia. | `planned` |
| FR-008 | Responder preguntas empresariales mediante evidencia recuperada. | Las respuestas numéricas citan resultados estructurados y se rechazan cuando la evidencia es insuficiente. | `planned` |
| FR-009 | Mostrar la evidencia de indicadores, alertas y respuestas. | El usuario puede navegar hasta el libro, hoja, página, mensaje o registro correspondiente. | `planned` |
| FR-010 | Registrar las transformaciones aplicadas. | Cada transformación incluye origen, regla, fecha, entrada y resultado. | `planned` |
| FR-011 | Registrar metadatos de confianza para resultados asistidos por IA. | Se conservan plataforma, plugin, prompt, método, modelo visible, confianza, evidencia y revisión. | `planned` |
| FR-012 | Permitir revisión humana de propuestas inciertas. | El usuario puede aceptar, corregir o rechazar sin alterar las fuentes. | `planned` |
| FR-013 | Proporcionar un dashboard operativo conciso. | Una interfaz permite consultar ingesta, importaciones, calidad, indicadores, alertas, evidencia y revisiones. | `planned` |
| FR-014 | Mantener operativo el núcleo determinístico sin servicios externos. | Excel, PDF, validación, consolidación, indicadores, alertas, procedencia y dashboard funcionan sin plugin activo. | `planned` |
| FR-015 | Desacoplar las funciones locales de IA mediante una interfaz de proveedor. | La lógica de negocio no depende de OpenAI, Gemini u otro modelo específico. | `planned` |
| FR-016 | Consultar una cuenta Gmail sintética mediante un plugin o integración de ChatGPT o Claude. | Una ejecución delimitada recupera mensajes sintéticos y registra plataforma, plugin, aplicación, consulta y fecha. | `planned` |
| FR-017 | Producir un lote de correo conforme al esquema canónico. | La IA genera JSON válido sin texto adicional y cada mensaje conserva referencia, evidencia, extracción y confianza. | `planned` |
| FR-018 | Importar y validar el lote del plugin. | Faro valida el JSON Schema, rechaza lotes incompatibles, detecta duplicados y preserva el artefacto original. | `planned` |
| FR-019 | Proporcionar contingencia mediante un fixture del mismo contrato. | El fixture pasa el mismo validador y permite ejecutar la demostración sin plugin ni internet. | `planned` |
| FR-020 | Seleccionar por página entre extracción de texto nativo y OCR. | La ruta queda registrada y las páginas escaneadas no se procesan como texto vacío. | `implemented` |
| FR-021 | Clasificar documentos PDF como factura, cotización o no soportado. | Los documentos soportados siguen su contrato y los no soportados se rechazan sin inventar campos. | `implemented` |
| FR-022 | Registrar metadatos y procedencia del OCR. | Cada resultado OCR conserva archivo, página, motor, versión, idioma, confianza y evidencia. | `implemented` |
| FR-023 | Ingerir archivos CSV y TSV mediante perfiles explícitos. | Se validan codificación, delimitador, encabezados, separador decimal, tipos, límites, referencias y procedencia por registro y campo. | `implemented` |
| FR-024 | Ingerir documentos electrónicos XML UBL. | El XML se valida de forma segura, conserva versión y XPath, y produce entidades documentales canónicas sin depender de OCR. | `planned` |
| FR-025 | Ingerir imágenes de facturas y cotizaciones. | JPG, JPEG, PNG, TIFF y WebP reutilizan OCR, clasificación, extracción, confianza y evidencia. | `planned` |
| FR-026 | Ingerir JSON y NDJSON versionados. | Los documentos y registros validan perfil, versión, tipos, límites y procedencia mediante JSON Pointer, número de registro y línea cuando aplica. | `implemented` |
| FR-027 | Importar mensajes exportados en EML y MBOX. | Se conservan cabeceras, cuerpo, adjuntos, Message-ID y ubicación dentro del buzón sin modificar la fuente. | `planned` |
| FR-028 | Procesar lotes ZIP controlados. | Solo se aceptan miembros permitidos, con límites, manifiesto, hashes y protección contra rutas inseguras y expansión excesiva. | `planned` |
| FR-029 | Ingerir documentos administrativos DOCX y ODT controlados. | El contenido se extrae sin ejecutar macros y conserva sección, párrafo y evidencia. | `planned` |

---

## 3. Requisitos de calidad

| ID | Requisito | Evidencia de aceptación | Estado |
|---|---|---|---|
| QR-001 | Ejecutarse localmente en Ubuntu con dependencias versionadas. | El proyecto se instala y ejecuta con los comandos documentados. | `implemented` |
| QR-002 | Usar únicamente datos sintéticos determinísticos con semilla fija. | Dos ejecuciones con la misma semilla producen los mismos archivos y anomalías. | `implemented` |
| QR-003 | No sobrescribir fuentes ni artefactos importados. | Los archivos Excel mantienen su hash antes y después de la ingesta; los PDF se leen sin sobrescritura. | `implemented` |
| QR-004 | Mantener secretos fuera del control de versiones. | Existe `.env.example`, `.env` está excluido y no hay credenciales conocidas. | `implemented` |
| QR-005 | Proporcionar comandos reproducibles de instalación, prueba y ejecución. | Funcionan desde un clon limpio. | `implemented` |
| QR-006 | Incorporar pruebas de éxito, error y regresión. | Las rutas sintética, PDF/OCR y Excel cuentan con pruebas unitarias e integración. | `implemented` |
| QR-007 | Mantener trazabilidad completa. | El 100 % de alertas y respuestas numéricas apunta a fuentes identificables. | `planned` |
| QR-008 | Producir resultados determinísticos para cálculos y reglas. | Las mismas entradas y configuración producen los mismos resultados. | `planned` |
| QR-009 | Informar errores de forma estructurada. | Cada error incluye código, fuente, ubicación, descripción y severidad. | `planned` |
| QR-010 | Evitar cifras generadas por IA sin respaldo estructurado. | Las respuestas sin evidencia se rechazan o marcan como no verificables. | `planned` |
| QR-011 | Degradar de forma controlada las dependencias externas. | La indisponibilidad del plugin no interrumpe el flujo determinístico ni la contingencia. | `planned` |
| QR-012 | Mantener una interfaz suficiente para el Demo Day. | El dashboard implementa únicamente las vistas aprobadas. | `planned` |
| QR-013 | Limitar la integración de correo a operaciones de lectura. | La demostración no envía, modifica, archiva ni elimina mensajes. | `planned` |
| QR-014 | Validar toda salida del plugin mediante un JSON Schema versionado. | Los lotes inválidos se rechazan con errores localizables. | `planned` |
| QR-015 | No inventar referencias de correo. | Una extracción sin referencia verificable queda observada y requiere revisión. | `planned` |
| QR-016 | Mantener portabilidad entre ChatGPT y Claude. | Ambos producen el mismo contrato sin cambiar el núcleo de Faro. | `planned` |
| QR-017 | Degradar de forma segura ante OCR ilegible o insuficiente. | El documento queda `pending_review` o `unsupported`; no se generan campos sin evidencia. | `implemented` |
| QR-018 | Mantener reproducible la ruta OCR. | El motor, idioma y versiones están fijados y los fixtures producen resultados verificables en el entorno documentado. | `planned` |
| QR-019 | Ejecutarse oficialmente en Windows 10/11 de 64 bits. | Un clon limpio instala, diagnostica y ejecuta las pruebas aprobadas en Windows. | `planned` |
| QR-020 | Detectar sistema operativo y ejecutables externos de forma centralizada. | La lógica de negocio no contiene rutas ni condiciones de plataforma dispersas. | `planned` |
| QR-021 | Mantener rutas y operaciones de archivos portables. | Las pruebas cubren rutas Linux y Windows, nombres Unicode y separadores distintos. | `planned` |
| QR-022 | Ejecutar CI en Linux y Windows. | La matriz de CI aprueba las pruebas que no requieren dependencias opcionales y diagnostica OCR por plataforma. | `planned` |
| QR-023 | Validar el contenido real y no solo la extensión. | Cada adaptador verifica firma, estructura o esquema antes de aceptar la fuente. | `planned` |
| QR-024 | Aplicar límites de seguridad a archivos y lotes. | Tamaño, filas, páginas, registros, miembros, profundidad y recursos están acotados y probados. | `planned` |

---

## 4. Preguntas empresariales garantizadas

1. ¿Cuáles fueron las ventas totales del periodo?
2. ¿Cómo variaron las ventas frente al periodo anterior?
3. ¿Qué productos presentan bajo inventario?
4. ¿Qué facturas o registros podrían estar duplicados?
5. ¿Qué pedidos presentan diferencias frente a lo facturado?
6. ¿Qué proveedores o productos presentan nombres inconsistentes?

---

## 5. Trazabilidad entre alcance y requisitos

| Capacidad | Requisitos |
|---|---|
| Libros de Excel | FR-001, FR-003, QR-003, QR-009 |
| CSV y TSV | FR-023, QR-021, QR-023, QR-024 |
| XML UBL | FR-024, QR-021, QR-023, QR-024 |
| Imágenes documentales | FR-025, FR-020, FR-021, FR-022, QR-017, QR-018 |
| JSON y NDJSON | FR-026, QR-014, QR-021, QR-023, QR-024 |
| EML y MBOX | FR-027, QR-021, QR-023, QR-024 |
| ZIP controlado | FR-028, QR-023, QR-024 |
| DOCX y ODT | FR-029, QR-021, QR-023, QR-024 |
| Facturas y cotizaciones PDF | FR-002, FR-020, FR-021, FR-022, QR-017, QR-018 |
| Plugin de correo | FR-016, FR-017, QR-013, QR-015, QR-016 |
| Importación del lote | FR-018, QR-014 |
| Contingencia | FR-019, QR-011 |
| Validación y normalización | FR-003, FR-004, FR-010 |
| Consolidación | FR-005, QR-007, QR-008 |
| Indicadores y alertas | FR-006, FR-007, FR-009 |
| Preguntas empresariales | FR-008, FR-009, QR-010 |
| Dashboard | FR-013, QR-012 |
| Núcleo sin servicios externos | FR-014, QR-011 |
| IA local desacoplada | FR-015 |
| Reproducibilidad | QR-001, QR-002, QR-004, QR-005, QR-006 |
| Compatibilidad Linux/Windows | QR-019, QR-020, QR-021, QR-022 |

---

## 6. Control de cambios

Se requiere un registro de decisión cuando un cambio afecte alcance, requisitos, interfaces, contratos, fórmulas, reglas, anomalías, procedencia, tecnologías principales, plugins o comportamiento visible de la demostración.

Las decisiones se documentan en `docs/decisions/`.

---

## 7. Fuentes canónicas relacionadas

| Concepto | Ruta |
|---|---|
| Alcance | `docs/product/mvp-scope.md` |
| Casos de uso | `docs/product/use-cases.md` |
| Flujo del plugin de correo | `docs/integrations/plugin-email-workflow.md` |
| Decisión de OCR | `docs/decisions/0001-support-scanned-pdf-ocr.md` |
| Selección de pila PDF/OCR | `docs/decisions/0002-select-local-pdf-ocr-stack.md` |
| Soporte Linux y Windows | `docs/decisions/0003-support-linux-and-windows.md` |
| Expansión de formatos | `docs/decisions/0004-expand-input-formats.md` |
| Hoja de ruta de formatos | `docs/product/input-format-roadmap.md` |
| Contratos | `docs/data/data-contracts.md` |
| Campos canónicos | `docs/data/data-dictionary.md` |
| Esquema del lote | `schemas/plugin-email-batch.schema.json` |
| Ejemplo reproducible | `data/samples/plugin-email-batch.example.json` |
| Prompt canónico | `prompts/email-plugin-extraction.md` |
