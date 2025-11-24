"""Statement specifications and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Sequence, Tuple

from .exceptions import ValidationError

Validator = Callable[[Dict[str, int]], None]


@dataclass(frozen=True)
class StatementSpec:
    """Defines the structure of a financial statement."""

    name: str
    label_mapping: Dict[str, Sequence[str]]
    required_fields: Tuple[str, ...]
    optional_fields: Tuple[str, ...] = ()
    validators: Tuple[Validator, ...] = field(default_factory=tuple)


def _within_tolerance(expected: int, actual: int, tolerance: float = 0.01) -> bool:
    """Check if actual value is within tolerance of expected value."""
    if expected == 0:
        return abs(actual) <= 1
    return abs(expected - actual) / abs(expected) <= tolerance


def _validate_income_statement(payload: Dict[str, int]) -> None:
    """Validate income statement with 1% tolerance for rounding differences."""
    tolerance = 0.01
    total_revenue = payload["total_revenue"]
    cogs = payload["cogs"]
    gross_profit = payload["gross_profit"]
    operating_expenses = payload["operating_expenses"]
    operating_income = payload["operating_income"]
    interest_expense = payload["interest_expense"]
    taxes = payload["taxes"]
    net_income = payload["net_income"]
    
    if not _within_tolerance(total_revenue - cogs, gross_profit, tolerance):
        raise ValidationError(
            f"Gross profit mismatch. Expected {total_revenue - cogs:,}, got {gross_profit:,}."
        )
    if not _within_tolerance(gross_profit - operating_expenses, operating_income, tolerance):
        raise ValidationError(
            f"Operating income mismatch. Expected {gross_profit - operating_expenses:,}, got {operating_income:,}."
        )
    if not _within_tolerance(operating_income - interest_expense - taxes, net_income, tolerance):
        raise ValidationError(
            f"Net income mismatch. Expected {operating_income - interest_expense - taxes:,}, got {net_income:,}."
        )


def _validate_balance_sheet(payload: Dict[str, int]) -> None:
    """Validate balance sheet with 1% tolerance for rounding differences."""
    tolerance = 0.01
    total_assets = payload["total_assets"]
    total_liabilities = payload["total_liabilities"]
    shareholders_equity = payload["shareholders_equity"]
    
    if not _within_tolerance(total_liabilities + shareholders_equity, total_assets, tolerance):
        raise ValidationError(
            f"Balance sheet does not balance (Assets ≠ Liabilities + Equity). "
            f"Expected {total_liabilities + shareholders_equity:,} for total assets, got {total_assets:,}."
        )


INCOME_STATEMENT_SPEC = StatementSpec(
    name="income_statement",
    required_fields=(
        "total_revenue",
        "cogs",
        "gross_profit",
        "operating_expenses",
        "operating_income",
        "interest_expense",
        "taxes",
        "net_income",
    ),
    optional_fields=(
        "risk_level",
        "depreciation",
        "amortization",
        "ebit",
        "ebitda",
        "operating_profit",
        "sales_expenses",
        "admin_expenses",
        "finance_costs",
        "total_expenses",
        "other_income",
        "other_expenses",
    ),
    label_mapping={
        "total_revenue": [
            "total revenue", "revenue", "sales", "turnover", "net sales", "income",
            "total sales", "sales revenue", "revenue from operations", "net revenue",
            "total for operating income", "operating income total",  # Some P&L statements use this
            "revenue sales", "total income", "operating revenue", "sales income"  # ✅ FIX: More variations
        ],
        "cogs": [
            "cogs", "cost of goods sold", "cost of revenue", "cost of sales",
            "cost goods sold", "costs of goods sold", "direct costs",
            "total for cost of goods sold", "cost of goods sold total",
            "total cogs", "cost goods", "direct labor costs", "purchases",  # ✅ FIX: More variations
            "materials", "parts materials", "labor costs"  # Common variations
        ],
        "gross_profit": [
            "gross profit", "gross income", "gross margin", "gross earnings"
        ],
        "operating_expenses": [
            "operating expenses", "total expenses", "expenses", "opex", "operating costs",
            "operating expenditure", "total operating expenses", "operating expense",
            "total for operating expense", "operating expense total",
            "total opex", "operating overhead", "total operating costs"  # ✅ FIX: More variations for totals
        ],
        "operating_income": [
            "operating income", "operating profit", "ebit", "earnings before interest and tax",
            "operating earnings", "operating result", "operating profit/loss"
        ],
        "interest_expense": [
            "interest expense", "interest paid", "interest", "interest charges",
            "finance costs", "financial expenses"
        ],
        "taxes": [
            "taxes", "income tax", "tax expense", "income taxes", "tax provision",
            "taxation", "tax"
        ],
        "net_income": [
            "net income", "net profit", "profit after tax", "net earnings",
            "profit for the year", "net profit after tax", "bottom line"
        ],
        "risk_level": ["risk level", "risk", "overall risk"],
    },
    validators=(_validate_income_statement,),
)


BALANCE_SHEET_SPEC = StatementSpec(
    name="balance_sheet",
    required_fields=("total_assets", "total_liabilities", "shareholders_equity"),
    label_mapping={
        "total_assets": ["total assets", "assets", "asset base"],
        "total_liabilities": ["total liabilities", "liabilities", "total debt"],
        "shareholders_equity": [
            "shareholders equity",
            "stockholders equity",
            "shareholder equity",
            "equity",
        ],
    },
    validators=(_validate_balance_sheet,),
)


DEFAULT_STATEMENT_SPECS = (INCOME_STATEMENT_SPEC, BALANCE_SHEET_SPEC)

