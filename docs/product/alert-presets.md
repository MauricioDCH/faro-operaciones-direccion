# Presets de alertas

**Estado:** implemented  
**Contrato:** `config/alerts.yaml` versión `1.0.0`

## Propósito

Cada empresa puede seleccionar una preconfiguración de alertas y ajustar umbrales, severidad, activación y tiempo de enfriamiento dentro de un catálogo seguro. Las reglas no aceptan SQL, Python ni expresiones arbitrarias.

Presets iniciales:

| Preset | Uso |
|---|---|
| `retail_distribution` | Ventas, inventario, compras y calidad |
| `sales_monitoring` | Objetivo y variación comercial |
| `inventory_control` | Reposición, pedidos y frescura de inventario |
| `data_quality` | Errores, conflictos y fechas inválidas |
| `custom_example` | Plantilla mínima para copiar y parametrizar |

## Fuentes permitidas

- resultados de indicadores persistidos en `indicator_result`;
- hallazgos persistidos en `quality_finding`.

## Operadores permitidos

- `greater_than`;
- `greater_or_equal`;
- `less_than`;
- `less_or_equal`;
- `equal`;
- `not_equal`.

## Agregaciones permitidas

- `single`;
- `count`;
- `sum`;
- `minimum`;
- `maximum`;
- `average`.

Los hallazgos de calidad solo permiten `count`. Una regla con fuente ausente o ambigua queda `not_evaluated` y no genera una alerta.

## Ejemplo

```json
{
  "rule_id": "ALERT-SALES-DROP-001",
  "name": "Caída relevante de ventas",
  "enabled": true,
  "source": {
    "type": "indicator",
    "id": "sales_change",
    "aggregation": "single"
  },
  "condition": {
    "operator": "less_than",
    "threshold": -15,
    "unit": "percent"
  },
  "severity": "critical",
  "cooldown_minutes": 1440
}
```

## Ejecución

```bash
PYTHONPATH=src uv run python scripts/evaluate_alerts.py --list-presets
PYTHONPATH=src uv run python scripts/evaluate_alerts.py --preset retail_distribution
```

## Persistencia y trazabilidad

Cada ejecución conserva:

- preset y hash de configuración;
- ejecución de indicadores utilizada;
- regla, operador y umbral;
- valor observado y unidad;
- estado `triggered`, `clear` o `not_evaluated`;
- resultados de indicador o hallazgos usados;
- registros y ubicaciones de procedencia;
- fecha de corte y fecha reproducible de evaluación.

Las evaluaciones se guardan en `alert_run` y `alert_evaluation`. Solo las condiciones activadas se materializan en `alert`.

## Límites actuales

- no se ejecuta SQL o código desde la configuración;
- no se envían correos ni mensajes todavía;
- `cooldown_minutes` queda persistido para una futura capa de notificaciones;
- `delivery_status=not_configured` comunica que la alerta está disponible en SQLite, pero no fue entregada por un canal externo;
- una nueva fuente o agregación requiere código y pruebas.
