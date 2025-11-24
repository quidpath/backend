"""High-reliability Excel to JSON financial extractor."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Union

from .exceptions import (
    ExtractorError,
    LabelNotFoundError,
    MissingFieldError,
    ValidationError,
    ValueNormalizationError,
)
from .intelligent import StatementParser
from .specs import INCOME_STATEMENT_SPEC, StatementSpec
from .validators import validate_financials
from .workbook_loader import load_tables

REQUIRED_FIELDS = INCOME_STATEMENT_SPEC.required_fields
DEFAULT_LABELS = INCOME_STATEMENT_SPEC.label_mapping


class FinancialExtractor:
    """Excel → JSON financial extractor.

    Example:
        extractor = FinancialExtractor()
        payload = extractor.extract(\"/tmp/statement.xlsx\")
    """

    def __init__(
        self,
        label_mapping: Dict[str, Iterable[str]] | None = None,
        label_threshold: float = 0.8,
    ) -> None:
        if label_mapping is not None:
            spec = StatementSpec(
                name="income_statement",
                required_fields=INCOME_STATEMENT_SPEC.required_fields,
                optional_fields=INCOME_STATEMENT_SPEC.optional_fields,
                label_mapping=label_mapping,
                validators=INCOME_STATEMENT_SPEC.validators,
            )
            self.parser = StatementParser(spec, label_threshold=label_threshold)
        else:
            self.parser = StatementParser(INCOME_STATEMENT_SPEC, label_threshold=label_threshold)

    def extract(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Extract financials and return the response payload."""
        try:
            data = self._extract_financials(file_path)
            data["status"] = "success"
            return data
        except ExtractorError as exc:
            return {"status": "error", "message": str(exc)}

    def _extract_financials(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise ExtractorError(f"File does not exist: {path}")

        tables = load_tables(path)
        data = self.parser.parse(tables)
        if not data:
            raise LabelNotFoundError("Missing required financial fields.")

        consolidated = {field: int(data[field]) for field in REQUIRED_FIELDS}
        validate_financials(consolidated)
        consolidated["risk_level"] = data.get("risk_level")
        return consolidated


