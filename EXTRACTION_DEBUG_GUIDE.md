# Financial Statement Extraction - Debug Guide

## Overview
This guide explains how to debug financial statement extraction issues and understand the extraction pipeline.

## Extraction Pipeline

```
Excel/PDF File → Intelligent Extractor → JSON Data → Storage → Model Input
```

### 1. File Reading (`workbook_loader.py`)
- Reads Excel file with `header=None` to preserve all rows
- Skips completely empty rows at the start
- Converts to pandas DataFrame

### 2. Intelligent Extraction (`intelligent.py`)
- **Label Matching**: Uses fuzzy matching, exact matching, and keyword matching
- **Priority-based Extraction**: Summary rows > Line items
- **Number Extraction**: Uses universal number parser for various formats
- **Fallback Search**: Searches entire row if value not found adjacent to label

### 3. Number Extraction (`number_extractor.py`)
Handles:
- Comma-formatted: `65,000,000`
- Space-formatted: `65 000 000`
- Unicode spaces: `65 000 000` (U+202F, U+00A0)
- Currency prefixes/suffixes: `Ksh 65,000,000` or `65,000,000 KES`
- Accounting negatives: `(65,000,000)` → `-65000000`
- Decimal numbers: `65,000,000.50`
- Text with numbers: `"Revenue: 65,000,000"`
- OCR noise: Filters common OCR errors
- Merged cells: Searches entire row

### 4. Storage (`EnhancedFinancialDataService.py`)
- Converts snake_case fields to camelCase
- Stores in `ProcessedFinancialData` model
- Creates `TazamaAnalysisRequest` with `input_data`

### 5. Model Input (`TazamaService.py`)
- Validates `input_data` is not None/empty
- Passes to `EnhancedFinancialOptimizer.analyze_income_statement()`

## Debug Logs to Look For

### 1. Extraction Stage
```
🔍 DEBUG - Full row contents (row X):
  [0]: 'Sales Revenue' (type: str)
  [1]: None (type: NoneType)
  [2]: 65000000 (type: int)
  [3]: 'KES' (type: str)
```

**What to check:**
- Is the label in the correct column?
- Is the value in an adjacent column?
- Is the value in a different format (string, with currency symbols, etc.)?

### 2. Field Status
```
📊 DEBUG - Required fields status:
  total_revenue: ✅ FOUND (65000000)
  gross_profit: ✅ FOUND (24100000)
  operating_income: ❌ MISSING (None)
  net_income: ❌ MISSING (None)
```

**What to check:**
- Which fields are missing?
- Are the labels matching correctly?
- Are the values being extracted?

### 3. Raw JSON from Extractor
```
================================================================================
📥 RAW JSON DATA FROM EXTRACTOR:
================================================================================
{
  "total_revenue": 65000000,
  "cogs": 41000000,
  "gross_profit": 24000000,
  "operating_expenses": 11600000,
  "operating_income": 12400000,
  "net_income": 8680000,
  "taxes": 3720000
}
================================================================================
```

**What to check:**
- Are all expected fields present?
- Are the values reasonable?
- Are any values 0 or None when they shouldn't be?

### 4. JSON Data Fed to Model
```
================================================================================
📤 JSON DATA BEING FED TO MODEL (REQUEST 123):
================================================================================
{
  "totalRevenue": 65000000,
  "cogs": 41000000,
  "grossProfit": 24000000,
  "totalOperatingExpenses": 11600000,
  "operatingIncome": 12400000,
  "netIncome": 8680000,
  "taxes": 3720000
}
================================================================================
```

**What to check:**
- Has snake_case been converted to camelCase?
- Are all fields present and non-zero?
- Do the values match the extractor output?

## Common Issues and Solutions

### Issue 1: "❌ Could not find numeric value for label 'X' in row Y"

**Possible Causes:**
1. Value is in a non-adjacent column (merged cell)
2. Value has unexpected format (unicode spaces, OCR noise)
3. Value is stored as text instead of number
4. Label matches but value extraction logic fails

**Solution:**
- Check the "DEBUG - Full row contents" log
- Verify the value is in the row
- Check if fallback extraction succeeded: "✅ Found candidate from entire row search"

### Issue 2: "❌ No recognizable statements found"

**Possible Causes:**
1. Not enough required fields were extracted
2. Labels didn't match (fuzzy matching threshold too high)
3. Values weren't extracted even when labels matched

**Solution:**
- Check the "Required fields status" log
- Verify which fields are missing
- Lower fuzzy matching threshold if needed
- Add more label variations to `specs.py`

### Issue 3: Values are 0 or None in model input

**Possible Causes:**
1. Extraction failed silently
2. Values were lost during storage/conversion
3. Field name mapping issue (snake_case ↔ camelCase)

**Solution:**
- Compare "RAW JSON DATA FROM EXTRACTOR" with "JSON DATA BEING FED TO MODEL"
- Check if values are present in extractor output
- Verify field name mapping in `EnhancedFinancialDataService._store_intelligent_extraction()`

### Issue 4: Generic labels matching incorrectly

**Possible Causes:**
1. Label is too generic (e.g., "Account", "Total")
2. Label is matching multiple fields

**Solution:**
- Check if label is in `GENERIC_LABEL_BLACKLIST` in `label_matcher.py`
- Add problematic generic labels to blacklist
- Use keyword matching instead of exact matching

## Adding New Field Support

### 1. Add to `specs.py`
```python
StatementSpec(
    name='income_statement',
    required_fields=('total_revenue', 'cogs', 'gross_profit', 'operating_expenses', 
                    'operating_income', 'net_income', 'your_new_field'),
    label_mappings={
        'your_new_field': [
            'New Field Label',
            'Alternative Label',
            'Another Variation'
        ]
    }
)
```

### 2. Add to `accounting_aliases.py`
```python
ACCOUNTING_ALIASES = {
    'your_new_field': [
        'new field label',
        'alternative label',
        'yet another label'
    ]
}
```

### 3. Update Storage
Add to `EnhancedFinancialDataService._store_intelligent_extraction()`:
```python
record = {
    'your_new_field': safe_get('your_new_field', 0),
    # ... other fields
}
```

### 4. Update Model
Add field to `ProcessedFinancialData` model in `Tazama/models.py`:
```python
your_new_field = models.DecimalField(max_digits=15, decimal_places=2, default=0)
```

## Testing Changes

### 1. Test Number Extraction
```python
from excel_extractor.number_extractor import extract_numeric_value

# Test various formats
print(extract_numeric_value("65,000,000"))  # Should be 65000000.0
print(extract_numeric_value("(65,000,000)"))  # Should be -65000000.0
print(extract_numeric_value("Ksh 65,000,000"))  # Should be 65000000.0
```

### 2. Test Label Matching
```python
from excel_extractor.label_matcher import AdvancedLabelMatcher
from excel_extractor.accounting_aliases import ACCOUNTING_ALIASES

matcher = AdvancedLabelMatcher(aliases=ACCOUNTING_ALIASES)
print(matcher.match("Sales Revenue"))  # Should match 'total_revenue'
print(matcher.match("Cost of Goods Sold"))  # Should match 'cogs'
```

### 3. Test Full Extraction
Upload a test file and check the logs for:
- "📊 DEBUG - All extracted fields"
- "📥 RAW JSON DATA FROM EXTRACTOR"
- "📤 JSON DATA BEING FED TO MODEL"

## Key Files Reference

| File | Purpose |
|------|---------|
| `excel_extractor/intelligent.py` | Core extraction logic, label matching, priority-based extraction |
| `excel_extractor/number_extractor.py` | Universal number parser, handles all formats |
| `excel_extractor/label_matcher.py` | Fuzzy matching, keyword matching, blacklist |
| `excel_extractor/specs.py` | Statement definitions, required fields, label mappings |
| `excel_extractor/accounting_aliases.py` | Comprehensive list of label variations |
| `Tazama/Services/EnhancedFinancialDataService.py` | Storage, field mapping, data cleaning |
| `Tazama/Services/TazamaService.py` | Model input preparation, analysis execution |

## Contact & Support

If you encounter persistent extraction issues:
1. Check all debug logs in sequence
2. Verify the file format is supported
3. Ensure labels are reasonable matches for expected fields
4. Check that values are in a parseable format
5. Review field name mappings (snake_case ↔ camelCase)


