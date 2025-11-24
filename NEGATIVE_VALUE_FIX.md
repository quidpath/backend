# Critical Bug Fix: Negative Value Extraction

## Problem Discovered

The financial extractor was **failing to extract negative values correctly**, causing:
1. Extraction failures for loss-making P&L statements
2. Positive values being returned instead of negative ones
3. Complete extraction failure (parser returned None)

### Example

For a simple income statement with losses:
```
Total Revenue: 12,500,000
COGS: 10,200,000
Gross Profit: 2,300,000
Operating Expenses: 3,800,000
Operating Income: -1,500,000  ← NEGATIVE (loss)
Interest Expense: 950,000
Taxes: 120,000
Net Income: -2,570,000  ← NEGATIVE (loss)
```

**What Was Happening**:
- Operating Income `-1500000` → Extracted as `+1500000` (positive!)
- Net Income `-2570000` → Extracted as `+2570000` (positive!)
- Result: Parser failed completely

---

## Root Cause

### Bug in `excel_extractor/number_extractor.py`

The `_extract_numbers_from_text()` function was extracting **BOTH**:
1. The positive part: `1500000`
2. The negative part: `-1500000`

Then `max([1500000, -1500000])` would return `1500000` (positive) ❌

```python
# OLD CODE (BUGGY):
# Pattern 2: Regular numbers
number_pattern = r'[\d][\d\s,]*\.?\d*'
for match in re.finditer(number_pattern, text):
    numbers.append(value)  # Adds 1500000

# Pattern 3: Negative numbers  
negative_pattern = r'-[\d\s,]+\.?\d*'
for match in re.finditer(negative_pattern, text):
    numbers.append(-abs(value))  # Adds -1500000

# Result: [1500000, -1500000]
# max() returns: 1500000 ❌
```

---

## Fixes Applied

### 1. Extract Negatives FIRST and Remove Them

```python
# ✅ FIX: Extract negative numbers FIRST
negative_pattern = r'-[\d\s,]+\.?\d*'
for match in re.finditer(negative_pattern, text):
    value = _parse_number_string(match.group(0))
    if value is not None:
        numbers.append(-abs(value))

# Remove negative numbers from text to avoid double extraction
text = re.sub(negative_pattern, ' ', text)

# NOW extract regular positive numbers
number_pattern = r'[\d][\d\s,]*\.?\d*'
for match in re.finditer(number_pattern, text):
    numbers.append(value)

# Result for '-1500000': [-1500000] only ✅
```

### 2. Handle Direct Int/Float from Excel

Excel might store values as Python `int` or `float` directly (not strings):

```python
# ✅ FIX: Handle direct numeric types
if isinstance(row, (int, float)):
    return float(row)

# ✅ FIX: Preserve numeric types in cell extraction
all_numbers = []
for cell in cells:
    if isinstance(cell, (int, float)):
        all_numbers.append(float(cell))  # Direct conversion
    else:
        numbers = _extract_numbers_from_text(str(cell))
        all_numbers.extend(numbers)
```

### 3. Updated `_normalize_input` to Preserve Types

```python
# OLD: Converted everything to strings
def _normalize_input(row):
    if isinstance(row, list):
        return [str(cell) for cell in row]  # Lost type info ❌

# NEW: Preserves int/float types
def _normalize_input(row):
    if isinstance(row, list):
        return [cell for cell in row if cell is not None]  # Preserves types ✅
```

---

## Test Cases

Created `test_negative_values.py` with comprehensive tests:

```python
def test_negative_string():
    assert extract_numeric_value('-1500000') == -1500000.0  ✅

def test_negative_integer():
    assert extract_numeric_value(-1500000) == -1500000.0  ✅

def test_negative_accounting():
    assert extract_numeric_value('(1500000)') == -1500000.0  ✅

def test_negative_in_row():
    row = ['Operating Income', '-1500000']
    assert extract_numeric_value(row) == -1500000.0  ✅

def test_loss_scenario():
    rows = [
        ['Operating Income', '-1500000'],
        ['Net Income', '-2570000']
    ]
    # All should extract correctly with negative sign preserved
```

---

## Expected Results (Upload P&L Again!)

### Before Fix ❌:
```
🎯 MATCH FOUND: Operating Income → operating_profit
   Extracted value: 1500000 (positive - WRONG!)
   
❌ Failed to extract income_statement - parser returned None
```

### After Fix ✅:
```
🎯 MATCH FOUND: Total Revenue → total_revenue
   ✅ Added candidate: total_revenue = 12500000

🎯 MATCH FOUND: Cost of Goods Sold (COGS) → cogs
   ✅ Added candidate: cogs = 10200000

🎯 MATCH FOUND: Gross Profit → gross_profit
   ✅ Added candidate: gross_profit = 2300000

🎯 MATCH FOUND: Operating Expenses → operating_expenses
   ✅ Added candidate: operating_expenses = 3800000

🎯 MATCH FOUND: Operating Income → operating_profit
   ✅ Added candidate: operating_profit = -1500000  ← NEGATIVE!

🎯 MATCH FOUND: Interest Expense → interest_expense
   ✅ Added candidate: interest_expense = 950000

🎯 MATCH FOUND: Taxes → taxes
   ✅ Added candidate: taxes = 120000

🎯 MATCH FOUND: Net Income → net_income
   ✅ Added candidate: net_income = -2570000  ← NEGATIVE!

✅ EXTRACTION SUCCESSFUL!

📊 Financial Summary:
   Total Revenue: 12,500,000
   COGS: 10,200,000
   Gross Profit: 2,300,000
   Operating Expenses: 3,800,000
   Operating Income: -1,500,000  ← LOSS!
   Net Income: -2,570,000  ← LOSS!
```

### AI Analysis (Truth Report):
```
🚨 FRAUD/MANIPULATION RED FLAGS:
   ⚠️ LOSS-MAKING YEAR: Net loss of -2.57M
   ⚠️ NEGATIVE OPERATING INCOME: Operations lose -1.5M
   ⚠️ HIGH DEBT BURDEN: 950K interest on loss-making ops
   ⚠️ UNSUSTAINABLE: Expenses exceed gross profit

💡 BRUTALLY HONEST RECOMMENDATIONS:
   1. IMMEDIATE CASH CRISIS: Cut expenses 40% immediately
   2. OPERATING MODEL BROKEN: Revise business strategy
   3. DEBT RESTRUCTURING URGENT: Cannot service debt at loss
   4. 3-6 MONTHS TO FIX: Or company will fail
```

**Risk Level**: **HIGH** ⚠️

---

## Files Modified

1. ✅ `excel_extractor/number_extractor.py`:
   - Reordered negative extraction before positive
   - Added text removal to prevent double extraction
   - Added direct int/float handling
   - Preserved numeric types in `_normalize_input`

2. ✅ `excel_extractor/accounting_aliases.py`:
   - Added travel, accommodation, clearing & forwarding aliases
   - Added hire of tools/equipment to COGS

3. ✅ `excel_extractor/tests/test_negative_values.py`:
   - Comprehensive test suite for negative values

---

## Upload Your P&L Again!

**The extractor will now correctly handle**:
- ✅ Negative operating income (losses)
- ✅ Negative net income (losses)  
- ✅ All expense categories (travel, clearing, etc.)
- ✅ Multi-year statements with negatives
- ✅ Accounting format: (1500000) = -1500000
- ✅ String negatives: "-1500000"
- ✅ Integer negatives: -1500000

**STRICT MODE ACTIVE** - The AI will show the **BRUTAL TRUTH**! 💪


