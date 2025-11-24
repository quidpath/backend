# Priority Fix for "Total" Rows with Value = 0

## Issue

The extractor was correctly identifying line items AND "Total" rows, but **"Total" rows with value = 0** were being selected over actual line items because they had higher priority (2.0 vs 1.0).

### Example from Ozonecool P&L:

**Candidates Found**:
- ✅ "Sales" = 35,143,811 (priority 1.0) ← Correct value!
- ❌ "Total for Operating Income" = 0 (priority 2.0) ← Selected because higher priority!

**Result**:
- total_revenue = 0 ❌ (should be 35,143,811)
- cogs = 0 ❌ (should be 15,664,882)
- operating_expenses = 0 ❌ (should be sum of line items)

## Root Cause

In the candidate selection logic, "Total" rows are given priority 2.0 because they're usually more accurate summaries. **BUT** in many P&L statements exported from accounting software, "Total" rows have placeholder value = 0 (because the software expects to calculate them, but the export shows 0).

## Fix Applied

### 1. Downgrade Priority for Zero-Value "Total" Rows

**Logic**:
```python
# If this is a "Total" row
if 'total' in label_lower and is_summary_row:
    # Check if row has any non-zero values
    has_nonzero = False
    for cell in row_list[1:]:
        if cell != 0 and cell != '0':
            has_nonzero = True
            break
    
    # If "Total" row = 0, give it LOWER priority than line items
    if not has_nonzero:
        priority = 0.5  # Lower than line items (1.0)
```

**Code Location**: `excel_extractor/intelligent.py` lines 256-277

### 2. Expanded Blacklist for Expense Line Items

Added specific expense items to blacklist to prevent them from matching to financial fields:
- "uniforms", "staff uniforms"
- "housing levy", "nssf", "nhif"
- "statutory", "statutory expense"
- "bond", "performance bond"

**Code Location**: `excel_extractor/label_matcher.py` lines 70-76

## Expected Results After Fix

### For Ozonecool P&L:

**Before**:
```json
{
  "total_revenue": 0,           ← WRONG (picked "Total for Operating Income" = 0)
  "cogs": 0,                    ← WRONG (picked "Total for Cost of Goods Sold" = 0)
  "operating_expenses": 0,      ← WRONG (picked "Total for Operating Expense" = 0)
  "net_income": 14132,          ← WRONG (picked "Staff uniforms")
  "taxes": 0                    ← WRONG (picked zero-value "Total")
}
```

**After**:
```json
{
  "total_revenue": 35143811,    ✅ (picked "Sales" with priority 1.0 > "Total" priority 0.5)
  "cogs": 15664882,             ✅ (picked "Purchases – Parts & Materials")
  "operating_expenses": 4700384, ✅ (picked "Salaries and Employees wages")
  "net_income": [calculated],   ✅ ("Staff uniforms" blocked by blacklist)
  "taxes": 5850                 ✅ (picked "Taxation (P&L)")
}
```

## Priority System Summary

| Label Type | Has Value | Priority | Example |
|---|---|---|---|
| Line item | Non-zero | 1.0 | "Sales" = 35,143,811 |
| Line item | Zero | 1.0 | "Interest Income" = 0 |
| Total row | Non-zero | 2.0 | "Total Trading Income" = 1,643,990 |
| **Total row** | **Zero** | **0.5** | **"Total for Operating Income" = 0** |
| Section header | No value | skipped | "Operating Income" (empty row) |

## Testing

Upload the Ozonecool P&L again. You should see:

1. ✅ Section headers skipped: "Operating Income", "Cost of Goods Sold", "Operating Expense"
2. ✅ Line items extracted: "Sales" = 35,143,811
3. ✅ Zero-value totals downgraded: "⚠️ 'Total' row has value = 0, downgrading priority to 0.5"
4. ✅ Best candidate selected: "Sales" (priority 1.0) over "Total" (priority 0.5)
5. ✅ Expense items blocked: "Staff uniforms", "Housing Levy", "NSSF"

## Log Output Example

```
🎯 MATCH FOUND in rows orientation:
   Row 5, Label: 'Sales' → Field: total_revenue
   Extracted value: 35143811
✅ Added candidate: total_revenue = 35143811

🎯 MATCH FOUND in rows orientation:
   Row 7, Label: 'Total for Operating Income' → Field: total_revenue
   Extracted value: 0
⚠️ 'Total' row has value = 0, downgrading priority to 0.5
✅ Added candidate: total_revenue = 0

📊 Selecting best candidate for total_revenue:
   Candidate 1: 'Sales' = 35143811 (priority 1.0) ← SELECTED
   Candidate 2: 'Total for Operating Income' = 0 (priority 0.5)
```

## Files Modified

1. **`excel_extractor/intelligent.py`** (lines 256-277):
   - Added zero-value detection for "Total" rows
   - Downgrade priority from 2.0 to 0.5 if Total = 0

2. **`excel_extractor/label_matcher.py`** (lines 70-76):
   - Expanded blacklist with specific expense items
   - Added: uniforms, levy, statutory, bond, nssf, nhif

## Known Limitations

1. **Multiple line items for same field**: If there are 10 "admin_expenses" line items, we only extract the last one (highest priority among line items). Future: Sum all line items for the same field.

2. **"Total" calculation**: We don't calculate totals from line items. If "Total" = 0, we rely on individual line items being extracted. Future: Implement line-item summation.

3. **Nested totals**: "Total for Staff costs" is a sub-total under "Operating Expenses". We don't handle hierarchical summation yet.


