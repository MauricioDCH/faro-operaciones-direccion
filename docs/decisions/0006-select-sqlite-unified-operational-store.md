# ADR-0006 — Seleccionar SQLite como almacén operacional unificado

**Estado:** accepted
**Fecha:** 2026-08-02
**Decisores:** equipo Faro
**Afecta:** persistencia, consolidación, procedencia, portabilidad y reproducibilidad

## Contexto

Faro ya cuenta con adaptadores para XLSX, CSV/TSV, JSON/NDJSON, PDF, imágenes y XML UBL. Los resultados permanecían separados en objetos de ingesta, lo que impedía consultar una única versión operacional de productos, ventas, inventarios, pedidos y documentos.

El producto debe ejecutarse localmente en Linux y Windows, funcionar sin un servidor externo y reconstruirse desde fuentes inmutables. La persistencia debe conservar observaciones de cada fuente, seleccionar registros canónicos mediante reglas explícitas y mantener la evidencia original.

## Decisión

Se utilizará SQLite mediante la biblioteca estándar de Python como almacén operacional local.

La consolidación:

1. ingiere todas las fuentes implementadas;
2. conserva cada observación aceptada o rechazada en una capa de auditoría;
3. selecciona un registro canónico únicamente entre observaciones `accepted`;
4. aplica una prioridad de fuente versionada;
5. registra conflictos y duplicados entre fuentes;
6. persiste procedencia por celda, fila, página, región, JSON Pointer o XPath;
7. registra un evento de transformación por registro canónico;
8. construye la base en un archivo temporal;
9. ejecuta `PRAGMA integrity_check`;
10. reemplaza la base anterior de forma atómica.

El artefacto local será `data/processed/faro.db` y no se versionará. La reproducibilidad se verificará mediante un hash lógico de filas ordenadas, no mediante igualdad binaria del archivo SQLite, porque el layout físico puede variar entre versiones y sistemas operativos.

## Prioridad inicial de fuentes

| Fuente | Prioridad |
|---|---:|
| XML UBL | 100 |
| XLSX | 90 |
| PDF | 85 |
| Imagen OCR | 80 |
| JSON / NDJSON | 70 |
| CSV / TSV | 60 |

La prioridad no elimina observaciones alternativas. Todas permanecen en `record_observation` y cualquier desacuerdo genera un hallazgo trazable.

## Alternativas consideradas

### Archivos JSON consolidados

Rechazada como persistencia principal porque complica relaciones, restricciones, consultas y actualizaciones atómicas.

### PostgreSQL

Pospuesta. Ofrece concurrencia y operación multiusuario, pero exige infraestructura adicional que no es necesaria para la primera versión local.

### DuckDB o Parquet

Pospuestos para analítica. Son adecuados para consultas columnares, pero no sustituyen el modelo operacional relacional y sus claves foráneas.

## Consecuencias

Positivas:

- instalación sin servidor;
- compatibilidad nativa con Linux y Windows;
- transacciones y claves foráneas;
- consultas SQL reproducibles;
- base regenerable desde fuentes;
- separación entre observaciones y registros canónicos;
- reemplazo atómico ante una ejecución correcta.

Costos y riesgos:

- concurrencia limitada para múltiples escritores;
- no es suficiente todavía para una operación multiusuario en red;
- requiere migraciones explícitas cuando cambie el esquema;
- las rutas OCR continúan dependiendo de ejecutables externos;
- el timestamp fijo actual pertenece al dataset sintético y debe configurarse en una operación real.

## Plan de validación

La capacidad se considera implementada cuando:

- todas las fuentes implementadas pueden alimentar una sola base;
- solo registros aceptados llegan a tablas canónicas;
- las observaciones y hallazgos permanecen auditables;
- las claves foráneas y `integrity_check` son válidos;
- dos ejecuciones con las mismas entradas producen el mismo hash lógico;
- una reconstrucción fallida conserva la base anterior;
- los hashes de fuentes no cambian;
- las pruebas se ejecutan en Linux y en la matriz de Windows aprobada.

## Plan de reversión

Si la consolidación falla, se conserva la base anterior y se elimina el archivo temporal. SQLite puede sustituirse posteriormente detrás de la interfaz de persistencia, manteniendo los contratos canónicos y las reglas de selección.
