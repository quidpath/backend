# 🚀 Universal Financial Parser - Quick Start Guide

## ⚡ 30-Second Overview

The Universal Financial Parser automatically reads **any financial statement** and extracts all KPIs — no formatting required!

---

## 📤 For End Users (Upload Flow)

### Step 1: Prepare Your File
**Supported formats:**
- ✅ CSV (.csv)
- ✅ Excel (.xlsx, .xls)
- ✅ Tab-separated (.tsv)

**Any layout works:**
```
Column A: Item names    Column B: Amounts
Column A: Section       Column B: Account    Column C: KES
Multiple columns        ...anything!
```

### Step 2: Upload
1. Go to Tazama Dashboard
2. Click "Upload Data"
3. Select your file
4. Click "Upload"

### Step 3: View Results
- Dashboard automatically shows:
  - ✅ Total Revenue (correct!)
  - ✅ Net Income (correct!)
  - ✅ All KPIs (correct!)
  - ✅ Next-period projections

**That's it! No manual entry, no reformatting.**

---

## 💻 For Developers (API Usage)

### Standalone Parsing

```python
from Tazama.Services.UniversalFinancialParser import parse_financial_statement

# Parse any file
result = parse_financial_statement('income_statement.xlsx')

if result['success']:
    # Get metrics
    metrics = result['structured_data']['current_metrics']
    print(f"Revenue: {metrics['total_revenue']:,.2f}")
    print(f"Net Income: {metrics['net_income']:,.2f}")
    
    # Get projections
    proj = result['structured_data']['projections']
    print(f"Next Period: {proj['period_label']}")
    print(f"Projected Revenue: {proj['projected_revenue']:,.2f}")
    
    # Print summary
    print(result['summary'])
```

### Via Upload Workflow (Automatic)

```python
# Upload via Django view - parsing happens automatically
upload_record = FinancialDataUpload.objects.create(...)

from Tazama.Services.CompleteAnalysisPipeline import CompleteAnalysisPipeline
pipeline = CompleteAnalysisPipeline()
result = pipeline.process_complete_workflow(upload_record)

# Metrics stored in ProcessedFinancialData
data = ProcessedFinancialData.objects.filter(upload=upload_record).first()
print(f"Revenue: {data.total_revenue}")
print(f"Net Income: {data.net_income}")
```

### Command-Line Testing

```bash
cd C:\Users\Chessman\erpbackend\quidpath-erp-backend\Tazama\Services

# Test your file
python UniversalFinancialParser.py path/to/your/file.csv

# Run test suite
python test_universal_parser.py
```

---

## 🔍 What It Detects Automatically

### ✅ Dates & Periods
```
"for the year ended 31 December 2025"  → 2025-12-31
"Q4 2024"                              → Oct-Dec 2024
"2024-Q2"                              → Apr-Jun 2024
"Income_Statement_2025_Q3.xlsx"        → Jul-Sep 2025
```

### ✅ Sections
```
Revenue items:        Sales, Revenue, Income, Turnover, Service Revenue
Expense items:        Salaries, Rent, Marketing, Utilities, Travel
COGS:                 Cost of Revenue, COGS, Production Costs
Profit items:         Net Income, Profit, Net Profit, Earnings
```

### ✅ Amounts
```
"1,000,000"           → 1000000
"KES 1,200,000"       → 1200000
"1.5M"                → 1500000
"500K"                → 500000
"$2.3 million"        → 2300000
"(150,000)"           → -150000 (negative)
```

---

## ✅ What It Calculates

### Primary Metrics
- **Total Revenue** (sum of all revenue items)
- **Cost of Revenue** (COGS)
- **Gross Profit** = Revenue - COGS
- **Operating Expenses** (sum of all expense items)
- **Operating Income** = Gross Profit - Expenses
- **Net Income** (explicit or derived)

### Ratios & Margins
- **Profit Margin** = Net Income / Revenue × 100
- **Operating Margin** = Operating Income / Revenue × 100
- **Gross Margin** = Gross Profit / Revenue × 100
- **Expense Ratio** = Expenses / Revenue × 100

### Projections (Next Period)
- **Projected Revenue** (+8% growth)
- **Projected Net Income** (+10% growth)
- **Projected Expenses** (+5% growth)
- **Projected Profit Margin**

---

## 🛠️ Customization

### Change Growth Rates

```python
from Tazama.Services.UniversalFinancialParser import UniversalFinancialParser

parser = UniversalFinancialParser()
parser.DEFAULT_GROWTH_RATES = {
    'revenue': 0.12,      # 12% instead of 8%
    'net_income': 0.15,   # 15% instead of 10%
    'expenses': 0.07      # 7% instead of 5%
}

result = parser.parse_file('statement.csv')
```

### Add Custom Keywords

```python
parser = UniversalFinancialParser()

# Add industry-specific terms
parser.SECTION_KEYWORDS['revenue'].extend([
    'subscription revenue',
    'license fees',
    'consulting income'
])

result = parser.parse_file('statement.csv')
```

---

## ⚠️ Troubleshooting

### "No data found"
- ✅ Check file has at least 2 rows (header + data)
- ✅ Ensure amounts are in a numeric column
- ✅ Verify file is not password-protected

### "Incorrect totals"
- ✅ Check if "Total Revenue" row exists
- ✅ Verify amounts don't have hidden characters
- ✅ Look at logs: parser shows what it detected

### "Date not detected"
- ✅ Add date to filename (e.g., `statement_Q4_2025.csv`)
- ✅ Or add header row: "Period: Oct-Dec 2025"
- ✅ Default: uses today's date if none found

### "Wrong section classification"
- ✅ Check logs to see what was classified where
- ✅ Add custom keywords (see Customization above)
- ✅ Or use explicit "Total" rows

---

## 📊 Example Files

### ✅ Works Great With:

**Format 1: Section-Item-Amount**
```csv
Section,Item,Amount (KES)
Revenue,Sales,850000
Revenue,Services,150000
Expenses,Salaries,300000
Expenses,Rent,50000
```

**Format 2: Item-Amount**
```csv
Account,Q4 2025
Total Revenue,1000000
Operating Expenses,460000
Net Profit,540000
```

**Format 3: Multi-Column**
```csv
Description,Amount,Currency,Period
Sales Revenue,850000,KES,Q4 2025
Service Revenue,150000,KES,Q4 2025
```

**All produce the same accurate results!**

---

## 🎓 Best Practices

### 1. Include Period in Filename
```
✅ income_statement_Q4_2025.xlsx
✅ PnL_2025_annual.csv
✅ financial_data_oct_dec_2025.xlsx
❌ data.csv (no date context)
```

### 2. Use Clear Labels
```
✅ "Total Revenue" or "Revenue"
✅ "Net Income" or "Net Profit"
✅ "Operating Expenses" or "Expenses"
❌ "ABC123" or unlabeled rows
```

### 3. Include Total Rows
```
Revenue items...
Total Revenue    1,000,000  ← Parser uses this

Expense items...
Total Expenses     460,000  ← Parser uses this
```

### 4. One Statement per File
- Upload one P&L or one Balance Sheet per file
- Don't mix statement types in one file

---

## 📞 Support

### Check Logs
```python
import logging
logging.basicConfig(level=logging.INFO)

# Parser logs every step:
# - File loaded: X rows
# - Date detected: Q4 2025
# - Sections classified: 5 revenue, 8 expenses
# - Metrics calculated: Revenue=1M, Expenses=460K
```

### Test with Sample Data
```bash
python test_universal_parser.py
```

### Manual Debugging
```python
result = parse_financial_statement('your_file.csv')
print(result['json_output'])  # See full structured data
```

---

## ✅ Success Checklist

When you upload a file, you should see:

- ✅ **Status:** "Processing completed"
- ✅ **Total Revenue:** Shows correct amount (NOT net income!)
- ✅ **Net Income:** Shows correct profit
- ✅ **Profit Margin:** Reasonable % (e.g., 20-60%)
- ✅ **Projections:** Next period with growth %
- ✅ **Period:** Correct quarter/year detected

**If all ✅, you're good to go!**

---

## 🎉 That's It!

You now have an intelligent parser that:
- Reads **any format**
- Finds **all KPIs**
- Generates **projections**
- **Zero manual work**

Just upload and analyze! 🚀

---

**Need Help?**
- 📖 Full docs: `UNIVERSAL_PARSER_README.md`
- 📝 Summary: `IMPLEMENTATION_SUMMARY.md`
- 🧪 Tests: `test_universal_parser.py`



