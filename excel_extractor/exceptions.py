"""Custom exceptions for the Excel financial extractor."""

from __future__ import annotations


class ExtractorError(Exception):
    """Base class for extractor errors."""


class ValueNormalizationError(ExtractorError):
    """Raised when a numeric cell cannot be normalized."""


class LabelNotFoundError(ExtractorError):
    """Raised when a required financial label is missing."""


class MissingFieldError(ExtractorError):
    """Raised when a financial field cannot be extracted."""


class ValidationError(ExtractorError):
    """Raised when internal validation rules fail."""
