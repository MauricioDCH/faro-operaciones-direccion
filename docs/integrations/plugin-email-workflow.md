# Flujo de correo mediante plugins de IA

**Estado:** línea base aprobada para implementación  
**Versión:** 1.0  
**Fuente canónica para:** integración ChatGPT/Claude–Gmail

---

## 1. Decisión

Faro utilizará un plugin o integración de IA para consultar una cuenta Gmail dedicada con correos sintéticos.

El plugin no forma parte del proceso local de Python. Opera dentro de ChatGPT o Claude y entrega a Faro un lote JSON portable.

```text
Gmail sintético
    ↓
plugin o integración
    ↓
ChatGPT / Claude
    ↓
plugin-email-batch.json
    ↓
Faro
```

Esta frontera evita acoplar el backend a una plataforma específica y permite reproducir el mismo contrato con un fixture.

---

## 2. Responsabilidades

### Plugin o integración

- autenticar el acceso autorizado a Gmail;
- buscar mensajes según una consulta delimitada;
- devolver referencias o citas disponibles;
- respetar los permisos de la cuenta conectada.

### IA

- clasificar el mensaje;
- extraer campos semánticos;
- producir confianza y evidencia;
- devolver JSON conforme al esquema;
- declarar limitaciones;
- evitar inferencias no sustentadas.

### Faro

- validar el lote;
- preservar el artefacto original;
- detectar duplicados;
- comprobar entidades y reglas;
- solicitar revisión humana;
- consolidar datos aprobados;
- calcular indicadores y alertas.

---

## 3. Modos aprobados

### `plugin_live`

Utiliza una integración real disponible en la cuenta:

```text
AI_PLUGIN_PLATFORM=chatgpt
AI_PLUGIN_APP=gmail
EMAIL_INGESTION_MODE=plugin_artifact
```

La disponibilidad debe comprobarse en la cuenta usada durante la Maratón. No se declara `implemented` hasta ejecutar una prueba real.

### `plugin_fixture`

Utiliza:

```text
data/samples/plugin-email-batch.example.json
```

Este modo reproduce el contrato sin afirmar que existe una conexión activa.

---

## 4. Configuración de la cuenta

La cuenta debe:

- estar dedicada a Faro;
- contener únicamente datos sintéticos;
- utilizar remitentes y dominios ficticios;
- excluir correos personales;
- excluir información de empresas reales;
- permitir revocar la conexión después del evento.

---

## 5. Flujo operativo

1. Conectar Gmail dentro de ChatGPT o Claude.
2. Confirmar que la integración puede buscar mensajes.
3. Ejecutar `prompts/email-plugin-extraction.md`.
4. Delimitar fechas, etiquetas y remitentes.
5. Obtener JSON puro.
6. Guardarlo como `plugin-email-batch.json`.
7. Validarlo con `schemas/plugin-email-batch.schema.json`.
8. Importarlo desde el dashboard.
9. Revisar campos inciertos.
10. Ejecutar reglas e indicadores.

---

## 6. Seguridad y control humano

El flujo autorizado es de solo lectura.

Quedan prohibidos en el MVP:

- enviar respuestas;
- eliminar correos;
- archivar mensajes;
- cambiar etiquetas;
- modificar contenido;
- ejecutar compras o pedidos;
- usar cuentas personales;
- ocultar que se utilizó un fixture.

Las propuestas de IA no cambian registros canónicos sin revisión o validación determinística.

---

## 7. Portabilidad

ChatGPT y Claude deben producir el mismo contrato. El backend no debe contener condiciones de negocio como:

```text
if platform == "chatgpt": ...
```

Las diferencias de plataforma se limitan al adaptador de entrada y a los metadatos de `plugin_run`.

---

## 8. Criterios de aceptación

1. La cuenta contiene solo datos sintéticos.
2. La integración recupera mensajes de solo lectura.
3. La salida valida contra el esquema.
4. Cada mensaje conserva una referencia verificable o una limitación explícita.
5. Faro detecta duplicados entre lotes.
6. Las propuestas inciertas requieren revisión.
7. El fixture usa exactamente el mismo contrato.
8. La demostración distingue `plugin_live` de `plugin_fixture`.
9. El núcleo funciona aunque el plugin no esté disponible.
10. La evidencia puede rastrearse desde el dashboard.

---

## 9. Dependencias externas

La disponibilidad de plugins, apps o integraciones depende del plan, la región, la superficie y la configuración de la cuenta. Esta capacidad debe verificarse antes del Demo Day.

La documentación oficial vigente de cada plataforma constituye la fuente de verdad sobre disponibilidad y permisos.
