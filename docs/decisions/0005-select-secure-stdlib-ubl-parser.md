# ADR-0005 — Seleccionar parser UBL local y seguro

**Estado:** accepted  
**Fecha:** 2026-08-02  
**Decisores:** equipo Faro

## Contexto

Faro debe interpretar facturas UBL 2.1 en Linux y Windows, preservar XPath y evitar dependencias obligatorias de red o de un proveedor de IA. XML puede contener construcciones peligrosas como DTD y entidades externas.

## Decisión

El adaptador `ubl_xml` utiliza `xml.etree.ElementTree` de la biblioteca estándar y aplica controles previos y posteriores: límite de tamaño, rechazo explícito de `DOCTYPE` y `ENTITY`, límites de elementos, profundidad y texto, raíces permitidas y versión UBL aprobada.

Se soportan `Invoice` y `AttachedDocument` con una factura `Invoice` embebida como XML escapado, elemento directo o contenido base64 XML. El resultado se mapea al modelo canónico de factura y conserva XPath lógico por campo.

La implementación no valida firmas, CUFE, estado tributario, XSD oficial completo ni cumplimiento jurídico ante la DIAN.

## Alternativas consideradas

- `lxml`: ofrece validación XSD avanzada, pero agrega una dependencia binaria y requiere endurecimiento explícito del parser.
- `defusedxml`: endurece XML, pero agrega una dependencia para controles que este alcance puede aplicar explícitamente.
- Servicio externo: rechazado por privacidad, reproducibilidad y disponibilidad.

## Consecuencias

- No se agregan dependencias Python.
- La ejecución es portable entre Linux y Windows.
- La seguridad depende de pruebas de regresión y límites explícitos.
- La validación tributaria completa queda fuera del alcance.

## Plan de validación y reversión

Se prueban factura directa, `AttachedDocument`, XML base64, DTD/entidades, raíz y versión no soportadas, límites, campos, totales, procedencia e inmutabilidad. Si los controles resultan insuficientes para datos reales, se sustituirá el parser detrás del adaptador sin cambiar el contrato canónico.
