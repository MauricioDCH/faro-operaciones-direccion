# Datos sintéticos de Faro

Durante la Maratón solo se permiten datos sintéticos. Ningún archivo de esta carpeta debe contener información personal, empresarial, financiera o confidencial real.

## Estructura

- `raw/`: fuentes sintéticas inmutables generadas para la demostración;
- `processed/`: resultados de validación, normalización y consolidación;
- `expected/`: verdad de referencia y manifiesto de hashes;
- `samples/`: fixtures pequeños, incluido el lote reproducible del plugin de correo.

## Generación y validación

```bash
make generate-data
make validate-data
```

La semilla predeterminada es `20260731`. Una ejecución existente y consistente se reutiliza sin sobrescribirla. Para reemplazarla de manera explícita:

```bash
PYTHONPATH=src uv run python scripts/generate_synthetic_data.py --force
```

`data/expected/dataset_manifest.json` registra conteos y hashes SHA-256 de las fuentes. La validación falla cuando un archivo generado cambia sin actualizar la línea base aprobada.
