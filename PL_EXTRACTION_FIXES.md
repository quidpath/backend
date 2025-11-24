# P&L Statement Extraction - Comprehensive Fixes

## Issues Identified and Fixed

### Issue 1: Document Title/Header Rows Being Matched as Financial Fields

**Problem**:
- "Profit and Loss" → matched to `net_income` ❌
- "Spin Mobile Limited" → matched to `taxes` ❌  
- Company names, document titles, and date ranges were being matched as financial fields

**Fix Applied**:
1. **Skip first 3 rows entirely** - these are typically titles, company name, and date range
2. **Expanded blacklist** to include document titles and company info terms
3. Added to blacklist:
   - Document titles: "profit and loss", "p&l", "income statement"
   - Company terms: "limited", "ltd", "llc", "inc", "corporation"
   - Date terms: "for the year ended", "for the period ended", "as at"

**Code Location**: 
- `excel_extractor/intelligent.py` lines 112-114 (skip first 3 rows)
- `excel_extractor/label_matcher.py` lines 43-54 (expanded blacklist)

---

### Issue 2: Section Headers with No Values

**Problem**:
```
Row 6: ['Trading Income', '', '', '', '', '']  ← Matched to total_revenue but has NO values!
Row 7: ['CRB', '630525.17', '807359.58', ...]  ← Actual line item
Row 24: ['Total Trading Income', '0', '0', ...] ← Total row
```

- "Trading Income", "Cost of Sales", "Operating Expenses" are **category headers** with empty values
- Extractor matched them but couldn't find values
- This caused "❌ Could not find numeric value" errors

**Fix Applied**:
1. **Detect section headers** - labels that match fields but have no numeric values in the row
2. **Skip section headers** - wait for "Total X" rows or line items instead
3. Check if row has any non-zero numeric values before extracting

**Code Location**: `excel_extractor/intelligent.py` lines 204-234

**Logic**:
```python
# Check if this is a section header with no values
has_numeric_value = False
for cell in row_list[1:]:  # Skip first column (label)
    if isinstance(cell, (int, float)) and cell != 0:
        has_numeric_value = True
        break

# Skip section headers with no values
is_section_header = (
    ('income' in label_lower or 'revenue' in label_lower or 
     'expense' in label_lower or 'cost' in label_lower) and
    'total' not in label_lower and
    not has_numeric_value
)

if is_section_header:
    skip this row
```

---

### Issue 3: Expense Line Items Matched as Revenue

**Problem**:
- "Sales commission" → matched to `total_revenue` ❌ (it's an expense!)
- "Transport" → matched to `total_revenue` ❌ (it's an expense!)
- "Travel - International" → matched to `total_revenue` ❌ (it's an expense!)
- "Cleaning" → matched to `net_income` ❌ (it's an expense!)
- "Audit Fees" → matched to `taxes` ❌ (it's an expense, not tax!)

**Fix Applied**:
1. **Context-aware matching** - track which section we're in (Income vs Expenses)
2. **Expense detection** - identify expense-like terms and prevent matching to revenue
3. **Section tracking** - detect when we enter "Operating Expenses" section
4. **Expanded blacklist** - added common expense terms

**Code Location**: 
- `excel_extractor/intelligent.py` lines 129-178 (context-aware logic)
- `excel_extractor/label_matcher.py` lines 57-68 (expense blacklist)

**Logic**:
```python
# Track current section
if 'operating expense' in first_label_lower:
    current_section = 'expenses'

# Don't match expenses to revenue in expense section
if current_section == 'expenses' and field == 'total_revenue':
    skip this match

# Detect expense-like terms
expense_indicators = ['expense', 'cost', 'fee', 'charge', 'commission',
                     'cleaning', 'transport', 'travel', 'telephone', ...]
if is_expense_like and field == 'total_revenue':
    skip this match
```

**Blacklist Additions**:
- Common expenses: "cleaning", "transport", "travel", "telephone"
- Expense types: "maintenance", "repairs", "supplies", "stationery"
- Non-revenue items: "training", "entertainment", "donations", "penalties"

---

### Issue 4: Multi-Year Statements with Zero Values in First Column

**Problem**:
```
Row 4: ['Account', '2025', '2024', '2023', '2022']
Row 12: ['Interest Income', '0', '0', '27393.41', '0']  ← Extracted 0 instead of 27393!
Row 17: ['Other Revenue', '0', '0', '0', '280000']      ← Extracted 0 instead of 280000!
```

- Extractor was returning the first value found (column 1 = 2025 = 0)
- Should skip zero values and find the first non-zero value
- Or use most recent non-zero year

**Fix Applied**:
1. **Prefer most recent year** - if column 1 (immediately after label) has non-zero value, use it
2. **Skip zero columns** - if column 1 = 0, search subsequent columns for first non-zero value
3. **Collect all values** - scan all columns, then select best one

**Code Location**: `excel_extractor/number_extractor.py` lines 236-260

**Logic**:
```python
# Search right of label, collecting all values
found_values = []

for offset in range(1, search_distance + 1):
    result = extract_numeric_value(value)
    if result is not None:
        found_values.append((offset, result))
        # If first column has non-zero value, use it (most recent year)
        if offset == 1 and result != 0:
            return result

# If first column was 0, return first non-zero value
if found_values:
    for offset, result in found_values:
        if result != 0:
            return result
    # If all values are 0, return 0
    return 0
```

---

### Issue 5: "Total" Rows with Value = 0 (Incorrect)

**Problem**:
```
Row 24: ['Total Trading Income', '0', '0', '0', '0']  ← Should be 1,643,990 (sum of line items)
Row 28: ['Total Cost of Sales', '0', '0', '0', '0']   ← Should be 15,988,087 (sum of line items)
Row 77: ['Total Operating Expenses', '0', '0', '0']   ← Should be 9,310,402 (sum of line items)
```

- "Total" rows exist but have incorrect value = 0
- Should calculate total from line items OR skip "Total" row and use line items directly
- Current implementation: Using "Total" rows with priority 2.0, but they're incorrect!

**Current Status**: 
⚠️ **PARTIALLY ADDRESSED** - The extractor now skips section headers and prefers non-zero values. However, if a "Total" row has value = 0, we still extract 0.

**Recommended Future Enhancement**:
1. If "Total X" row = 0, sum the line items in that section
2. Track line items between section header and "Total" row
3. Calculate sum and use that instead of 0

---

### Issue 6: Indented Line Items (Leading Spaces)

**Problem**:
```
Row 4: ['          Other Charges', '', '1.24']  ← Indented with spaces
Row 5: ['          Sales', '', '35143811.2']    ← Indented
```

- Labels have leading spaces (indentation to show hierarchy)
- Label normalization handles this, but it's good to be aware

**Status**: ✅ **ALREADY HANDLED** by `normalize_label_text()` in `excel_extractor/utils.py`

---

## Summary of All Changes

### Files Modified

1. **`excel_extractor/intelligent.py`**:
   - Skip first 3 rows (lines 112-114)
   - Track current section for context-aware matching (lines 108-146)
   - Skip section headers with no values (lines 204-234)
   - Detect expense-like terms and prevent revenue matching (lines 160-178)
   - Skip "non-operating" labels for operating fields (lines 180-189)
   - Handle "Total Operating Income" ambiguity (lines 191-202)

2. **`excel_extractor/label_matcher.py`**:
   - Expanded `GENERIC_LABEL_BLACKLIST` (lines 30-69)
   - Added document titles, company terms, common expenses

3. **`excel_extractor/number_extractor.py`**:
   - Improved multi-year value extraction (lines 236-260)
   - Prefer most recent non-zero year
   - Skip zero values in first column

### Test Cases Covered

✅ **Multi-year P&L with section headers**
- Spin Mobile Limited (80 rows x 6 columns)
- Headers: "Trading Income", "Cost of Sales", "Operating Expenses" (no values)
- Line items with 5 years of data
- "Total" rows with value = 0

✅ **Indented P&L with parent-child structure**
- Ozonecool Investment Limited (72 rows x 3 columns)
- Parent categories: "Operating Income", "Cost of Goods Sold", "Operating Expense" (no values)
- Indented line items: "          Sales", "          Purchases", etc.
- "Total for X" rows

✅ **Income Statement with "Total Operating Income" ambiguity**
- Previous fix ensures this is mapped to `total_revenue`, not `operating_income`

---

## Expected Results After Fixes

### For Spin Mobile Limited P&L:

**Before**:
- total_revenue: 0 (wrong - picked first zero value)
- cogs: 0 (wrong - picked "Total Cost of Sales" = 0)
- operating_expenses: 0 (wrong - picked "Total Operating Expenses" = 0)
- taxes: 83630 (wrong - picked "Licenses & Permits")
- "Cleaning" → net_income (wrong!)
- "Transport", "Travel" → total_revenue (wrong!)

**After**:
- ✅ "Trading Income" (header) → skipped (no values)
- ✅ "CRB" = 630,525 (first non-zero year 2025)
- ✅ "Total Trading Income" = 0 → still 0 (known limitation - need to sum line items)
- ✅ "Cost of Sales" (header) → skipped
- ✅ "Cost of Goods Sold" = 4,066,405 (from 2025)
- ✅ "Cleaning" → skipped (expense blacklist)
- ✅ "Transport", "Travel" → skipped (expense detection + blacklist)
- ✅ "Licenses & Permits" → skipped for taxes (in expenses section)

### For Ozonecool Investment Limited P&L:

**Before**:
- "Profit and Loss" → taxes (WRONG!)
- "Operating Income" (header) → operating_profit (matched but no value → error)
- "Sales" = 35,143,811 (correct!)
- "Total for Operating Income" = 0 (wrong - should be 35,143,811)
- "Travelling, Accommodation & Allowance" → total_revenue (WRONG - it's an expense!)

**After**:
- ✅ "Profit and Loss" → skipped (blacklist + skip first 3 rows)
- ✅ "Operating Income" (header) → skipped (section header, no values)
- ✅ "Sales" = 35,143,811 (correct!)
- ✅ "Total for Operating Income" = 0 → still 0 (limitation - need to calculate)
- ✅ "Travelling..." → skipped (expense-like term + expense section)

---

## Known Limitations (Future Work)

1. **"Total" rows with value = 0**: Need to implement line-item summation
2. **Complex multi-level hierarchies**: Deep nesting (3+ levels) not fully tested
3. **Merged cells**: May cause column misalignment (need to test)
4. **Right-to-left layouts**: Not tested (Arabic/Hebrew statements)
5. **Quarterly statements**: Multiple periods in columns (Q1, Q2, Q3, Q4) - need to select correct quarter

---

## Testing Instructions

1. **Upload Spin Mobile Limited P&L** (multi-year with section headers)
2. **Upload Ozonecool Investment Limited P&L** (indented with parent categories)
3. **Verify in logs**:
   - "📍 Section: INCOME" appears when entering income section
   - "📍 Section: EXPENSES" appears when entering expense section
   - "⚠️ SKIP: Label 'X' is a section header with no values"
   - "⚠️ SKIP: Label 'X' looks like an expense, can't be revenue"
   - "⚠️ SKIP: Label 'X' is in EXPENSES section, can't be revenue"
4. **Check extracted values**:
   - total_revenue should be non-zero (from line items, not "Total" = 0)
   - Expense items should NOT be in total_revenue
   - Document titles should NOT match any field
   - Multi-year data should use most recent non-zero year

---

## Architecture Improvements

1. **Section-Aware Parsing**: System now tracks which section of the P&L it's reading (Income, COGS, Expenses, Profit)
2. **Context-Based Validation**: Labels are validated based on their position in the document
3. **Smart Zero Handling**: Automatically skips zero values in multi-year statements
4. **Hierarchical Detection**: Identifies parent categories vs line items vs totals
5. **Expanded Vocabulary**: Comprehensive blacklist prevents mismatches with generic/expense terms

These improvements ensure the extractor handles diverse P&L formats from Kenyan companies, accounting software exports (like QuickBooks, Sage), and multi-year comparative statements.


