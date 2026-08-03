# ADR 0008 — Actualizaciones incrementales seguras desde el dashboard

- **Estado:** `accepted`
- **Fecha:** 2026-08-03
- **Decisores:** equipo Faro

## Contexto

El usuario empresarial necesita agregar información sin ejecutar comandos ni reconstruir manualmente el flujo completo. Una carga defectuosa no debe dejar el dashboard sin servicio ni corromper la última base válida.

## Decisión

Faro implementa un flujo incremental y atómico:

1. valida el archivo en una zona temporal;
2. ingiere solo la fuente nueva;
3. reutiliza las observaciones ya persistidas en SQLite;
4. recalcula la selección canónica;
5. escribe una base candidata;
6. calcula indicadores y alertas sobre la candidata;
7. verifica integridad;
8. conserva una copia de seguridad y reemplaza la base activa mediante `os.replace`.

Los trabajos de importación se registran en una base separada. La configuración empresarial se carga con un fallback seguro para evitar que un archivo de configuración inválido impida abrir el panel.

## Alternativas consideradas

### Reconstruir desde todos los archivos raw en cada carga

Rechazada para el flujo interactivo porque repite OCR e ingesta histórica, aumenta el tiempo de espera y obliga a recorrer fuentes no afectadas.

### Modificar la base activa directamente

Rechazada porque una excepción intermedia podría dejar datos incompletos o indicadores desalineados.

### Guardar la carga y esperar un proceso manual

Rechazada porque no satisface la experiencia de actualización desde el dashboard.

## Consecuencias

### Positivas

- la última base válida permanece disponible ante fallas;
- no se releen todas las fuentes históricas;
- indicadores y alertas se actualizan en la misma operación;
- los archivos duplicados se detectan por SHA-256;
- las observaciones anteriores conservan procedencia.

### Negativas

- la recanonización usa todas las observaciones persistidas;
- la carga sincrónica no es adecuada para lotes grandes;
- se requiere espacio temporal para candidata y copia de seguridad;
- el modo `upsert` agrega prioridad a la nueva fuente y puede generar conflictos trazables.

## Validación y reversión

- prueba de carga válida con registro nuevo;
- prueba de archivo inválido que conserva el hash binario de la base activa;
- `PRAGMA integrity_check` antes del reemplazo;
- verificación de copia `faro.db.bak`;
- la reversión consiste en restaurar la copia de seguridad o deshabilitar el endpoint de importación manteniendo el dashboard de solo lectura.
