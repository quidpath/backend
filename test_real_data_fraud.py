#!/usr/bin/env python
"""
Test enhanced fraud detection on real uploaded data
Run: docker exec django-backend-dev python test_real_data_fraud.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.Services.EnhancedFinancialDataService import EnhancedFinancialDataService
from Tazama.models import FinancialDataUpload
import json

# Get latest upload
latest = FinancialDataUpload.objects.order_by('-created_at').first()
print(f'📊 Running Enhanced Analysis on: {latest.file_name}')

# Get processed data
from Tazama.models import ProcessedFinancialData
processed = ProcessedFinancialData.objects.filter(upload=latest).order_by('-period_date').first()

# Prepare input
input_data = {
    'totalRevenue': float(processed.total_revenue),
    'costOfRevenue': float(processed.cost_of_revenue),
    'grossProfit': float(processed.gross_profit),
    'totalOperatingExpenses': float(processed.total_operating_expenses),
    'operatingIncome': float(processed.operating_income),
    'netIncome': float(processed.net_income),
    # Extract from additional_features if available, otherwise 0
    'incomeTaxExpense': float(processed.additional_features.get('income_tax_expense', 0)),
    'interestExpense': float(processed.additional_features.get('interest_expense', 0))
}

print(f'\n📈 Input Data:')
for k, v in input_data.items():
    print(f'   {k}: KES {v:,.2f}')

# Run analysis
service = EnhancedFinancialDataService()
truth_report = service._generate_truth_report(input_data, predictions=None)
print(f'\n🔍 Fraud Analysis:')
risk_assessment = truth_report.get('risk_assessment', {})
print(f'   Fraud Score: {risk_assessment.get("fraud_score", "N/A")}/100')
print(f'   Fraud Risk: {risk_assessment.get("fraud_risk", "N/A")}')
print(f'   Overall Risk: {risk_assessment.get("overall_risk", "N/A")}')

fraud_flags = truth_report.get('fraud_red_flags', [])
print(f'\n🚨 Fraud Red Flags: {len(fraud_flags)}')
for i, flag in enumerate(fraud_flags[:10], 1):  # Show first 10
    print(f'   {i}. {flag}')

recommendations = truth_report.get('brutally_honest_recommendations', [])
print(f'\n📋 Recommendations: {len(recommendations)}')
for i, rec in enumerate(recommendations[:5], 1):  # Show first 5
    priority = rec.get('priority', 'MEDIUM')
    text = rec.get('recommendation', rec.get('action', 'N/A'))
    print(f'   {i}. [{priority}] {text[:100]}...' if len(text) > 100 else f'   {i}. [{priority}] {text}')

print('\n' + '='*80)
print('✅ Analysis Complete!')
print('='*80)

