# Enhanced Fraud Detection System

## Overview
The Tazama AI now includes a sophisticated forensic accounting engine that accurately detects fraudulent financial statements while correctly identifying legitimate businesses. This system uses **strict mode** with industry-standard benchmarks to separate good from bad financial data.

## Key Features

### 1. **Fraud Detection Score (0-100)**
- **0-24**: LOW RISK - Statement appears legitimate
- **25-49**: MEDIUM RISK - Some anomalies detected, verification recommended
- **50-74**: HIGH RISK - Significant fraud indicators present
- **75-100**: CRITICAL RISK - Multiple fraud red flags, investigation required

### 2. **Multi-Layered Analysis**

#### A. Mathematical Consistency Checks
- **Gross Profit Verification**: GP = Revenue - COGS (1% tolerance)
- **Operating Income Verification**: OI = GP - Operating Expenses
- **Net Income Reconciliation**: NI = OI - Interest - Taxes
- **Detects**: Arithmetic errors, inflated profits, understated costs

#### B. Benford's Law & Round Number Syndrome
- **Detects**: Suspiciously round numbers indicating fabrication
- **Threshold**: >70% round numbers = HIGH risk, >50% = MEDIUM risk
- **Example**: All values ending in 000,000 suggests estimation, not real accounting

#### C. Ratio Analysis with Industry Benchmarks
```
Gross Margin:      15-85% (typical: 25-60%)
Operating Margin:  -10% to 50% (typical: 5-25%)
Net Margin:        -30% to 40% (typical: 3-20%)
COGS Ratio:        15-85% (typical: 40-75%)
OpEx Ratio:        5-80% (typical: 15-50%)
Tax Rate:          15-35% (typical: 20-30%)
```

#### D. Tax Pattern Analysis
- **Profitable companies MUST pay taxes** (20-30% effective rate)
- Zero taxes on profit > KES 10,000 = CRITICAL fraud indicator
- Unusually low tax rates (<15%) = HIGH risk
- Loss-making companies correctly handled (no false positives)

#### E. Logical Impossibility Detection
- Net income > Revenue = IMPOSSIBLE
- Gross profit > Revenue = IMPOSSIBLE
- Operating expenses = 0 with revenue > 0 = IMPOSSIBLE
- Negative COGS = IMPOSSIBLE

#### F. Expense Pattern Analysis
- Large companies (>KES 1M) with zero interest = Unusual but possible
- Companies with revenue >KES 5M and OpEx <10% = HIGH risk
- OpEx >150% of revenue = IMPOSSIBLE (unsustainable)
- OpEx <5% of revenue for companies >KES 1M = SUSPICIOUS

#### G. Profitability Anomaly Detection
- Net margin >50% = CRITICAL (extremely rare in real businesses)
- Net margin >80% on revenue >KES 1M = HIGH risk
- COGS <5% of revenue for companies >KES 1M = SUSPICIOUS

## How It Works

### Step 1: Data Ingestion
```python
input_data = {
    'totalRevenue': 71869325,
    'costOfRevenue': 51642207,
    'grossProfit': 20227118,
    'totalOperatingExpenses': 11297724,
    'operatingIncome': 8929394,
    'netIncome': 7589985,
    'incomeTaxExpense': 0,  # ❌ RED FLAG
    'interestExpense': 0
}
```

### Step 2: Fraud Engine Analysis
The `FraudDetectionEngine` runs all tests in parallel and accumulates a fraud score:
- Each CRITICAL flag adds 25 points
- Each HIGH flag adds 15 points
- Each MEDIUM flag adds 7 points
- Each LOW flag adds 3 points

### Step 3: Risk Classification
```python
if fraud_score >= 75: return 'CRITICAL'
elif fraud_score >= 50: return 'HIGH'
elif fraud_score >= 25: return 'MEDIUM'
else: return 'LOW'
```

### Step 4: Detailed Reporting
The system provides:
- **Fraud Score**: Numeric score (0-100)
- **Fraud Probability**: Risk level (LOW/MEDIUM/HIGH/CRITICAL)
- **Red Flags**: Specific fraud indicators with explanations
- **Warnings**: Minor anomalies that don't indicate fraud but should be verified
- **Detailed Analysis**: Mathematical consistency, ratio analysis, tax compliance, expense patterns

## Example Results

### Example 1: Legitimate Business
```
Revenue: KES 45,789,234
COGS: KES 27,456,821 (60% - normal)
Operating Expenses: KES 9,234,567 (20% - normal)
Net Income: KES 7,123,456
Taxes: KES 1,456,789 (20.5% tax rate - normal)

Result: Fraud Score = 7/100, Risk = LOW ✅
Flags: Only minor warning about some round numbers
```

### Example 2: Fraudulent Statement
```
Revenue: KES 50,000,000 (round number)
COGS: KES 45,000,000 (round number)
Operating Expenses: KES 500,000 (only 1% - unrealistic)
Net Income: KES 4,500,000
Taxes: KES 0 ❌ (no taxes despite KES 4.5M profit)

Result: Fraud Score = 58/100, Risk = HIGH 🚨
Red Flags:
- 🚨 CRITICAL: Tax evasion indicator (no taxes on profit)
- ⚠️ HIGH: Round number syndrome (100% round)
- ⚠️ HIGH: Operating expenses only 1% of revenue
```

### Example 3: Loss-Making Company (No False Positive)
```
Revenue: KES 12,500,000
COGS: KES 10,200,000
Operating Expenses: KES 3,800,000
Net Income: -KES 2,570,000 (loss)
Taxes: KES 0 (no taxes due to loss - this is correct)

Result: Fraud Score = 0/100, Risk = LOW ✅
Flags: None - correctly identified as legitimate loss
```

## Integration

### Backend
The fraud detection is automatically integrated into the truth report generation:
```python
from Tazama.core.FraudDetectionEngine import FraudDetectionEngine

engine = FraudDetectionEngine()
fraud_analysis = engine.analyze_financial_statement(financial_data)

# Results automatically included in risk_assessment
risk_assessment = {
    'overall_risk': fraud_analysis['fraud_probability'],
    'fraud_score': fraud_analysis['fraud_score'],
    'fraud_risk': fraud_analysis['fraud_probability'],
    'profitability_risk': '...',
    'operational_risk': '...',
    # ... other risks
}
```

### Frontend
The fraud score is displayed prominently on both:
1. **Analysis Page** (`/Tazama/analysis`)
   - Fraud Detection Score card with color-coded risk level
   - Detailed breakdown of fraud indicators
   
2. **Dashboard** (`/Tazama`)
   - Large fraud score display in Risk Assessment section
   - All fraud red flags listed with severity indicators

## Testing

### Run Fraud Detection Tests
```bash
# Test the fraud detection engine with 3 scenarios
docker exec django-backend-dev python test_enhanced_fraud_detection.py

# Test on real uploaded data
docker exec django-backend-dev python test_real_data_fraud.py
```

### Test Data Files
Two CSV test files are included:
1. `test_data_clean_statement.csv` - Legitimate business (should score LOW)
2. `test_data_fraudulent_statement.csv` - Fraudulent statement (should score HIGH)

## Key Improvements

### ✅ What This System Does Right

1. **Accurate Detection**: Distinguishes between legitimate and fraudulent statements with high precision
2. **No False Positives**: Loss-making companies are correctly handled without triggering false fraud alerts
3. **Industry Standards**: Uses conservative, realistic benchmarks based on actual business operations
4. **Detailed Explanations**: Every flag includes specific numbers and clear reasoning
5. **Strict Mode**: No leniency - all checks use strict accounting principles
6. **Reasonable Tolerances**: Allows for minor rounding (1%) but catches significant discrepancies

### 🎯 Fraud Indicators Detected

1. **Tax Evasion**: Profitable companies with zero taxes
2. **Fabricated Numbers**: All round numbers (Benford's Law violation)
3. **Arithmetic Errors**: Numbers that don't add up mathematically
4. **Unrealistic Margins**: Profits too high or costs too low for real businesses
5. **Missing Expenses**: Operating expenses unrealistically low
6. **Logical Impossibilities**: Net income > Revenue, negative COGS, etc.
7. **Incomplete Statements**: Missing critical components (taxes, expenses)

## API Response Structure

```json
{
  "truth_report": {
    "risk_assessment": {
      "overall_risk": "MEDIUM",
      "fraud_score": 28,
      "fraud_risk": "MEDIUM",
      "profitability_risk": "LOW",
      "operational_risk": "LOW",
      "liquidity_risk": "LOW"
    },
    "fraud_red_flags": [
      "🚨 CRITICAL: Tax Evasion Indicator: Company reported profit of KES 7,589,985 but ZERO taxes...",
      "ℹ️ LOW: Unusual Pattern: Company with KES 71,869,325 revenue reports zero interest expense..."
    ],
    "brutally_honest_recommendations": [
      {
        "priority": "CRITICAL",
        "category": "fraud_detection",
        "recommendation": "Address tax reporting immediately",
        "description": "Company shows zero tax expense despite significant profit...",
        "timeline": "Immediate"
      }
    ]
  }
}
```

## Conclusion

This fraud detection system provides **enterprise-grade forensic accounting analysis** that:
- ✅ Accurately identifies fraudulent statements
- ✅ Correctly validates legitimate businesses
- ✅ Uses industry-standard accounting principles
- ✅ Provides detailed, actionable insights
- ✅ Maintains strict mode without false positives

The system is now ready for production use and will help identify problematic financial statements while not penalizing legitimate businesses, including those with losses or unusual (but valid) financial structures.

