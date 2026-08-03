# Presets de indicadores

**Estado:** implemented
**Contrato:** `config/indicators.yaml` versión `1.0.0`

## Modelo de configuración

La empresa selecciona una preconfiguración y ajusta parámetros permitidos. Las fórmulas no se escriben en el archivo: permanecen en código probado.

Presets iniciales:

| Preset | Uso |
|---|---|
| `retail_distribution` | Vista general de una comercializadora o distribuidora |
| `sales_monitoring` | Seguimiento de ventas y productos líderes |
| `inventory_control` | Inventario, compras y diferencias documentales |

Selección temporal:

```bash
PYTHONPATH=src uv run python scripts/calculate_indicators.py --preset sales_monitoring
```

Selección predeterminada: cambiar `active_preset` en `config/indicators.yaml`.

## Indicadores de ejemplo

- `sales_total`: suma determinística de `line_total_cop` del último mes disponible.
- `sales_change`: variación porcentual contra el mes calendario anterior.
- `top_products`: ranking por ingresos o unidades.
- `low_inventory`: productos cuya disponibilidad está por debajo del punto de reorden.
- `order_invoice_mismatch`: conteo de hallazgos pedido-factura.
- `data_quality_summary`: hallazgos agrupados por severidad.
- `source_coverage`: cantidad de archivos por adaptador.
- `data_freshness`: días entre la fecha de corte y el dato más reciente.

## Restricciones

- No se acepta SQL libre.
- No se aceptan indicadores desconocidos.
- Cada parámetro tiene tipo y rango controlados.
- Cada resultado conserva versión de fórmula y evidencia.
- Un indicador nuevo requiere código, pruebas y actualización del catálogo.
