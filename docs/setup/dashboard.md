# Dashboard base de Faro

## Estado

`implemented`

## Objetivo

Presentar decisiones operativas en lenguaje claro y permitir cargas incrementales sin ejecutar comandos ni reemplazar una base válida cuando un archivo falla.

## Ejecutar

```bash
uv sync --locked
make dashboard
```

Abrir:

```text
http://127.0.0.1:8080/dashboard
```

## Experiencia principal

La vista base prioriza:

- estado general del negocio;
- acciones recomendadas ordenadas por urgencia;
- indicadores explicados en español;
- evidencia técnica bajo demanda;
- actualización segura desde el navegador.

Los términos internos, identificadores y reglas permanecen ocultos hasta activar **Mostrar detalles técnicos**.

## Actualización incremental

El botón **Actualizar información** procesa un archivo nuevo sin volver a leer todas las fuentes históricas.

Flujo:

1. Guarda el archivo en una zona temporal no pública.
2. Verifica nombre, tamaño, extensión, formato real y perfil seleccionado.
3. Rechaza hashes ya procesados.
4. Ingiere únicamente el archivo nuevo.
5. Combina las observaciones nuevas con las ya almacenadas en SQLite.
6. Construye una base candidata.
7. Calcula indicadores y alertas sobre la candidata.
8. Ejecuta `PRAGMA integrity_check`.
9. Archiva el archivo raw y crea `faro.db.bak`.
10. Reemplaza `faro.db` de forma atómica.

Una falla en los pasos 1 a 8 elimina la candidata y conserva intacta la base activa.

## Formatos del botón

- XLSX: catálogos, ventas, inventario y pedidos;
- CSV y TSV;
- JSON, NDJSON y JSONL;
- PDF;
- JPG, JPEG, PNG, TIFF y WebP;
- XML UBL.

Los archivos tabulares requieren que el usuario indique qué información contienen. PDF, imágenes y XML se clasifican mediante el adaptador correspondiente.

## Modos

- `upsert`: la fuente recién cargada recibe prioridad para el mismo identificador empresarial;
- `append`: conserva la prioridad normal del formato.

Las observaciones anteriores no se borran. Permanecen disponibles para procedencia y conflictos entre fuentes.

## Resiliencia

- una configuración empresarial inválida activa un perfil seguro integrado;
- una base ausente o ilegible produce una pantalla explicativa, no un error sin controlar;
- el historial de cargas vive en `data/processed/faro_imports.db`, separado de la base operacional;
- una carga fallida no reemplaza `data/processed/faro.db`;
- el servidor se mantiene local en `127.0.0.1` por defecto.

No es técnicamente posible prometer que el software nunca sufrirá una falla. El contrato implementado es **fallar de forma segura, conservar la última base válida y explicar el resultado al usuario**.

## Variables

```text
FARO_DATABASE_PATH
FARO_COMPANY_CONFIG_PATH
FARO_DASHBOARD_HOST
FARO_DASHBOARD_PORT
FARO_IMPORT_DATABASE_PATH
FARO_IMPORT_STAGING_DIR
FARO_IMPORT_ARCHIVE_DIR
FARO_IMPORT_MAX_FILE_SIZE_MB
```

## Limitaciones

- no hay autenticación ni acceso remoto aprobado;
- las cargas son sincrónicas y adecuadas para archivos pequeños del MVP;
- no existe edición manual de registros desde el panel;
- datos empresariales reales siguen bloqueados hasta implementar privacidad, control de acceso, copias verificadas y recuperación operativa.
