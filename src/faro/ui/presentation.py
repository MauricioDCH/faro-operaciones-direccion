"""Spanish business-language presentation rules for the base dashboard."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


ENTITY_LABELS = {
    "sale_line": "Movimientos de venta",
    "product": "Productos",
    "inventory_snapshot": "Registros de inventario",
    "document": "Documentos",
    "customer": "Clientes",
    "document_page": "Páginas procesadas",
    "invoice": "Facturas",
    "invoice_line": "Productos facturados",
    "purchase_order_line": "Productos pedidos",
    "supplier": "Proveedores",
    "quotation": "Cotizaciones",
    "quotation_line": "Productos cotizados",
}
SOURCE_LABELS = {
    "xlsx": "Archivos de Excel",
    "delimited": "Archivos CSV o TSV",
    "json_records": "Archivos JSON",
    "json": "Archivos JSON",
    "pdf": "Documentos PDF",
    "image_document": "Imágenes de documentos",
    "image": "Imágenes de documentos",
    "ubl_xml": "Facturas electrónicas XML",
    "unknown": "Fuentes anteriores sin clasificación",
}
SEVERITY_LABELS = {
    "critical": "Urgente",
    "error": "Importante",
    "warning": "Revisar",
    "info": "Información",
}
REVIEW_LABELS = {
    "pending": "Pendiente",
    "pending_review": "Pendiente",
    "accepted": "Revisada",
}
DELIVERY_LABELS = {
    "not_configured": "Visible solo en Faro",
    "sent": "Enviada",
    "pending": "Pendiente de envío",
}
OPERATOR_LABELS = {
    "greater_than": "mayor que",
    "greater_or_equal": "igual o mayor que",
    "less_than": "menor que",
    "less_or_equal": "igual o menor que",
    "equal": "igual a",
    "not_equal": "diferente de",
}
UNIT_LABELS = {
    "COP": "COP",
    "percent": "%",
    "day": "días",
    "unit": "unidades",
    "product": "productos",
    "finding": "casos",
    "source_file": "archivos",
    "products": "productos",
    "findings": "casos",
    "days": "días",
    "units": "unidades",
}
INDICATOR_COPY = {
    "sales_total": (
        "Ventas del periodo",
        "Dinero vendido en el periodo más reciente disponible.",
    ),
    "sales_change": (
        "Cambio en las ventas",
        "Compara las ventas actuales con las del periodo anterior.",
    ),
    "top_products": (
        "Productos más vendidos",
        "Muestra qué productos generaron más ventas.",
    ),
    "low_inventory": (
        "Productos por reponer",
        "Productos que están en o por debajo de su nivel mínimo.",
    ),
    "order_invoice_mismatch": (
        "Diferencias entre pedidos y facturas",
        "Casos donde lo pedido no coincide con lo facturado.",
    ),
    "data_quality_summary": (
        "Problemas encontrados en los datos",
        "Registros que deben revisarse antes de tomar decisiones.",
    ),
    "source_coverage": (
        "Información recibida",
        "Cantidad de archivos procesados por tipo.",
    ),
    "data_freshness": (
        "Antigüedad de la información",
        "Días transcurridos desde la última actualización disponible.",
    ),
}


def decimal_value(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except (InvalidOperation, ValueError):
        return None


def format_number(value: Any, unit: str | None, currency: str = "COP") -> str:
    number = decimal_value(value)
    if number is None:
        return "Sin dato"
    if unit == "COP":
        return f"$ {number:,.0f} {currency}".replace(",", ".")
    if unit == "percent":
        return f"{number:,.1f} %".replace(",", "X").replace(".", ",").replace("X", ".")
    if number == number.to_integral():
        text = f"{number:,.0f}".replace(",", ".")
    else:
        text = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    label = UNIT_LABELS.get(unit or "", unit or "")
    return f"{text} {label}".strip()


def entity_label(value: str) -> str:
    return ENTITY_LABELS.get(value, value.replace("_", " ").capitalize())


def source_label(value: str) -> str:
    return SOURCE_LABELS.get(value, value.replace("_", " ").capitalize())


def alert_copy(alert: dict[str, Any], *, currency: str) -> dict[str, Any]:
    alert_type = alert.get("alert_type", "")
    action_map = {
        "low_inventory": (
            "Reponer inventario",
            "Confirma las existencias y prepara una compra o traslado del producto.",
        ),
        "order_invoice_mismatch": (
            "Comparar pedido y factura",
            "Revisa cantidades y precios antes de aprobar el pago al proveedor.",
        ),
        "data_freshness": (
            "Actualizar la información",
            "Carga un archivo reciente para evitar decisiones con datos antiguos.",
        ),
        "sales_change": (
            "Revisar la caída de ventas",
            "Compara productos, clientes y canales para encontrar la causa del cambio.",
        ),
        "data_quality_summary": (
            "Corregir datos importantes",
            "Empieza por los registros marcados como error; pueden alterar los reportes.",
        ),
        "cross_source_conflict": (
            "Confirmar cuál dato es correcto",
            "Dos fuentes dicen cosas distintas. Revisa la evidencia antes de decidir.",
        ),
        "invalid_date": (
            "Corregir fechas",
            "Ajusta las fechas inválidas para que los periodos se calculen correctamente.",
        ),
    }
    action_title, action_text = action_map.get(
        alert_type,
        ("Revisar esta situación", "Abre el detalle y confirma la información relacionada."),
    )
    severity = alert.get("severity", "info")
    value_text = format_number(alert.get("observed_value"), alert.get("unit"), currency)
    return {
        **alert,
        "severity_label": SEVERITY_LABELS.get(severity, "Información"),
        "value_text": value_text,
        "action_title": action_title,
        "action_text": action_text,
        "simple_description": _simple_alert_description(alert_type, value_text),
        "rule_text": (
            f"Se activa cuando el valor es {OPERATOR_LABELS.get(alert.get('operator'), alert.get('operator'))} "
            f"{format_number(alert.get('threshold_value'), alert.get('unit'), currency)}."
        ),
        "review_label": REVIEW_LABELS.get(alert.get("review_status"), "Pendiente"),
        "delivery_label": DELIVERY_LABELS.get(
            alert.get("delivery_status"), "Visible solo en Faro"
        ),
    }


def _simple_alert_description(alert_type: str, value_text: str) -> str:
    templates = {
        "low_inventory": f"Hay {value_text} que necesitan reposición.",
        "order_invoice_mismatch": f"Se encontraron {value_text} entre pedidos y facturas.",
        "data_freshness": f"La información tiene {value_text} de antigüedad.",
        "sales_change": f"Las ventas cambiaron {value_text} frente al periodo anterior.",
        "data_quality_summary": f"Hay {value_text} que pueden afectar los reportes.",
        "cross_source_conflict": f"Hay {value_text} donde dos fuentes no coinciden.",
        "invalid_date": f"Hay {value_text} con fechas que deben corregirse.",
    }
    return templates.get(alert_type, f"Faro encontró una situación que requiere atención: {value_text}.")


def indicator_copy(item: dict[str, Any], *, currency: str) -> dict[str, Any]:
    indicator_id = item.get("indicator_id", "")
    title, meaning = INDICATOR_COPY.get(
        indicator_id,
        (item.get("indicator_name", "Indicador"), "Resultado calculado con la información disponible."),
    )
    value = decimal_value(item.get("numeric_value"))
    tone = "neutral"
    interpretation = "Este dato está disponible para consulta."
    if indicator_id == "sales_change" and value is not None:
        if value < 0:
            tone = "danger"
            interpretation = "Las ventas bajaron frente al periodo anterior."
        else:
            tone = "good"
            interpretation = "Las ventas subieron frente al periodo anterior."
    elif indicator_id == "low_inventory":
        tone = "warning"
        interpretation = "Este producto requiere reposición."
    elif indicator_id == "order_invoice_mismatch" and value and value > 0:
        tone = "danger"
        interpretation = "Hay diferencias que conviene revisar antes de pagar."
    elif indicator_id == "data_quality_summary" and value and value > 0:
        tone = "warning"
        interpretation = "Hay información que debe corregirse."
    elif indicator_id == "data_freshness" and value is not None:
        tone = "good" if value <= 1 else "warning" if value <= 3 else "danger"
        interpretation = (
            "La información está reciente."
            if value <= 1
            else "Conviene actualizar esta información."
        )
    return {
        **item,
        "title": title,
        "meaning": meaning,
        "value_text": format_number(item.get("numeric_value"), item.get("unit"), currency),
        "unit_label": UNIT_LABELS.get(item.get("unit", ""), item.get("unit", "")),
        "dimension_label": _dimension_label(item),
        "interpretation": interpretation,
        "tone": tone,
    }


def _dimension_label(item: dict[str, Any]) -> str:
    value = item.get("dimension_value")
    if not value:
        return "Vista general"
    if item.get("indicator_id") == "data_freshness":
        return {
            "inventory": "Inventario",
            "invoices": "Facturas",
            "orders": "Pedidos",
            "sales": "Ventas",
        }.get(value, str(value))
    if item.get("dimension") == "severity":
        return SEVERITY_LABELS.get(value, str(value).capitalize())
    return str(value)
