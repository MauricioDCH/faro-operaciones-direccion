# Casos de uso

**Estado:** línea base aprobada para implementación
**Producto:** Faro
**Versión:** 1.5

Los criterios técnicos detallados permanecen en `docs/product/requirements.md`.

---

## UC-001 — Procesar fuentes operativas

**Actor:** administrador.
**Objetivo:** incorporar libros de Excel, facturas y cotizaciones PDF, y lotes estructurados producidos por plugins.

**Flujo:**

1. El usuario selecciona las fuentes.
2. Faro registra sus metadatos.
3. Faro valida libros, hojas, documentos y lotes.
4. Faro informa fuentes aceptadas, rechazadas o observadas.
5. Los originales permanecen sin cambios.

**Resultado:** las fuentes quedan disponibles para validación y consolidación con procedencia.

**Requisitos:** FR-001, FR-002, FR-018, FR-010.

---

## UC-002 — Revisar la calidad de los datos

**Actor:** administrador o auxiliar administrativo.
**Objetivo:** identificar errores antes de calcular indicadores.

**Flujo:**

1. El usuario ejecuta la validación.
2. Faro comprueba estructuras, campos, tipos, fechas, rangos, duplicados e integridad referencial.
3. Faro clasifica los hallazgos.
4. El usuario consulta la fuente y ubicación.
5. Faro conserva los datos originales.

**Resultado:** el usuario conoce qué registros son válidos, observados o rechazados.

**Requisitos:** FR-003, FR-009, QR-009.

---

## UC-003 — Revisar una extracción incierta

**Actor:** administrador o auxiliar administrativo.
**Objetivo:** validar propuestas asistidas por IA.

**Flujo:**

1. Faro presenta una extracción con confianza insuficiente.
2. El usuario consulta evidencia, plataforma, plugin, método y prompt.
3. El usuario acepta, corrige o rechaza.
4. Faro registra la decisión y conserva el valor original.
5. El resultado aprobado queda disponible para consolidación.

**Resultado:** ninguna propuesta incierta se incorpora sin revisión.

**Requisitos:** FR-004, FR-011, FR-012.

---

## UC-004 — Consultar el dashboard

**Actor:** propietario o administrador.
**Objetivo:** obtener una vista concisa del estado operativo.

**Flujo:**

1. El usuario abre el dashboard.
2. Faro muestra ingesta e importaciones.
3. Faro presenta calidad, indicadores y alertas.
4. Faro muestra revisiones pendientes.
5. El usuario inspecciona evidencia.

**Resultado:** el usuario identifica asuntos que requieren atención.

**Requisitos:** FR-006, FR-007, FR-013.

---

## UC-005 — Detectar riesgo de inventario

**Actor:** responsable de inventario.
**Objetivo:** identificar productos por debajo del umbral aprobado.

**Flujo:**

1. El usuario consulta productos con bajo inventario.
2. Faro aplica la regla configurada.
3. Faro muestra valor observado, umbral y severidad.
4. El usuario accede a los registros utilizados.
5. El usuario decide si debe revisar una reposición.

**Resultado:** cada alerta es verificable y no ejecuta decisiones.

**Requisitos:** FR-006, FR-007, FR-009.

---

## UC-006 — Detectar inconsistencias

**Actor:** auxiliar administrativo.

**Escenarios:**

- facturas posiblemente duplicadas;
- ventas duplicadas;
- diferencias entre pedido y factura;
- cambios de pedido informados por correo;
- nombres inconsistentes.

**Flujo:**

1. Faro ejecuta reglas.
2. Faro genera alertas.
3. El usuario consulta registros relacionados.
4. Faro muestra regla, evidencia y severidad.
5. El usuario marca el caso como pendiente, revisado o descartado.

**Resultado:** el usuario verifica la inconsistencia antes de actuar.

**Requisitos:** FR-003, FR-004, FR-007, FR-009.

---

## UC-007 — Formular una pregunta empresarial

**Actor:** propietario o administrador.
**Objetivo:** obtener una respuesta verificable.

**Flujo:**

1. El usuario selecciona o formula una pregunta aprobada.
2. Faro recupera resultados estructurados.
3. Faro presenta una respuesta concisa.
4. Faro muestra cifras y fuentes.
5. Con evidencia insuficiente, Faro lo informa sin inventar.

**Resultado:** toda respuesta numérica puede rastrearse.

**Requisitos:** FR-008, FR-009, QR-010.

---

## UC-008 — Rastrear un resultado

**Actor:** cualquier usuario del MVP.
**Objetivo:** verificar el origen de un indicador, alerta o respuesta.

**Flujo:**

1. El usuario selecciona un resultado.
2. Faro muestra el libro, PDF o referencia de correo original.
3. Faro identifica hoja, página, mensaje, fila, ejecución de plugin o registro.
4. Faro muestra transformaciones y reglas.
5. El usuario regresa al resultado.

**Resultado:** el usuario reconstruye la procedencia.

**Requisitos:** FR-009, FR-010, QR-007.

---

## UC-009 — Continuar sin plugin

**Actor:** administrador o presentador del Demo Day.
**Objetivo:** ejecutar el flujo principal cuando Gmail, el plugin o internet no estén disponibles.

**Flujo:**

1. Faro informa que la conexión externa no está disponible.
2. El usuario selecciona el fixture de contingencia.
3. Faro valida el fixture con el mismo JSON Schema.
4. Faro ejecuta validación, consolidación, indicadores y alertas.
5. El dashboard identifica que la fuente es una reproducción.

**Resultado:** la demostración continúa sin presentar el fixture como una conexión activa.

**Requisitos:** FR-019, QR-011, QR-014.

---

## UC-010 — Consultar correos mediante plugin de IA

**Actor:** administrador.
**Sistemas externos:** ChatGPT o Claude; Gmail sintético.

**Precondiciones:**

- la cuenta contiene únicamente datos sintéticos;
- la aplicación o integración de Gmail está conectada;
- el prompt canónico está disponible;
- la consulta temporal está delimitada.

**Flujo:**

1. El usuario abre ChatGPT o Claude.
2. Invoca el plugin o integración de Gmail.
3. Ejecuta `prompts/email-plugin-extraction.md`.
4. La IA recupera solo los mensajes que cumplen la consulta.
5. La IA clasifica y extrae campos.
6. La IA devuelve únicamente un JSON conforme al esquema.
7. El usuario guarda el artefacto sin editarlo.

**Flujos alternativos:**

- si el plugin no está disponible, se ejecuta UC-009;
- si una referencia no es verificable, el campo queda observado;
- si el JSON no cumple el esquema, no se importa.

**Resultado:** se obtiene un lote portable y trazable.

**Requisitos:** FR-016, FR-017, QR-013, QR-015, QR-016.

---

## UC-011 — Importar el lote del plugin

**Actor:** administrador.
**Objetivo:** incorporar a Faro los eventos extraídos de Gmail por la IA.

**Flujo:**

1. El usuario selecciona `plugin-email-batch.json`.
2. Faro valida versión, estructura y campos.
3. Faro verifica duplicados y referencias.
4. Faro registra la ejecución del plugin.
5. Faro importa mensajes y extracciones válidas.
6. Faro envía propuestas inciertas a revisión humana.
7. Faro preserva el lote original.

**Resultado:** los eventos de correo quedan disponibles para reglas e indicadores sin confiar ciegamente en la IA.

**Requisitos:** FR-018, FR-011, FR-012, QR-014.

---

## UC-012 — Procesar un documento PDF escaneado

**Actor:** administrador o auxiliar administrativo.
**Objetivo:** extraer información verificable de una factura o cotización escaneada.

**Precondiciones:**

- el documento es sintético;
- corresponde a una factura o cotización;
- contiene entre una y tres páginas;
- el texto impreso es razonablemente legible.

**Flujo:**

1. El usuario carga el PDF.
2. Faro calcula el hash y registra el archivo sin modificarlo.
3. Faro inspecciona cada página.
4. Las páginas con texto suficiente usan extracción directa.
5. Las páginas sin texto suficiente se renderizan y procesan mediante OCR.
6. Faro registra método, motor, versión, idioma, confianza y evidencia por página.
7. La IA clasifica el documento y propone campos estructurados.
8. Faro valida fechas, cantidades, subtotales, impuestos, totales y relaciones.
9. Los campos inciertos pasan a revisión humana.
10. El usuario consulta el PDF y la página que sustentan cada campo.

**Flujos alternativos:**

- un documento no soportado se rechaza de forma estructurada;
- una página ilegible queda `pending_review`;
- un campo sin evidencia no se consolida;
- un total inconsistente genera un hallazgo de calidad.

**Resultado:** la factura o cotización queda estructurada con procedencia verificable, o se informa por qué no pudo aceptarse.

**Requisitos:** FR-002, FR-020, FR-021, FR-022, QR-017, QR-018.

---

## UC-013 — Seleccionar y evaluar un preset de alertas

**Actor:** propietario o administrador.
**Objetivo:** adaptar los umbrales de seguimiento a las prioridades de la empresa sin modificar código.

**Flujo:**

1. El usuario consulta los presets disponibles.
2. Selecciona distribución, ventas, inventario, calidad o una copia del ejemplo personalizable.
3. Faro valida fuentes, agregaciones, operadores, umbrales, unidades y severidades.
4. Faro calcula el preset de indicadores requerido.
5. Faro evalúa todas las reglas y registra estados `triggered`, `clear` o `not_evaluated`.
6. Las condiciones activadas se guardan como alertas con evidencia.
7. El usuario revisa el valor observado, umbral, registros y ubicaciones fuente.

**Flujos alternativos:**

- una regla con SQL, código o campos desconocidos se rechaza;
- una fuente ausente o ambigua queda `not_evaluated`;
- una condición clara no crea una alerta, pero conserva su evaluación;
- la falta de canal externo deja `delivery_status=not_configured`.

**Resultado:** la empresa obtiene alertas reproducibles y adaptadas a su operación.

**Requisitos:** FR-006, FR-007, FR-009, QR-007.

---

## UC-014 — Actualizar información desde el dashboard

**Actor:** propietario, administrador o auxiliar autorizado.
**Objetivo:** agregar o reemplazar información sin ejecutar comandos ni reprocesar todas las fuentes históricas.

**Precondiciones:**

- existe una base operacional válida;
- el dashboard se ejecuta localmente;
- el archivo utiliza un formato implementado;
- para archivos tabulares se conoce el tipo de contenido.

**Flujo:**

1. El usuario selecciona **Actualizar información**.
2. Elige un archivo y, cuando aplica, indica si contiene productos, clientes, proveedores, ventas, inventario o pedidos.
3. Selecciona **Actualizar** o **Agregar**.
4. Faro guarda temporalmente el archivo fuera de la base activa.
5. Faro valida tamaño, nombre, extensión, formato real y duplicidad por hash.
6. Faro ingiere únicamente la nueva fuente.
7. Faro combina las nuevas observaciones con las ya almacenadas.
8. Faro construye una base candidata y recalcula indicadores y alertas.
9. Faro verifica integridad, crea una copia de seguridad y reemplaza la base activa de forma atómica.
10. El dashboard muestra el resultado de la carga y los datos renovados.

**Flujos alternativos:**

- un archivo repetido se marca como ya procesado y no genera cambios;
- un archivo inválido se rechaza con un mensaje sencillo;
- una referencia inexistente impide activar la candidata;
- un error durante cálculo o persistencia elimina la candidata;
- una configuración empresarial inválida usa un perfil seguro integrado;
- en todos los fallos, la última base válida sigue disponible.

**Resultado:** la información se actualiza desde la interfaz o el usuario recibe una explicación sin pérdida de servicio ni corrupción de la base activa.

**Requisitos:** FR-031, FR-032, FR-033, FR-034, QR-025, QR-026, QR-027.
