# Registro de uso de IA

Registre únicamente decisiones, implementaciones, auditorías o correcciones sustantivas asistidas por IA. No duplique el historial rutinario del chat.

| Fecha/hora | Herramienta | Tarea | Resultado | Validación humana | Archivos/commit |
|---|---|---|---|---|---|
| 2026-07-31 | ChatGPT | Definir la arquitectura y el scaffold del repositorio | Estructura profesional del proyecto generada | Estructura y comprobaciones automatizadas revisadas | Scaffold inicial |
| 2026-07-31 | ChatGPT | Implementar la línea base sintética determinística | Generador, validador, 11 anomalías, manifiesto y pruebas creados | `make check` y `make validate-data` ejecutados; 10 pruebas y 11/11 anomalías | `src/faro/synthetic/`, `scripts/`, `config/data-quality-rules.yaml`, `data/expected/` |
| 2026-07-31 | ChatGPT | Evaluar y documentar soporte OCR para PDF escaneados | ADR, alcance, requisitos, contratos, arquitectura y plan de validación actualizados | Pendiente revisión y aprobación mediante Pull Request | `docs/decisions/0001-support-scanned-pdf-ocr.md`, `docs/product/`, `docs/data/`, `docs/architecture/system-design.md`, `docs/evaluation/validation-plan.md` |
| 2026-07-31 | ChatGPT | Implementar la primera ruta local PDF/OCR | Selección Poppler/Tesseract, modelos, procedencia, CLI, configuración y pruebas | Validado con 25 pruebas y fixtures nativo, escaneado y mixto | `docs/decisions/0002-select-local-pdf-ocr-stack.md`, `src/faro/extraction/`, `tests/` |
