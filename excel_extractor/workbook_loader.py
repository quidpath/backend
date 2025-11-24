"""Table loading utilities using pandas."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from .exceptions import ExtractorError

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"}
CSV_SUFFIXES = {".csv", ".tsv"}


def load_tables(path: Path) -> Dict[str, pd.DataFrame]:
    """Load Excel/CSV content into pandas DataFrames with raw values."""
    suffix = path.suffix.lower()

    if suffix in EXCEL_SUFFIXES:
        try:
            # ✅ FIX: Try to detect header row first, but fall back to header=None if detection fails
            # Read with header=None to get all raw data
            frames = pd.read_excel(
                path,
                sheet_name=None,
                dtype=str,
                header=None,  # Keep header=None to get all rows
                engine="openpyxl",
            )
        except Exception as exc:  # pragma: no cover - pandas/openpyxl internals
            raise ExtractorError(f"Unable to open workbook: {path}") from exc
    elif suffix in CSV_SUFFIXES:
        try:
            df = pd.read_csv(path, dtype=str, header=None)
        except Exception as exc:  # pragma: no cover - pandas internals
            raise ExtractorError(f"Unable to read CSV file {path}: {exc}") from exc
        frames = {path.stem or "Sheet1": df}
    else:
        raise ExtractorError(f"Unsupported file format '{suffix or 'unknown'}'.")

    prepared = {}
    for name, frame in frames.items():
        # Fill NaN with empty strings, then convert to string
        # This ensures we can properly check for empty cells
        normalized = frame.fillna("").astype(str)
        # Replace "nan" strings (from pandas) with empty strings
        normalized = normalized.replace("nan", "")
        
        # ✅ FIX: Remove completely empty rows at the start
        # Find first non-empty row
        first_data_row = 0
        for idx in range(len(normalized)):
            row = normalized.iloc[idx]
            # Check if row has any non-empty cells
            if any(str(cell).strip() and str(cell).strip().lower() != 'nan' for cell in row):
                first_data_row = idx
                break
        
        # Skip empty rows at the start
        if first_data_row > 0:
            normalized = normalized.iloc[first_data_row:].reset_index(drop=True)
        
        prepared[str(name) or "Sheet1"] = normalized
    return prepared

