#!/usr/bin/env python
"""
Run a fresh analysis with enhanced fraud detection
Run: docker exec django-backend-dev python test_new_analysis_with_fraud.py
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.models import FinancialDataUpload, ProcessedFinancialData, TazamaAnalysisRequest, TazamaMLModel
from Tazama.core.TazamaCore import TazamaCore
from datetime import date

print("=" * 80)
print("🔄 RUNNING NEW ANALYSIS WITH ENHANCED FRAUD DETECTION")
print("=" * 80)

# Get latest upload
latest_upload = FinancialDataUpload.objects.order_by('-created_at').first()
print(f"\n📁 Using upload: {latest_upload.file_name}")

# Get processed data
processed = ProcessedFinancialData.objects.filter(upload=latest_upload).order_by('-period_date').first()

# Prepare financial data
financial_data = {
    'totalRevenue': float(processed.total_revenue),
    'costOfRevenue': float(processed.cost_of_revenue),
    'grossProfit': float(processed.gross_profit),
    'totalOperatingExpenses': float(processed.total_operating_expenses),
    'operatingIncome': float(processed.operating_income),
    'netIncome': float(processed.net_income),
    'incomeTaxExpense': float(processed.additional_features.get('income_tax_expense', 0)),
    'interestExpense': float(processed.additional_features.get('interest_expense', 0))
}

print("\n📊 Financial Data:")
for key, value in financial_data.items():
    print(f"   {key}: KES {value:,.2f}")

# Initialize Tazama Core
core = TazamaCore(model_type='ensemble')

# Run analysis
print("\n🔍 Running Analysis...")
result = core.analyze(financial_data)

# Extract key results
truth_report = result.get('truth_report', {})
risk_assessment = truth_report.get('risk_assessment', {})
fraud_flags = truth_report.get('fraud_red_flags', [])
recommendations = truth_report.get('brutally_honest_recommendations', [])

print("\n" + "=" * 80)
print("📋 FRAUD DETECTION RESULTS")
print("=" * 80)
print(f"Fraud Score: {risk_assessment.get('fraud_score', 'N/A')}/100")
print(f"Fraud Risk Level: {risk_assessment.get('fraud_risk', 'N/A')}")
print(f"Overall Risk: {risk_assessment.get('overall_risk', 'N/A')}")

print(f"\n🚨 Fraud Red Flags: {len(fraud_flags)}")
for i, flag in enumerate(fraud_flags[:10], 1):
    print(f"   {i}. {flag}")

print(f"\n💡 Recommendations: {len(recommendations)}")
for i, rec in enumerate(recommendations[:5], 1):
    priority = rec.get('priority', 'MEDIUM')
    text = rec.get('recommendation', rec.get('action', 'N/A'))
    category = rec.get('category', 'general')
    print(f"   {i}. [{priority}] ({category}) {text[:80]}...")

# Save as new analysis
print("\n💾 Saving Analysis...")
model = TazamaMLModel.objects.filter(is_active=True, model_type='ensemble').first()

if model:
    analysis = TazamaAnalysisRequest.objects.create(
        corporate=latest_upload.corporate,
        request_type='single_prediction',
        input_data=financial_data,
        model_used=model,
        status='completed',
        predictions=result.get('predictions', {}),
        truth_report=truth_report,
        metadata={
            'upload_id': str(latest_upload.id),
            'processed_data_id': str(processed.id),
            'analysis_date': str(date.today()),
            'fraud_detection_version': '2.0'
        }
    )
    print(f"✅ Analysis saved with ID: {analysis.id}")
    print(f"   Fraud Score in DB: {analysis.truth_report.get('risk_assessment', {}).get('fraud_score', 'N/A')}")
    print(f"   Frontend URL: /Tazama/analysis?upload_id={latest_upload.id}")
else:
    print("⚠️ No active ensemble model found")

print("\n" + "=" * 80)
print("✅ ANALYSIS COMPLETE!")
print("=" * 80)
print(f"\nNext Steps:")
print(f"1. Refresh your frontend (Ctrl+Shift+R)")
print(f"2. Navigate to: /Tazama/analysis?upload_id={latest_upload.id}")
print(f"3. You should see the fraud score: {risk_assessment.get('fraud_score', 'N/A')}/100")
print("=" * 80)

