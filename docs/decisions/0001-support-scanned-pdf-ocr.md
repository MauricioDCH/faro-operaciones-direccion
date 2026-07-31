# ADR-0001 — Soporte OCR para documentos PDF escaneados

**Estado:** accepted  
**Fecha:** 2026-07-31  
**Decisores:** equipo Faro  
**Afecta:** alcance, arquitectura, contratos de datos, validación y Demo Day

## Contexto

El alcance anterior asumía que las facturas PDF sintéticas contenían texto extraíble y dejaba el OCR general fuera del MVP.

En el segmento objetivo es razonable que una micro o pequeña empresa reciba facturas y cotizaciones como documentos escaneados. Excluirlos limitaría el valor operativo de Faro y produciría una demostración poco representativa del problema.

El proyecto debe seguir siendo reproducible, auditable y viable durante la Maratón. Por tanto, no se adoptará un OCR universal para cualquier documento, idioma o calidad de imagen.

## Decisión

Faro soportará dos rutas para documentos PDF sintéticos:

1. extracción directa cuando la página contenga texto suficiente;
2. OCR cuando la página sea escaneada o el texto nativo sea insuficiente.

Los tipos documentales garantizados serán:

- factura de proveedor;
- cotización de proveedor.

El flujo será:

```text
PDF
  ↓
inspección por página
  ├── texto suficiente → extracción directa
  └── texto insuficiente → renderizado + OCR
                              ↓
                       texto, confianza y evidencia
  ↓
clasificación y extracción asistida por IA
  ↓
validación determinística
  ↓
revisión humana cuando corresponda
```

La IA podrá clasificar el documento, interpretar campos y proponer correspondencias. El código determinístico validará formatos, fechas, cantidades, subtotales, impuestos, totales, relaciones y duplicados.

Toda página procesada conservará:

- archivo y hash de origen;
- número de página;
- ruta utilizada: `native_text` u `ocr`;
- motor y versión cuando se utilice OCR;
- idioma configurado;
- confianza disponible;
- fragmento o región de evidencia;
- estado de revisión humana.

## Límites aprobados

El MVP garantiza únicamente:

- documentos sintéticos;
- idioma español;
- facturas y cotizaciones;
- PDF con texto, escaneado o mixto;
- entre una y tres páginas por documento;
- plantillas conocidas o variaciones controladas;
- texto impreso legible;
- procesamiento local reproducible.

Quedan fuera del alcance:

- manuscritos complejos;
- fotografías severamente deformadas;
- documentos protegidos con contraseña;
- tablas arbitrarias sin estructura reconocible;
- formularios universales;
- documentos reales durante la Maratón;
- aceptación automática de campos con confianza insuficiente.

## Alternativas consideradas

### Mantener únicamente PDF con texto

Rechazada porque no cubre documentos escaneados frecuentes en el escenario objetivo.

### Delegar todo el documento a un modelo multimodal

Rechazada como ruta única porque reduce reproducibilidad, aumenta dependencia externa y dificulta validar procedencia y cálculos.

### Implementar OCR universal

Rechazada por exceso de alcance y riesgo para el cronograma.

## Consecuencias

Positivas:

- escenario más realista;
- mejor cobertura de facturas y cotizaciones;
- separación clara entre recuperación de texto, interpretación y validación;
- evidencia por página y método;
- revisión humana explícita.

Costos y riesgos:

- nuevas dependencias del sistema;
- mayor tiempo de procesamiento;
- resultados sensibles a calidad y versión del motor;
- necesidad de fixtures escaneados;
- necesidad de pruebas específicas para OCR y baja confianza.

## Validación

La implementación no podrá marcarse como `implemented` hasta aprobar:

1. PDF con texto nativo;
2. PDF completamente escaneado;
3. PDF mixto;
4. factura soportada;
5. cotización soportada;
6. página ilegible;
7. documento no soportado;
8. campo obligatorio ausente;
9. total inconsistente;
10. baja confianza enviada a revisión;
11. procedencia por archivo y página;
12. ejecución reproducible con versiones fijadas.

## Plan de reversión

Si el OCR no alcanza la calidad o reproducibilidad mínima, la ruta OCR se deshabilitará mediante configuración y se conservará la extracción de texto nativo. Los documentos escaneados quedarán `pending_review` o `unsupported`, sin inventar datos.
