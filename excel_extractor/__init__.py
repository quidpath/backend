"""
Excel financial extractor package for QuidPath ERP.

This module exposes the high-level `FinancialExtractor` class that can be
used to extract and process financial data from Excel files.
"""

from .extractor import FinancialExtractor
from .intelligent import IntelligentStatementExtractor
from .label_matcher import AdvancedLabelMatcher, match_label_to_field
from .accounting_aliases import ACCOUNTING_ALIASES
from .exceptions import (
    ExtractorError,
    LabelNotFoundError,
    MissingFieldError,
    ValidationError,
    ValueNormalizationError,
)

__all__ = [
    "FinancialExtractor",
    "IntelligentStatementExtractor",
    "AdvancedLabelMatcher",
    "match_label_to_field",
    "ACCOUNTING_ALIASES",
    "ExtractorError",
    "LabelNotFoundError",
    "MissingFieldError",
    "ValidationError",
    "ValueNormalizationError",
]

