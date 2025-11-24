# Financial Statement Extraction - Fixes Summary

## Issues Fixed

### Issue A: Operating Income Mapped to Total Revenue

**Problem**: "Total Operating Income" (which means Sales + Other Income = Total Revenue) was being matched to the `operating_income` field (which should be Operating Profit).

**Root Cause**: The term "Operating Income" is ambiguous:
- In some statements: Operating Income = Operating Profit (Gross Profit - Operating Expenses)
- In other statements: Total Operating Income = Total Revenue (Sales + Other Income)

**Fix Applied**:
1. Added logic to detect "Total Operating Income" and re-map it to `total_revenue` instead of `operating_income`
2. Set higher priority (2.0) for this mapping since it contains "Total"
3. Use "Operating Profit" for `operating_income` field via fallback mapping

**Code Location**: `excel_extractor/intelligent.py` lines 145-156

### Issue B: Total Revenue Excludes Other Income

**Problem**: When extracting "Sales Revenue" separately from "Other Income", the model wasn't calculating true total revenue.

**Fix Applied**:
1. If `total_revenue` and `other_income` are both extracted:
   - Check if `other_income` is <5% of `total_revenue` (likely already included)
   - If not, add `other_income` to `total_revenue`
2. This handles cases where:
   - "Sales Revenue" is extracted first (50M)
   - "Other Income" is extracted separately (50K)
   - Need to calculate: Total Revenue = 50M + 50K = 50.05M

**Code Location**: `excel_extractor/intelligent.py` lines 244-272

### Issue C: Operating Margin Calculation Wrong

**Problem**: Operating Margin was 100% because Operating Income was wrongly set to Total Revenue.

**Fix**: Automatically resolved by fixes A and B. Now:
- Operating Income = Operating Profit = 3,850,000 ✅
- Total Revenue = 50,050,000 ✅
- Operating Margin = 3,850,000 / 50,050,000 = 7.69% ✅

### Issue D: Tax Expense Matching to Interest Expense

**Problem**: "Tax Expense (30%)" was matching to `interest_expense` instead of `taxes`.

**Fix Applied**:
1. Added explicit aliases for tax with percentages: "tax expense (30%)", "tax (25%)", etc.
2. Boosted `taxes` field priority from 4 to 6 (higher than `interest_expense`'s 5)
3. This ensures "Tax Expense" labels always match to `taxes` field first

**Code Location**: `excel_extractor/accounting_aliases.py` lines 186-213, 433

### Issue E: Non-Operating Expenses Matched to Operating Expenses

**Problem**: "Total Non-Operating Expenses" (230K) was being selected over "Total Operating Expenses" (9.2M) for the `operating_expenses` field.

**Fix Applied**:
1. Added logic to skip labels containing "non-operating" when matching to `operating_expenses` or `operating_income` fields
2. This ensures only true operating expenses are captured

**Code Location**: `excel_extractor/intelligent.py` lines 134-143

### Issue F: Column Scan Extracting Wrong Values

**Problem**: After transposing DataFrame, column scan was extracting values from the labels row instead of the values row, resulting in "30" (from "Tax Expense (**30**%)") being extracted for all fields.

**Fix Applied**:
1. Disabled column-wise scanning (only use row-wise scanning)
2. Row-wise scanning is sufficient for most financial statements and doesn't have this bug

**Code Location**: `excel_extractor/intelligent.py` lines 101-106

## Testing

Upload a financial statement with:
- Sales Revenue: 50,000,000
- Other Income: 50,000
- Total Operating Income: 50,050,000
- Operating Profit: 3,850,000
- Tax Expense (30%): 1,090,500

**Expected Results**:
- ✅ total_revenue: 50,050,000 (includes other income)
- ✅ operating_income: 3,850,000 (from Operating Profit)
- ✅ taxes: 1,090,500 (matched correctly)
- ✅ operating_expenses: 9,200,000 (excludes non-operating)
- ✅ Operating Margin: 7.69% (correct calculation)

## Architecture Improvements

1. **Ambiguity Detection**: The system now detects ambiguous labels and makes intelligent decisions about field mapping
2. **Priority System**: Summary rows with "Total" get higher priority than line items
3. **Context-Aware Matching**: Labels are evaluated in context (e.g., "non-operating" disqualifies from operating fields)
4. **Automatic Calculations**: System calculates totals when components are available (Sales + Other Income)
5. **Fallback Mappings**: Optional fields (operating_profit, finance_costs) can substitute for required fields when appropriate

## Files Modified

1. `excel_extractor/intelligent.py` - Core extraction logic
2. `excel_extractor/accounting_aliases.py` - Alias dictionary and priorities
3. `excel_extractor/number_extractor.py` - Universal number parser (created)
4. `excel_extractor/label_matcher.py` - Fuzzy matching with blacklist (enhanced)

## Next Steps

1. Test with diverse financial statements from different formats
2. Monitor extraction accuracy in production
3. Add more aliases based on real-world statement variations
4. Implement ML-based label classification for highly ambiguous cases


