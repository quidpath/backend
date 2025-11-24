#!/usr/bin/env python
"""
Test the Financial Reconciliation Engine
Run: docker exec django-backend-dev python test_reconciliation_engine.py
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.core.FinancialReconciliationEngine import FinancialReconciliationEngine

print("=" * 80)
print("🔧 FINANCIAL RECONCILIATION ENGINE TEST")
print("=" * 80)

# Your test data with multiple errors
test_data = {
    'revenue': 3200000,
    'costOfGoodsSold': 200000,
    'grossProfit': 3300000,  # ❌ WRONG: Should be 3,000,000
    'otherIncome': 96000,
    'operatingIncomeBeforeOPEX': 1856000,  # ❌ WRONG
    'operatingExpenses': 50000,
    'operatingProfit': 1280000,  # ❌ WRONG
    'financeCosts': -38400,  # ❌ WRONG: Negative (should be positive)
    'profitBeforeTax': 1241600,  # ❌ WRONG
    'incomeTaxExpense': -372480,  # ❌ WRONG: Negative (should be positive)
    'netProfit': 869120  # ❌ WRONG
}

print("\n📊 ORIGINAL (INCORRECT) DATA:")
print("-" * 80)
for key, value in test_data.items():
    print(f"   {key:30s}: KES {value:>15,.2f}")

# Run reconciliation
engine = FinancialReconciliationEngine()
result = engine.reconcile_statement(test_data)

print("\n" + "=" * 80)
print("✅ RECONCILIATION COMPLETE")
print("=" * 80)

print(f"\nStatus: {'✅ RECONCILED' if result['is_reconciled'] else '❌ FAILED'}")
print(f"Corrections Made: {len(result['corrections_made'])}")
print(f"Risk Level: {result['risk_level']}")
print(f"Risk Reason: {result['risk_reason']}")

print("\n" + "=" * 80)
print("📋 RECONCILED (CORRECTED) DATA:")
print("=" * 80)
reconciled = result['reconciled_data']
for key, value in reconciled.items():
    if key != 'margins':
        print(f"   {key:30s}: KES {value:>15,.2f}")

print("\n📊 CALCULATED MARGINS:")
print("-" * 80)
margins = reconciled['margins']
for key, value in margins.items():
    print(f"   {key:30s}: {value:>6.2f}%")

print("\n" + "=" * 80)
print("📝 DETAILED RECONCILIATION REPORT:")
print("=" * 80)
print(result['reconciliation_report'])

print("\n" + "=" * 80)
print("💼 LENDING RECOMMENDATION:")
print("=" * 80)
print(f"   {result['lending_recommendation']}")

# Export as JSON
print("\n" + "=" * 80)
print("📤 JSON OUTPUT (for API response):")
print("=" * 80)
json_output = {
    'reconciled_data': result['reconciled_data'],
    'corrections_made': result['corrections_made'],
    'risk_level': result['risk_level'],
    'lending_recommendation': result['lending_recommendation']
}
print(json.dumps(json_output, indent=2))

print("\n" + "=" * 80)
print("✅ TEST COMPLETE!")
print("=" * 80)

