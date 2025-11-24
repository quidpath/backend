"""
Unit tests for universal number extraction.
"""

import unittest
from excel_extractor.number_extractor import (
    extract_numeric_value,
    find_value_in_row,
    _extract_numbers_from_text,
    _parse_number_string,
    _is_tax_label
)


class TestNumberExtractor(unittest.TestCase):
    """Test cases for number extraction."""
    
    def test_comma_formatted_numbers(self):
        """Test numbers with commas."""
        self.assertEqual(extract_numeric_value("65,000,000"), 65000000.0)
        self.assertEqual(extract_numeric_value("1,234,567.89"), 1234567.89)
        self.assertEqual(extract_numeric_value(["Revenue", "65,000,000"]), 65000000.0)
    
    def test_space_formatted_numbers(self):
        """Test numbers with spaces."""
        self.assertEqual(extract_numeric_value("65 000 000"), 65000000.0)
        self.assertEqual(extract_numeric_value("1 234 567.89"), 1234567.89)
        self.assertEqual(extract_numeric_value("65 000 000.50"), 65000000.5)
    
    def test_unicode_spaced_numbers(self):
        """Test numbers with Unicode spaces (U+202F, U+00A0)."""
        # Narrow no-break space (U+202F)
        self.assertEqual(extract_numeric_value("65\u202F000\u202F000"), 65000000.0)
        # Non-breaking space (U+00A0)
        self.assertEqual(extract_numeric_value("65\u00A0000\u00A0000"), 65000000.0)
        # Mixed unicode spaces
        self.assertEqual(extract_numeric_value("65\u202F000\u00A0000"), 65000000.0)
    
    def test_currency_prefixes(self):
        """Test numbers with currency prefixes."""
        self.assertEqual(extract_numeric_value("Ksh 65,000,000"), 65000000.0)
        self.assertEqual(extract_numeric_value("KES 65,000,000"), 65000000.0)
        self.assertEqual(extract_numeric_value("KSH 65,000,000"), 65000000.0)
        self.assertEqual(extract_numeric_value("$1,234,567"), 1234567.0)
        self.assertEqual(extract_numeric_value("€1,234,567"), 1234567.0)
        self.assertEqual(extract_numeric_value("£1,234,567"), 1234567.0)
    
    def test_currency_suffixes(self):
        """Test numbers with currency suffixes."""
        self.assertEqual(extract_numeric_value("65,000,000 Ksh"), 65000000.0)
        self.assertEqual(extract_numeric_value("65,000,000 KES"), 65000000.0)
        self.assertEqual(extract_numeric_value("1,234,567 USD"), 1234567.0)
    
    def test_accounting_negatives(self):
        """Test accounting format negatives: (65,000,000)."""
        self.assertEqual(extract_numeric_value("(65,000,000)"), -65000000.0)
        self.assertEqual(extract_numeric_value("(1,234,567.89)"), -1234567.89)
        self.assertEqual(extract_numeric_value("(10000)"), -10000.0)
    
    def test_decimal_numbers(self):
        """Test decimal numbers."""
        self.assertEqual(extract_numeric_value("65,000,000.50"), 65000000.5)
        self.assertEqual(extract_numeric_value("1234.56"), 1234.56)
        self.assertEqual(extract_numeric_value("0.50"), 0.5)
    
    def test_text_with_numbers(self):
        """Test numbers embedded in text."""
        self.assertEqual(extract_numeric_value("Revenue for the period: 65,000,000"), 65000000.0)
        self.assertEqual(extract_numeric_value("Total: 1,234,567.89 KES"), 1234567.89)
        self.assertEqual(extract_numeric_value("Amount: (50,000)"), -50000.0)
    
    def test_ocr_noisy_text(self):
        """Test OCR noise mixed in text."""
        # Common OCR errors
        self.assertEqual(extract_numeric_value("65,O00,000"), 65000000.0)  # O instead of 0
        self.assertEqual(extract_numeric_value("65,000,0O0"), 65000000.0)  # O instead of 0
        self.assertEqual(extract_numeric_value("65,000,000 abc"), 65000000.0)  # Extra text
        self.assertEqual(extract_numeric_value("abc 65,000,000 xyz"), 65000000.0)  # Text around
    
    def test_excel_text_numbers(self):
        """Test numbers stored as Excel text."""
        self.assertEqual(extract_numeric_value("'65,000,000"), 65000000.0)  # Excel text prefix
        self.assertEqual(extract_numeric_value("'1,234,567.89"), 1234567.89)
    
    def test_multiple_numbers(self):
        """Test rows with multiple numbers (should return largest)."""
        self.assertEqual(extract_numeric_value(["Revenue", "50,000", "65,000,000", "10,000"]), 65000000.0)
        self.assertEqual(extract_numeric_value("Revenue: 50,000 and Total: 65,000,000"), 65000000.0)
    
    def test_tax_fields(self):
        """Test tax fields (should return smallest number for rates)."""
        # Tax rate should return smaller number
        self.assertEqual(extract_numeric_value("Tax Rate: 30% or 0.30", label="Tax Expense"), 0.30)
        self.assertEqual(extract_numeric_value("Tax: 30% (0.30)", label="Tax Rate"), 0.30)
        # But if only one number, return it
        self.assertEqual(extract_numeric_value("Tax: 30", label="Tax"), 30.0)
    
    def test_negative_numbers(self):
        """Test regular negative numbers."""
        self.assertEqual(extract_numeric_value("-65,000,000"), -65000000.0)
        self.assertEqual(extract_numeric_value("-1,234,567.89"), -1234567.89)
    
    def test_mixed_formats(self):
        """Test mixed formatting."""
        self.assertEqual(extract_numeric_value("Ksh 65,000,000.50"), 65000000.5)
        self.assertEqual(extract_numeric_value("(KES 1,234,567.89)"), -1234567.89)
        self.assertEqual(extract_numeric_value("65 000 000.50 KES"), 65000000.5)
    
    def test_empty_invalid_input(self):
        """Test empty or invalid input."""
        self.assertIsNone(extract_numeric_value(""))
        self.assertIsNone(extract_numeric_value("abc"))
        self.assertIsNone(extract_numeric_value(None))
        self.assertIsNone(extract_numeric_value([]))
    
    def test_find_value_in_row(self):
        """Test find_value_in_row function."""
        row = ["Sales Revenue", "65,000,000", "KES", "2024"]
        self.assertEqual(find_value_in_row(row, 0, is_numeric=True), 65000000.0)
        
        row = ["Revenue", "", "65,000,000", ""]
        self.assertEqual(find_value_in_row(row, 0, is_numeric=True), 65000000.0)
        
        row = ["", "65,000,000", "Revenue"]
        self.assertEqual(find_value_in_row(row, 2, is_numeric=True), 65000000.0)
    
    def test_entire_row_search(self):
        """Test searching entire row for merged cells."""
        row = ["Total Revenue", "", "", "65,000,000", "", ""]
        # Should find number even if not adjacent
        result = find_value_in_row(row, 0, is_numeric=True, search_distance=0)
        self.assertEqual(result, 65000000.0)
    
    def test_extract_numbers_from_text_edge_cases(self):
        """Test edge cases in number extraction."""
        # Very large numbers
        self.assertEqual(_extract_numbers_from_text("1,000,000,000,000"), [1000000000000.0])
        
        # Very small numbers
        self.assertEqual(_extract_numbers_from_text("0.01"), [0.01])
        
        # Multiple numbers
        numbers = _extract_numbers_from_text("Revenue: 50,000 and Cost: 30,000")
        self.assertIn(50000.0, numbers)
        self.assertIn(30000.0, numbers)
    
    def test_parse_number_string(self):
        """Test number string parsing."""
        self.assertEqual(_parse_number_string("65,000,000"), 65000000.0)
        self.assertEqual(_parse_number_string("65 000 000"), 65000000.0)
        self.assertEqual(_parse_number_string("65,000,000.50"), 65000000.5)
        self.assertEqual(_parse_number_string("KES 65,000,000"), 65000000.0)
        self.assertIsNone(_parse_number_string(""))
        self.assertIsNone(_parse_number_string("abc"))
    
    def test_is_tax_label(self):
        """Test tax label detection."""
        self.assertTrue(_is_tax_label("Tax Expense"))
        self.assertTrue(_is_tax_label("Tax Rate"))
        self.assertTrue(_is_tax_label("Tax Percentage"))
        self.assertTrue(_is_tax_label("Tax (30%)"))
        self.assertFalse(_is_tax_label("Revenue"))
        self.assertFalse(_is_tax_label("Operating Expenses"))


if __name__ == '__main__':
    unittest.main()


