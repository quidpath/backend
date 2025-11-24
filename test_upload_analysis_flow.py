#!/usr/bin/env python
"""
Test script to verify upload → analysis flow
Run: docker exec django-backend-dev python test_upload_analysis_flow.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.models import FinancialDataUpload, ProcessedFinancialData, TazamaAnalysisRequest
import json

print("=" * 80)
print("🧪 UPLOAD → ANALYSIS FLOW TEST")
print("=" * 80)

# Get the latest upload
latest_upload = FinancialDataUpload.objects.order_by('-created_at').first()
if not latest_upload:
    print("❌ No uploads found")
    exit(1)

print(f"\n✅ Latest Upload:")
print(f"   ID: {latest_upload.id}")
print(f"   Filename: {latest_upload.file_name}")
print(f"   Upload Date: {latest_upload.created_at}")
print(f"   Processing Status: {latest_upload.processing_status}")

# Find associated processed data
processed_data = ProcessedFinancialData.objects.filter(upload=latest_upload).order_by('-created_at')
print(f"\n📊 Associated Processed Data: {processed_data.count()} record(s)")

if processed_data.exists():
    latest_processed = processed_data.first()
    print(f"\n   Latest Processed Record:")
    print(f"   ID: {latest_processed.id}")
    print(f"   Total Revenue: {latest_processed.total_revenue:,}")
    print(f"   Cost of Revenue: {latest_processed.cost_of_revenue:,}")
    print(f"   Gross Profit: {latest_processed.gross_profit:,}")
    print(f"   Operating Expenses: {latest_processed.total_operating_expenses:,}")
    print(f"   Operating Income: {latest_processed.operating_income:,}")
    print(f"   Net Income: {latest_processed.net_income:,}")
    print(f"   Period Date: {latest_processed.period_date}")

# Find recent analyses (there's no direct upload foreign key, so we get recent ones)
analyses = TazamaAnalysisRequest.objects.order_by('-created_at')[:5]
print(f"\n🔍 Recent Analyses: {len(analyses)} record(s)")

if analyses:
    latest_analysis = analyses[0]
    print(f"\n   Latest Analysis:")
    print(f"   ID: {latest_analysis.id}")
    print(f"   Created: {latest_analysis.created_at}")
    print(f"   Request Type: {latest_analysis.request_type}")
    print(f"   Status: {latest_analysis.status}")
    
    # Check input_data
    if latest_analysis.input_data:
        print(f"\n   ✅ Input Data Present:")
        print(f"      Total Revenue: {latest_analysis.input_data.get('totalRevenue', 'N/A')}")
        print(f"      Net Income: {latest_analysis.input_data.get('netIncome', 'N/A')}")
        print(f"      Operating Expenses: {latest_analysis.input_data.get('totalOperatingExpenses', 'N/A')}")
    else:
        print(f"   ❌ NO INPUT DATA")
    
    # Check truth_report
    if latest_analysis.truth_report:
        print(f"\n   ✅ Truth Report Present:")
        print(f"      Keys: {list(latest_analysis.truth_report.keys())}")
        recs = latest_analysis.truth_report.get('brutally_honest_recommendations', [])
        print(f"      Recommendations: {len(recs)}")
        if recs:
            print(f"\n      First Recommendation:")
            first_rec = recs[0]
            print(f"         Priority: {first_rec.get('priority')}")
            print(f"         Category: {first_rec.get('category')}")
            print(f"         Timeline: {first_rec.get('timeline')}")
            print(f"         Text: {first_rec.get('recommendation', '')[:100]}...")
        
        fraud_flags = latest_analysis.truth_report.get('fraud_red_flags', [])
        print(f"      Fraud Flags: {len(fraud_flags)}")
        if fraud_flags:
            print(f"         {fraud_flags[0][:100]}...")
        
        risk = latest_analysis.truth_report.get('risk_assessment', {})
        print(f"      Overall Risk: {risk.get('overall_risk', 'N/A')}")
    else:
        print(f"   ❌ NO TRUTH REPORT")
else:
    print("\n   ⚠️ No analyses found for this upload")
    print("   This means the analysis endpoint was not called, or failed")

print("\n" + "=" * 80)
print("🎯 SUMMARY")
print("=" * 80)
print(f"Upload ID to use in frontend: {latest_upload.id}")
print(f"Expected flow: Upload File → Process → Call /analyze-financial-data/ with upload_id={latest_upload.id}")

if processed_data.exists() and not analyses:
    print("\n⚠️ WARNING: Processed data exists but NO analysis found!")
    print("   Action: Call /analyze-financial-data/ endpoint with this upload_id")
elif analyses:
    if latest_analysis.truth_report:
        print("\n✅ SUCCESS: Full pipeline working correctly!")
    else:
        print("\n⚠️ WARNING: Analysis exists but truth_report is missing!")
        print("   Check backend analyze endpoint and truth_report generation")

