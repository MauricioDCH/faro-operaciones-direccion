"""Deterministic validation for structured invoices and quotations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from faro.domain.documents import QualityFinding


MONEY_TOLERANCE = Decimal("0.01")


def validate_required(fields: dict[str, object], required: Iterable[str]) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for name in required:
        value = fields.get(name)
        if value is None or value == "":
            findings.append(
                QualityFinding(
                    code="missing_required_field",
                    severity="error",
                    field=name,
                    message=f"Required document field is missing: {name}.",
                )
            )
    return findings


def validate_document_totals(
    *, subtotal: Decimal | None, tax: Decimal | None, total: Decimal | None
) -> list[QualityFinding]:
    if subtotal is None or tax is None or total is None:
        return []
    expected = subtotal + tax
    if abs(expected - total) <= MONEY_TOLERANCE:
        return []
    return [
        QualityFinding(
            code="document_total_mismatch",
            severity="error",
            field="total_cop",
            message="Document total does not equal subtotal plus tax.",
            observed_value=str(total),
            expected_value=str(expected),
        )
    ]


def validate_line_totals(lines: Iterable[object]) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for index, line in enumerate(lines, start=1):
        quantity = getattr(line, "quantity")
        unit_price = getattr(line, "unit_price_cop")
        line_total = getattr(line, "line_total_cop")
        expected = quantity * unit_price
        if abs(expected - line_total) > MONEY_TOLERANCE:
            findings.append(
                QualityFinding(
                    code="line_total_mismatch",
                    severity="error",
                    field=f"lines[{index}].line_total_cop",
                    message="Line total does not equal quantity multiplied by unit price.",
                    observed_value=str(line_total),
                    expected_value=str(expected),
                )
            )
    return findings


def validate_subtotal(lines: Iterable[object], subtotal: Decimal | None) -> list[QualityFinding]:
    materialized = tuple(lines)
    if subtotal is None or not materialized:
        return []
    expected = sum((getattr(line, "line_total_cop") for line in materialized), Decimal("0"))
    if abs(expected - subtotal) <= MONEY_TOLERANCE:
        return []
    return [
        QualityFinding(
            code="subtotal_line_sum_mismatch",
            severity="error",
            field="subtotal_cop",
            message="Subtotal does not equal the sum of line totals.",
            observed_value=str(subtotal),
            expected_value=str(expected),
        )
    ]


def validate_quotation_dates(
    *, issue_date: date | None, valid_until: date | None
) -> list[QualityFinding]:
    if issue_date is None or valid_until is None or valid_until >= issue_date:
        return []
    return [
        QualityFinding(
            code="invalid_valid_until",
            severity="error",
            field="valid_until",
            message="Quotation validity date cannot precede issue date.",
            observed_value=valid_until.isoformat(),
            expected_value=f">={issue_date.isoformat()}",
        )
    ]
