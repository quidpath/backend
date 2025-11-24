"""
Test negative value extraction.
"""

import pytest
from excel_extractor.number_extractor import extract_numeric_value


def test_negative_string():
    """Test extraction of negative values as strings."""
    result = extract_numeric_value('-1500000')
    assert result == -1500000.0, f"Expected -1500000, got {result}"


def test_negative_integer():
    """Test extraction of negative values as integers."""
    result = extract_numeric_value(-1500000)
    assert result == -1500000.0, f"Expected -1500000, got {result}"


def test_negative_float():
    """Test extraction of negative values as floats."""
    result = extract_numeric_value(-1500000.50)
    assert result == -1500000.50, f"Expected -1500000.50, got {result}"


def test_negative_with_commas():
    """Test extraction of negative values with commas."""
    result = extract_numeric_value('-1,500,000')
    assert result == -1500000.0, f"Expected -1500000, got {result}"


def test_negative_accounting_format():
    """Test extraction of negative values in accounting format."""
    result = extract_numeric_value('(1500000)')
    assert result == -1500000.0, f"Expected -1500000, got {result}"


def test_negative_in_row():
    """Test extraction of negative values from a row."""
    row = ['Operating Income', '-1500000']
    result = extract_numeric_value(row)
    assert result == -1500000.0, f"Expected -1500000, got {result}"


def test_negative_integer_in_row():
    """Test extraction of negative integer values from a row."""
    row = ['Operating Income', -1500000]
    result = extract_numeric_value(row)
    assert result == -1500000.0, f"Expected -1500000, got {result}"


def test_mixed_positive_negative():
    """Test that negative values are preserved when mixed with positive."""
    # Should NOT extract both positive and negative
    result = extract_numeric_value('-1500000')
    assert result == -1500000.0, f"Expected -1500000, got {result}"
    
    # Verify it doesn't return the positive version
    assert result < 0, f"Expected negative value, got {result}"


def test_loss_scenario():
    """Test realistic loss scenario from P&L."""
    rows = [
        ['Operating Income', '-1500000'],
        ['Interest Expense', '950000'],
        ['Taxes', '120000'],
        ['Net Income', '-2570000']
    ]
    
    for row in rows:
        result = extract_numeric_value(row)
        # Parse expected value from row
        expected_str = str(row[1]).replace(',', '')
        expected = float(expected_str)
        assert result == expected, f"For {row[0]}: Expected {expected}, got {result}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


