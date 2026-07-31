# Registro de uso de IA

Registre únicamente decisiones, implementaciones, auditorías o correcciones sustantivas asistidas por IA. No duplique el historial rutinario del chat.

| Fecha/hora | Herramienta | Tarea | Resultado | Validación humana | Archivos/commit |
|---|---|---|---|---|---|
| 2026-07-31 | ChatGPT | Definir la arquitectura y el scaffold del repositorio | Estructura profesional del proyecto generada | Estructura y comprobaciones automatizadas revisadas | Scaffold inicial |
| 2026-07-31 | ChatGPT | Implementar la línea base sintética determinística | Generador, validador, 11 anomalías, manifiesto y pruebas creados | `make check` y `make validate-data` ejecutados; 10 pruebas y 11/11 anomalías | `src/faro/synthetic/`, `scripts/`, `config/data-quality-rules.yaml`, `data/expected/` |
