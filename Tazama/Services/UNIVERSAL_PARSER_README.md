# Universal Financial Statement Parser

## 🎯 Overview

The **Universal Financial Statement Parser** is a production-ready, intelligent parser that automatically reads, cleans, normalizes, and interprets data from **any financial statement format**. It supports Income Statements, Profit & Loss statements, Balance Sheets, and Cash Flow statements across multiple file formats.

## ✨ Key Features

### 1. **Dynamic File Handling**
- ✅ Supports **CSV, TSV, XLS, XLSX** formats
- ✅ Automatic encoding detection (UTF-8, Latin-1, ISO-8859-1, CP1252)
- ✅ Automatic delimiter detection
- ✅ Multi-sheet Excel support (uses first sheet by default)

### 2. **Intelligent Date Extraction**
- ✅ Detects reporting dates from headers and filenames
- ✅ Recognizes patterns like:
  - "for the year ended 31 Dec 2025"
  - "Q4 2024"
  - "2024-Q2"
  - "October–December 2025"
- ✅ Automatically calculates next-period projection dates

### 3. **Smart Section Identification**
Automatically classifies rows into logical categories:
- **Revenue** / Sales / Income
- **Cost of Revenue** / COGS
- **Expenses** (Admin, Marketing, Salaries, etc.)
- **Gross Profit**
- **Operating Income** / EBIT
- **Net Income** / Profit
- **Assets** / Liabilities / Equity (Balance Sheet)
- **Cash Inflows** / Outflows (Cash Flow)

### 4. **Robust Numeric Normalization**
Handles various amount formats:
- `KES 1,200,000` → `1200000.0`
- `1.2M` → `1200000.0`
- `500K` → `500000.0`
- `$1.5 million` → `1500000.0`
- Strips currency symbols (KES, $, €, £, etc.)
- Handles negative values: `(150,000)` → `-150000.0`

### 5. **Automatic Metric Calculation**
Computes key financial metrics:
- Total Revenue
- Cost of Revenue
- Gross Profit = Total Revenue – Cost of Revenue
- Operating Expenses
- Operating Income = Gross Profit – Operating Expenses
- Net Income
- Profit Margin = (Net Income / Total Revenue) × 100
- Operating Margin, Gross Margin, Expense Ratio

### 6. **Intelligent Projections**
- Generates next-period forecasts based on detected dates
- Default growth assumptions:
  - Revenue: +8%
  - Net Income: +10%
  - Expenses: +5%
- Automatically calculates projection period (Q1 2026, Year 2026, etc.)

### 7. **Multi-Format Output**
- **Structured JSON** for ML processing
- **Human-readable summary** with formatted metrics
- **Period-aware projections** with growth percentages

## 📦 Installation

No additional dependencies beyond standard Django/Python stack:

```python
# Already installed in your environment:
import pandas  # Data processing
import numpy  # Numerical operations
from dateutil import parser  # Date parsing
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
```

## 🚀 Usage

### Basic Usage

```python
from Tazama.Services.UniversalFinancialParser import parse_financial_statement

# Parse any financial statement
result = parse_financial_statement('path/to/statement.csv')

if result['success']:
    print(result['summary'])  # Human-readable summary
    print(result['json_output'])  # Structured JSON
    
    # Access structured data
    metrics = result['structured_data']['current_metrics']
    print(f"Total Revenue: {metrics['total_revenue']:,.2f}")
    print(f"Net Income: {metrics['net_income']:,.2f}")
    print(f"Profit Margin: {metrics['profit_margin']:.1f}%")
    
    # Access projections
    projections = result['structured_data']['projections']
    print(f"Next Period: {projections['period_label']}")
    print(f"Projected Revenue: {projections['projected_revenue']:,.2f}")
```

### Integration with Django Pipeline

The parser is already integrated into your `CompleteAnalysisPipeline`:

```python
from Tazama.Services.CompleteAnalysisPipeline import CompleteAnalysisPipeline

# Upload processing automatically uses Universal Parser
pipeline = CompleteAnalysisPipeline()
result = pipeline.process_complete_workflow(upload_record)
```

### Standalone Usage

```python
from Tazama.Services.UniversalFinancialParser import UniversalFinancialParser

parser = UniversalFinancialParser()
result = parser.parse_file('financial_statement.xlsx')

# Access detected metadata
print(f"Statement Type: {parser.statement_type}")
print(f"Currency: {parser.currency}")
print(f"Period: {parser.detected_period}")
```

## 📊 Input Examples

### Example 1: Income Statement (Tabular)

```csv
Section,Item,Amount (KES)
Revenue,Sales Revenue,850000
Revenue,Service Revenue,150000
Revenue,Total Revenue,1000000
Expenses,Salaries & Wages,300000
Expenses,Rent,50000
Expenses,Marketing,40000
Expenses,Total Expenses,460000
Net Income,Profit Before Tax,540000
```

**Output:**
```
Total Revenue:          KES 1,000,000.00
Operating Expenses:     KES 460,000.00
Net Income:             KES 540,000.00
Profit Margin:          54.0%

Next Period Projections (Q1 2026)
Projected Revenue:      KES 1,080,000.00 (+8.0% growth)
Projected Net Income:   KES 594,000.00 (+10.0% growth)
```

### Example 2: Balance Sheet

```csv
Category,Item,Amount (KES)
Assets,Cash,1200000
Assets,Accounts Receivable,400000
Assets,Total Assets,1900000
Liabilities,Accounts Payable,250000
Liabilities,Total Liabilities,450000
Equity,Retained Earnings,1350000
Equity,Total Equity,1450000
```

### Example 3: Abbreviated Amounts

```csv
Account,Q4 2025 (KES)
Total Revenue,1.5M
Operating Expenses,650K
Net Profit,850K
```

**Automatically parsed to:**
- Total Revenue: 1,500,000
- Operating Expenses: 650,000
- Net Profit: 850,000

## 🔧 Configuration

### Custom Growth Rates

```python
parser = UniversalFinancialParser()
parser.DEFAULT_GROWTH_RATES = {
    'revenue': 0.12,  # 12%
    'net_income': 0.15,  # 15%
    'expenses': 0.08,  # 8%
}
result = parser.parse_file('statement.csv')
```

### Custom Section Keywords

```python
parser = UniversalFinancialParser()
parser.SECTION_KEYWORDS['revenue'].extend(['turnover', 'receipts'])
result = parser.parse_file('statement.csv')
```

## 📈 Output Structure

### Structured JSON Schema

```json
{
  "success": true,
  "structured_data": {
    "metadata": {
      "statement_type": "income_statement",
      "currency": "KES",
      "period": {
        "start_date": "2025-10-01",
        "end_date": "2025-12-31",
        "period_type": "quarterly",
        "quarter": 4,
        "year": 2025
      }
    },
    "current_metrics": {
      "total_revenue": 1000000.0,
      "cost_of_revenue": 0.0,
      "gross_profit": 1000000.0,
      "total_operating_expenses": 460000.0,
      "operating_income": 540000.0,
      "net_income": 540000.0,
      "profit_margin": 54.0,
      "operating_margin": 54.0,
      "gross_margin": 100.0,
      "expense_ratio": 46.0
    },
    "projections": {
      "period_label": "Q1 2026",
      "start_date": "2026-01-01",
      "end_date": "2026-03-31",
      "projected_revenue": 1080000.0,
      "projected_net_income": 594000.0,
      "projected_expenses": 483000.0,
      "revenue_growth": 8.0,
      "net_income_growth": 10.0,
      "projected_profit_margin": 55.0
    }
  },
  "summary": "...",
  "json_output": "..."
}
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
cd Tazama/Services
python test_universal_parser.py
```

This tests:
- ✅ Standard income statements
- ✅ Balance sheets
- ✅ Abbreviated amounts (1.5M, 650K)
- ✅ Various date formats
- ✅ Different file encodings
- ✅ Multi-column layouts

## 🔍 How It Works

### 1. **File Loading**
- Detects file format (CSV, TSV, Excel)
- Tries multiple encodings and delimiters
- Loads data into pandas DataFrame

### 2. **Metadata Extraction**
- Scans filename and file content for dates
- Detects currency symbols
- Identifies reporting period

### 3. **Data Normalization**
- Identifies label and amount columns
- Cleans and parses numeric values
- Removes empty rows

### 4. **Section Classification**
- Uses keyword matching to classify rows
- Handles variations in naming conventions
- Automatically detects statement type

### 5. **Metric Calculation**
- Sums categorized amounts
- Derives missing metrics (Gross Profit, Operating Income)
- Calculates ratios and percentages

### 6. **Projection Generation**
- Calculates next period dates
- Applies growth rates
- Generates formatted projections

## 🛡️ Robustness Features

- ✅ **Fallback mechanisms** if primary parsers fail
- ✅ **Graceful handling** of missing sections
- ✅ **Conservative defaults** when data is incomplete
- ✅ **Logging** at all stages for debugging
- ✅ **Type safety** with proper error handling

## 🎨 Frontend Integration

The parser is fully integrated with your Tazama dashboard. When a user uploads a file:

1. File is saved to `FinancialDataUpload`
2. `CompleteAnalysisPipeline` triggers automatic parsing
3. Universal Parser extracts and normalizes data
4. Results stored in `ProcessedFinancialData`
5. Dashboard displays metrics and projections

**No frontend parsing needed!** Everything is handled server-side.

## 📝 API Response Example

After upload and processing, the dashboard endpoint returns:

```json
{
  "statement_snapshot": {
    "total_revenue": 1000000,
    "net_income": 540000,
    "profit_margin": 0.54,
    ...
  },
  "intelligent_analysis": {
    "intelligent_projections": {
      "next_period": {
        "projected_revenue": 1080000,
        "projected_net_income": 594000,
        ...
      }
    }
  }
}
```

## 🚨 Error Handling

The parser includes comprehensive error handling:

```python
result = parse_financial_statement('file.csv')

if not result['success']:
    print(f"Error: {result.get('error')}")
    # Fallback logic or user notification
```

Common error scenarios handled:
- Unsupported file formats
- Corrupt files
- Missing required sections
- Invalid numeric formats
- Encoding issues

## 🔄 Continuous Improvement

The parser supports easy extension:

1. **Add new section keywords** in `SECTION_KEYWORDS`
2. **Add new date patterns** in `DATE_PATTERNS`
3. **Customize growth rates** per statement type
4. **Extend currency detection** logic

## 📞 Support

For issues or questions:
- Check logs: `logger.info()` statements throughout
- Run test suite: `python test_universal_parser.py`
- Review parse result: `result['structured_data']`

---

**Version:** 1.0.0  
**Author:** Tazama AI Financial System  
**Last Updated:** October 31, 2025





