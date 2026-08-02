# ADR-0004 — Expansión de formatos de entrada mediante adaptadores

**Estado:** accepted  
**Fecha:** 2026-08-02  
**Decisores:** equipo Faro  
**Afecta:** alcance, contratos de datos, ingesta, procedencia, seguridad y pruebas

## Contexto

Faro ya procesa libros Excel y documentos PDF. Una empresa pequeña también puede recibir exportaciones CSV, facturas electrónicas XML, fotografías de documentos, integraciones JSON y correos exportados.

Agregar todos los formatos directamente a un único servicio produciría acoplamiento, reglas duplicadas y menor trazabilidad. Además, aceptar una extensión no significa que su contenido sea válido o seguro.

## Decisión

Faro utilizará un registro central de capacidades y un adaptador independiente por familia de formatos. Todos los adaptadores producirán modelos canónicos y conservarán procedencia.

### Fase 1 — formatos prioritarios

- CSV y TSV;
- XML UBL para documentos electrónicos;
- JPG, JPEG, PNG, TIFF y WebP mediante la ruta documental/OCR;
- JSON y NDJSON versionados.

### Fase 2 — interoperabilidad adicional

- EML y MBOX;
- ZIP con manifiesto y límites de seguridad;
- DOCX y ODT para documentos administrativos controlados.

### Fase 3 — evaluación futura

- OFX, QFX, MT940 y CAMT.053;
- Parquet como almacenamiento analítico interno.

La detección inicial podrá usar nombre, extensión y tipo MIME, pero cada adaptador deberá validar la firma o estructura interna antes de aceptar la fuente.

Cada entrada conservará como mínimo:

- archivo original y hash;
- tipo MIME declarado y detectado;
- formato y versión;
- adaptador utilizado;
- ubicación específica: fila, página, XPath, JSON Pointer, mensaje o miembro de archivo;
- valor original y normalizado;
- regla aplicada;
- confianza y estado de revisión cuando corresponda.

## Alternativas consideradas

### Convertir todo a Excel antes de ingresar

Rechazada porque pierde metadatos, obliga a trabajo manual y degrada la trazabilidad.

### Detectar únicamente por extensión

Rechazada porque una extensión puede ser incorrecta o maliciosa.

### Implementar todos los formatos en una sola entrega

Rechazada por exceso de alcance. La implementación se realizará por fases y cada formato mantendrá estado explícito.

## Consecuencias

Positivas:

- extensibilidad controlada;
- contratos y pruebas por formato;
- reutilización del modelo canónico;
- procedencia uniforme;
- menor dependencia de un proveedor de IA.

Costos y riesgos:

- más fixtures y pruebas;
- manejo de codificaciones y separadores;
- validación segura de XML y archivos comprimidos;
- límites de tamaño y recursos;
- compatibilidad de formatos ofimáticos.

## Plan de validación

Cada adaptador deberá aprobar:

1. archivo válido;
2. estructura inválida;
3. extensión engañosa;
4. codificación o versión no soportada;
5. archivo vacío o corrupto;
6. procedencia completa;
7. preservación del hash raw;
8. ejecución repetible;
9. mensajes de error estructurados;
10. límites de tamaño y recursos.

## Plan de reversión

Un adaptador podrá deshabilitarse por configuración sin afectar los formatos implementados. Los formatos no implementados deberán declararse `planned` o `out of scope` y nunca aceptarse silenciosamente.
