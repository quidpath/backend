"""
Comprehensive tests for the advanced label matcher.

Tests cover:
- Exact matching
- Alias matching
- Fuzzy matching
- OCR errors
- Misspellings
- Different accounting formats
- Noisy labels
"""

import unittest
from excel_extractor.label_matcher import AdvancedLabelMatcher, match_label_to_field
from excel_extractor.accounting_aliases import ACCOUNTING_ALIASES


class TestAdvancedLabelMatcher(unittest.TestCase):
    """Test suite for AdvancedLabelMatcher."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.matcher = AdvancedLabelMatcher()
    
    def test_exact_match(self):
        """Test exact matching (case-insensitive, normalized)."""
        # Standard exact matches
        self.assertEqual(self.matcher.match("Total Revenue"), "total_revenue")
        self.assertEqual(self.matcher.match("total revenue"), "total_revenue")
        self.assertEqual(self.matcher.match("TOTAL REVENUE"), "total_revenue")
        self.assertEqual(self.matcher.match("Revenue"), "total_revenue")
        self.assertEqual(self.matcher.match("Sales"), "total_revenue")
        
        # With punctuation
        self.assertEqual(self.matcher.match("Revenue:"), "total_revenue")
        self.assertEqual(self.matcher.match("Total Revenue:"), "total_revenue")
        self.assertEqual(self.matcher.match("Revenue (Net)"), "total_revenue")
    
    def test_alias_match(self):
        """Test alias matching."""
        # Abbreviations
        self.assertEqual(self.matcher.match("COGS"), "cogs")
        self.assertEqual(self.matcher.match("OPEX"), "operating_expenses")
        self.assertEqual(self.matcher.match("EBIT"), "ebit")
        self.assertEqual(self.matcher.match("EBITDA"), "ebitda")
        
        # Long forms
        self.assertEqual(self.matcher.match("Cost of Goods Sold"), "cogs")
        self.assertEqual(self.matcher.match("Earnings Before Interest and Tax"), "ebit")
        
        # Regional variations
        self.assertEqual(self.matcher.match("Turnover"), "total_revenue")
        self.assertEqual(self.matcher.match("Trading Income"), "total_revenue")
    
    def test_fuzzy_match_typos(self):
        """Test fuzzy matching with typos."""
        # Common typos
        self.assertEqual(self.matcher.match("Revenu"), "total_revenue")  # Missing 'e'
        self.assertEqual(self.matcher.match("Revanue"), "total_revenue")  # Swapped 'a' and 'e'
        self.assertEqual(self.matcher.match("Revenuc"), "total_revenue")  # Extra 'c'
        
        # COGS typos
        self.assertEqual(self.matcher.match("Cost of Go0ds Sold"), "cogs")  # OCR error
        self.assertEqual(self.matcher.match("C0GS"), "cogs")  # OCR error
    
    def test_fuzzy_match_ocr_errors(self):
        """Test fuzzy matching with OCR errors."""
        # OCR character confusion
        self.assertEqual(self.matcher.match("Totai Revenue"), "total_revenue")  # 'l' -> 'i'
        self.assertEqual(self.matcher.match("Tota1 Revenue"), "total_revenue")  # 'l' -> '1'
        self.assertEqual(self.matcher.match("Revenuc"), "total_revenue")  # 'e' -> 'c'
        self.assertEqual(self.matcher.match("Operatlng Expenses"), "operating_expenses")  # 'i' -> 'l'
    
    def test_fuzzy_match_spacing(self):
        """Test fuzzy matching with spacing variations."""
        # Extra spaces
        self.assertEqual(self.matcher.match("Total  Revenue"), "total_revenue")
        self.assertEqual(self.matcher.match("Cost  of  Goods  Sold"), "cogs")
        
        # Missing spaces
        self.assertEqual(self.matcher.match("TotalRevenue"), "total_revenue")
        self.assertEqual(self.matcher.match("OperatingExpenses"), "operating_expenses")
    
    def test_fuzzy_match_partial(self):
        """Test fuzzy matching with partial matches."""
        # Long sentences (should match key words)
        result = self.matcher.match("Total revenue generated during the period")
        self.assertEqual(result, "total_revenue")
        
        result = self.matcher.match("Income from primary business operations")
        self.assertEqual(result, "total_revenue")
        
        result = self.matcher.match("Cost of goods sold during the financial year")
        self.assertEqual(result, "cogs")
    
    def test_fuzzy_match_unicode(self):
        """Test fuzzy matching with unicode characters."""
        # Unicode hyphens
        self.assertEqual(self.matcher.match("Purchases – Parts & Materials"), "cogs")  # En-dash
        self.assertEqual(self.matcher.match("Purchases — Parts & Materials"), "cogs")  # Em-dash
        self.assertEqual(self.matcher.match("Purchases − Parts & Materials"), "cogs")  # Minus sign
        
        # Unicode in labels
        self.assertEqual(self.matcher.match("Revenuë"), "total_revenue")  # Should normalize
    
    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        self.assertEqual(self.matcher.match("REVENUE"), "total_revenue")
        self.assertEqual(self.matcher.match("Revenue"), "total_revenue")
        self.assertEqual(self.matcher.match("revenue"), "total_revenue")
        self.assertEqual(self.matcher.match("ReVeNuE"), "total_revenue")
    
    def test_punctuation_handling(self):
        """Test punctuation handling."""
        # Colons
        self.assertEqual(self.matcher.match("Revenue:"), "total_revenue")
        self.assertEqual(self.matcher.match("Total Revenue:"), "total_revenue")
        
        # Parentheses
        self.assertEqual(self.matcher.match("Revenue (Net)"), "total_revenue")
        self.assertEqual(self.matcher.match("Operating Expenses (Total)"), "operating_expenses")
        
        # Commas
        self.assertEqual(self.matcher.match("Revenue, Total"), "total_revenue")
    
    def test_abbreviations(self):
        """Test abbreviation matching."""
        self.assertEqual(self.matcher.match("COGS"), "cogs")
        self.assertEqual(self.matcher.match("C.O.G.S."), "cogs")
        self.assertEqual(self.matcher.match("OPEX"), "operating_expenses")
        self.assertEqual(self.matcher.match("EBIT"), "ebit")
        self.assertEqual(self.matcher.match("EBITDA"), "ebitda")
        self.assertEqual(self.matcher.match("GP"), "gross_profit")
        self.assertEqual(self.matcher.match("NI"), "net_income")
    
    def test_regional_variations(self):
        """Test regional/format variations."""
        # UK spelling
        self.assertEqual(self.matcher.match("Turnover"), "total_revenue")
        self.assertEqual(self.matcher.match("Amortisation"), "amortization")
        
        # IFRS/GAAP variations
        self.assertEqual(self.matcher.match("Revenue from Contracts with Customers"), "total_revenue")
        self.assertEqual(self.matcher.match("Revenue from Ordinary Activities"), "total_revenue")
    
    def test_no_match(self):
        """Test that non-matching labels return None."""
        self.assertIsNone(self.matcher.match("Random Text"))
        self.assertIsNone(self.matcher.match("Account Number"))
        self.assertIsNone(self.matcher.match(""))
        self.assertIsNone(self.matcher.match("   "))
        self.assertIsNone(self.matcher.match("12345"))
    
    def test_confidence_scores(self):
        """Test confidence score matching."""
        # Exact match = 100%
        field, confidence = self.matcher.match_with_confidence("Total Revenue")
        self.assertEqual(field, "total_revenue")
        self.assertEqual(confidence, 100.0)
        
        # Alias match = 95%
        field, confidence = self.matcher.match_with_confidence("COGS")
        self.assertEqual(field, "cogs")
        self.assertEqual(confidence, 95.0)
        
        # Fuzzy match = score
        result = self.matcher.match_with_confidence("Revenu")  # Typo
        self.assertIsNotNone(result)
        if result:
            field, confidence = result
            self.assertEqual(field, "total_revenue")
            self.assertGreaterEqual(confidence, 85.0)  # Should meet threshold
    
    def test_all_canonical_fields(self):
        """Test that all canonical fields can be matched."""
        test_cases = {
            "total_revenue": ["Total Revenue", "Sales", "Turnover", "Revenue"],
            "cogs": ["COGS", "Cost of Goods Sold", "Cost of Sales"],
            "gross_profit": ["Gross Profit", "Gross Income", "GP"],
            "operating_expenses": ["Operating Expenses", "OPEX", "Operating Costs"],
            "operating_income": ["Operating Income", "Operating Profit", "EBIT"],
            "interest_expense": ["Interest Expense", "Interest Paid", "Finance Costs"],
            "taxes": ["Taxes", "Income Tax", "Tax Expense"],
            "net_income": ["Net Income", "Net Profit", "Profit After Tax"],
            "depreciation": ["Depreciation", "Depreciation Expense"],
            "amortization": ["Amortization", "Amortisation"],
            "ebit": ["EBIT", "Earnings Before Interest and Tax"],
            "ebitda": ["EBITDA", "Earnings Before Interest, Tax, Depreciation and Amortization"],
        }
        
        for field, labels in test_cases.items():
            for label in labels:
                result = self.matcher.match(label)
                self.assertEqual(result, field, 
                               f"Label '{label}' should match field '{field}' but got '{result}'")
    
    def test_convenience_function(self):
        """Test the convenience function match_label_to_field."""
        self.assertEqual(match_label_to_field("Total Revenue"), "total_revenue")
        self.assertEqual(match_label_to_field("COGS"), "cogs")
        self.assertEqual(match_label_to_field("Revenu"), "total_revenue")  # Typo
        self.assertIsNone(match_label_to_field("Random Text"))


class TestLabelMatcherEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.matcher = AdvancedLabelMatcher()
    
    def test_empty_string(self):
        """Test empty string handling."""
        self.assertIsNone(self.matcher.match(""))
        self.assertIsNone(self.matcher.match("   "))
        self.assertIsNone(self.matcher.match("\t\n"))
    
    def test_none_input(self):
        """Test None input handling."""
        self.assertIsNone(self.matcher.match(None))
    
    def test_numeric_strings(self):
        """Test that numeric strings don't match."""
        self.assertIsNone(self.matcher.match("12345"))
        self.assertIsNone(self.matcher.match("1,234,567"))
        self.assertIsNone(self.matcher.match("$1,000"))
    
    def test_very_long_strings(self):
        """Test very long label strings."""
        long_label = "Total revenue generated during the financial period ending December 31, 2023"
        result = self.matcher.match(long_label)
        self.assertEqual(result, "total_revenue")
    
    def test_special_characters(self):
        """Test labels with special characters."""
        # Currency symbols
        self.assertEqual(self.matcher.match("Revenue (KES)"), "total_revenue")
        self.assertEqual(self.matcher.match("Revenue ($)"), "total_revenue")
        
        # Percentages
        self.assertEqual(self.matcher.match("Revenue %"), "total_revenue")
    
    def test_multiple_matches(self):
        """Test that priority is used when multiple fields match."""
        # "Operating Income" could match both operating_income and operating_profit
        # Should prefer the one with higher priority
        result = self.matcher.match("Operating Income")
        self.assertIn(result, ["operating_income", "operating_profit"])


if __name__ == "__main__":
    unittest.main()


