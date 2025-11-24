"""Adapter around the excel_extractor package for Django services."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from excel_extractor import IntelligentStatementExtractor

logger = logging.getLogger(__name__)


class IntelligentDataExtractor:
    """Django-friendly wrapper that logs every JSON payload."""

    def __init__(self) -> None:
        self.extractor = IntelligentStatementExtractor()

    def extract_financial_data(
        self,
        file_path: str,
        file_type: str = "auto",
        corporate=None,
        user=None,
        upload_record=None,
    ) -> Dict[str, Any]:
        result = self.extractor.extract(file_path)

        if result.get("success"):
            for name, payload in result.get("statements", {}).items():
                logger.info("Final %s JSON:\n%s", name, json.dumps(payload, indent=2))

        return result


