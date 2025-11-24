"""
Universal number extraction for financial statements.
Handles various formats including OCR noise, unicode, currency symbols, etc.
"""

import re
import unicodedata
from typing import Any, List, Optional, Union


def extract_numeric_value(
    row: Union[List[Any], dict, str],
    label: Optional[str] = None,
    search_entire_row: bool = True
) -> Optional[float]:
    """
    Extract numeric value from a row, cell, or string.
    
    Supports:
    1. Numbers with commas: 65,000,000
    2. Numbers with spaces: 65 000 000
    3. Numbers with Unicode spaces (U+202F, U+00A0): 65 000 000
    4. Currency prefixes: Ksh 65,000,000 or KES 65,000,000
    5. Currency suffixes: 65,000,000 Ksh
    6. Negative accounting format: (65,000,000)
    7. Decimal numbers: 65,000,000.50
    8. Whole text strings: "Revenue for the period: 65,000,000"
    9. Numbers inside merged cells (searches entire row)
    10. OCR noise characters mixed in text
    11. Direct int/float values from Excel: -1500000
    
    Args:
        row: Can be a list of cells, dict, or string
        label: Optional label text (used to determine if tax field)
        search_entire_row: If True, search all cells in row; if False, only first cell
    
    Returns:
        Extracted numeric value as float, or None if no valid number found
    """
    # ✅ FIX: Handle direct numeric types (int, float) from Excel/pandas
    if isinstance(row, (int, float)):
        return float(row)
    
    # Convert input to list of strings
    cells = _normalize_input(row)
    
    if not cells:
        return None
    
    # Extract all numbers from all cells
    all_numbers = []
    for cell in cells:
        # ✅ FIX: Handle direct numeric values from Excel
        if isinstance(cell, (int, float)):
            all_numbers.append(float(cell))
        else:
            numbers = _extract_numbers_from_text(str(cell))
            all_numbers.extend(numbers)
    
    if not all_numbers:
        return None
    
    # Determine which number to return
    # For tax fields, return smallest (often the rate)
    # For other fields, return largest (usually the main amount)
    is_tax_field = label and _is_tax_label(label)
    
    if is_tax_field and len(all_numbers) > 1:
        # For tax, prefer smaller numbers (rates like 30, 0.3, etc.)
        return min(all_numbers)
    else:
        # For other fields, return largest number
        return max(all_numbers)


def _normalize_input(row: Union[List[Any], dict, str]) -> List[Any]:
    """Convert various input types to a list of values (preserving numeric types)."""
    if isinstance(row, str):
        return [row]
    
    if isinstance(row, (int, float)):
        return [row]
    
    if isinstance(row, dict):
        return [v for v in row.values() if v is not None]
    
    if isinstance(row, list):
        return [cell for cell in row if cell is not None]
    
    return []


def _extract_numbers_from_text(text: str) -> List[float]:
    """
    Extract all valid numbers from a text string.
    
    Handles:
    - Unicode spaces and separators
    - Currency symbols (prefix and suffix)
    - Accounting negatives: (10000)
    - Regular negatives: -10000
    - Commas, spaces, dots
    - OCR noise
    """
    if not text or not isinstance(text, str):
        return []
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    
    # Replace unicode spaces with regular spaces
    # U+202F (narrow no-break space), U+00A0 (non-breaking space), etc.
    text = text.replace('\u202F', ' ').replace('\u00A0', ' ')
    text = text.replace('\u2009', ' ').replace('\u2008', ' ')
    
    # Remove common OCR noise characters (keep digits, dots, commas, minus, parentheses)
    # Remove letters except for currency codes
    text = re.sub(r'[^\d\.,\-\s\(\)KkSsHhEeRr$€£¥₹%]', ' ', text)
    
    # Extract all potential number patterns
    # Pattern 1: Accounting format: (123,456.78) or (123456.78)
    accounting_pattern = r'\(([\d\s,]+\.?\d*)\)'
    accounting_matches = re.finditer(accounting_pattern, text)
    numbers = []
    
    for match in accounting_matches:
        num_str = match.group(1)
        value = _parse_number_string(num_str)
        if value is not None:
            numbers.append(-abs(value))  # Accounting format is always negative
    
    # Remove accounting format numbers from text to avoid double extraction
    text = re.sub(accounting_pattern, ' ', text)
    
    # ✅ FIX: Extract negative numbers FIRST to avoid double extraction
    # Pattern 2A: Negative numbers with minus sign
    negative_pattern = r'-[\d\s,]+\.?\d*'
    negative_matches = re.finditer(negative_pattern, text)
    
    for match in negative_matches:
        num_str = match.group(0)
        value = _parse_number_string(num_str)
        if value is not None:
            numbers.append(-abs(value))
    
    # Remove negative numbers from text to avoid double extraction
    text = re.sub(negative_pattern, ' ', text)
    
    # Pattern 2B: Regular numbers with various separators
    # Match: digits with commas/spaces/dots, optional decimal part
    # Examples: 65,000,000.50, 65 000 000, 65000000.5
    number_pattern = r'[\d][\d\s,]*\.?\d*'
    number_matches = re.finditer(number_pattern, text)
    
    for match in number_matches:
        num_str = match.group(0)
        value = _parse_number_string(num_str)
        if value is not None:
            numbers.append(value)
    
    return numbers


def _parse_number_string(num_str: str) -> Optional[float]:
    """
    Parse a number string into a float.
    
    Handles:
    - Commas: 1,234,567
    - Spaces: 1 234 567
    - Dots as decimal: 1234.56
    - Multiple separators: 1,234 567.89
    """
    if not num_str:
        return None
    
    # Remove all spaces and commas
    cleaned = num_str.replace(' ', '').replace(',', '').strip()
    
    # Remove currency codes if present (KES, Ksh, etc.)
    cleaned = re.sub(r'(?i)(kes|ksh|kshs|ksh\.|usd|eur|gbp|jpy|inr)', '', cleaned)
    cleaned = cleaned.strip()
    
    # Remove currency symbols
    cleaned = cleaned.replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('₹', '')
    cleaned = cleaned.strip()
    
    # Check if it's a valid number
    if not cleaned or cleaned == '.' or cleaned == '-':
        return None
    
    # Handle decimal point
    if cleaned.count('.') > 1:
        # Multiple dots - likely OCR noise, take first valid number
        parts = cleaned.split('.')
        if parts[0]:
            cleaned = parts[0] + '.' + ''.join(parts[1:])
        else:
            return None
    
    try:
        value = float(cleaned)
        # Filter out obviously wrong numbers (too small or too large)
        if abs(value) > 1e15:  # Sanity check: numbers larger than 1 quadrillion
            return None
        return value
    except (ValueError, OverflowError):
        return None


def _is_tax_label(label: str) -> bool:
    """Check if label indicates a tax field (returns smallest number for tax rates)."""
    if not label:
        return False
    
    label_lower = label.lower()
    tax_keywords = ['tax', 'rate', 'percentage', '%', 'percent']
    
    return any(keyword in label_lower for keyword in tax_keywords)


def find_value_in_row(
    row_list: List[Any],
    label_col_idx: int,
    is_numeric: bool = True,
    search_distance: int = 10
) -> Optional[Any]:
    """
    Find a value in the same row as the label.
    
    Enhanced version that:
    - Searches entire row if needed
    - Uses robust number extraction
    - Handles merged cells and OCR noise
    
    Args:
        row_list: List of cell values in the row
        label_col_idx: Index of the label column
        is_numeric: Whether to extract numeric value
        search_distance: Maximum distance to search (0 = entire row)
    
    Returns:
        Extracted value or None
    """
    if not row_list or label_col_idx < 0 or label_col_idx >= len(row_list):
        return None
    
    # If search_distance is 0, search entire row
    if search_distance == 0:
        search_distance = len(row_list)
    
    # Search right of label first (most common)
    # For multi-year statements, prefer non-zero values
    found_values = []
    
    for offset in range(1, min(search_distance + 1, len(row_list) - label_col_idx)):
        target_idx = label_col_idx + offset
        if target_idx < len(row_list):
            value = row_list[target_idx]
            if is_numeric:
                result = extract_numeric_value(value, search_entire_row=False)
                if result is not None:
                    found_values.append((offset, result))
                    # If first column has non-zero value, use it (most recent year)
                    if offset == 1 and result != 0:
                        return result
            elif isinstance(value, str) and value.strip():
                return value.strip()
    
    # If first column was 0, return the first non-zero value found
    if found_values:
        for offset, result in found_values:
            if result != 0:
                return result
        # If all values are 0, return 0
        return 0
    
    # Search left of label
    for offset in range(1, min(search_distance + 1, label_col_idx + 1)):
        target_idx = label_col_idx - offset
        if target_idx >= 0:
            value = row_list[target_idx]
            if is_numeric:
                result = extract_numeric_value(value, search_entire_row=False)
                if result is not None:
                    return result
            elif isinstance(value, str) and value.strip():
                return value.strip()
    
    # If still not found and is_numeric, try searching entire row
    if is_numeric:
        result = extract_numeric_value(row_list, search_entire_row=True)
        if result is not None:
            return result
    
    return None

