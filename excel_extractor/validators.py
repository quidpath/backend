"""Validation helpers for financial extractions."""

from __future__ import annotations

from typing import Dict

from .exceptions import ValidationError


def _within_tolerance(expected: int, actual: int, tolerance: float) -> bool:
    if expected == 0:
        return abs(actual) <= 1
    return abs(expected - actual) / abs(expected) <= tolerance


def validate_financials(payload: Dict[str, int], tolerance: float = 0.01) -> None:
    """
    Validate internal financial relationships.

    Raises:
        ValidationError: if any rule fails.
    """
    total_revenue = payload["total_revenue"]
    cogs = payload["cogs"]
    gross_profit = payload["gross_profit"]
    operating_expenses = payload["operating_expenses"]
    operating_income = payload["operating_income"]
    interest_expense = payload["interest_expense"]
    taxes = payload["taxes"]
    net_income = payload["net_income"]

    rules = (
        (
            "gross_profit",
            total_revenue - cogs,
            gross_profit,
            "Gross profit must equal total revenue minus COGS.",
        ),
        (
            "operating_income",
            gross_profit - operating_expenses,
            operating_income,
            "Operating income must equal gross profit minus operating expenses.",
        ),
        (
            "net_income",
            operating_income - interest_expense - taxes,
            net_income,
            "Net income must equal operating income minus interest and taxes.",
        ),
    )

    for field, expected, actual, message in rules:
        if not _within_tolerance(expected, actual, tolerance):
            raise ValidationError(
                f"{message} Expected {expected:,} for {field}, got {actual:,}."
            )
