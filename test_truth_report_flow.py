#!/usr/bin/env python
"""
Test script to verify truth report generation end-to-end
Run: docker exec django-backend-dev python test_truth_report_flow.py
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.models import ProcessedFinancialData, TazamaAnalysisRequest
from Tazama.Services.EnhancedFinancialDataService import EnhancedFinancialDataService
from Tazama.core.TazamaCore import EnhancedFinancialOptimizer
from Tazama.Services.TazamaService import TazamaModelService

print("=" * 80)
print("🧪 TRUTH REPORT GENERATION TEST")
print("=" * 80)

# Get the latest processed data
latest = ProcessedFinancialData.objects.order_by('-created_at').first()

if not latest:
    print("❌ No ProcessedFinancialData found")
    exit(1)

print(f"\n✅ Found ProcessedFinancialData: ID={latest.id}")
print(f"   Revenue: {latest.total_revenue:,.0f}")
print(f"   COGS: {latest.cost_of_revenue:,.0f}")
print(f"   OPEX: {latest.total_operating_expenses:,.0f}")
print(f"   Net Income: {latest.net_income:,.0f}")

# Build financial_data dict
financial_data = {
    'totalRevenue': float(latest.total_revenue or 0),
    'costOfRevenue': float(latest.cost_of_revenue or 0),
    'grossProfit': float(latest.gross_profit or 0),
    'totalOperatingExpenses': float(latest.total_operating_expenses or 0),
    'operatingIncome': float(latest.operating_income or 0),
    'netIncome': float(latest.net_income or 0),
}

print(f"\n📊 Testing EnhancedFinancialDataService._generate_truth_report()...")
service = EnhancedFinancialDataService()
truth_report = service._generate_truth_report(financial_data, {})

print(f"\n✅ Truth Report Generated!")
print(f"   Keys: {list(truth_report.keys())}")
print(f"   Recommendations count: {len(truth_report.get('brutally_honest_recommendations', []))}")
print(f"   Fraud flags count: {len(truth_report.get('fraud_red_flags', []))}")
print(f"   Overall risk: {truth_report.get('risk_assessment', {}).get('overall_risk', 'UNKNOWN')}")

if truth_report.get('brutally_honest_recommendations'):
    print(f"\n📋 Recommendations:")
    for i, rec in enumerate(truth_report['brutally_honest_recommendations'][:3], 1):
        print(f"   {i}. [{rec.get('priority', 'UNKNOWN')}] {rec.get('recommendation', 'N/A')[:100]}...")
else:
    print(f"\n❌ ERROR: No recommendations generated!")
    print(f"   Financial data: {json.dumps(financial_data, indent=2, default=str)}")

# Test with actual model analysis
print(f"\n📊 Testing full analysis flow with EnhancedFinancialOptimizer...")
try:
    model_service = TazamaModelService()
    active_model = model_service.get_active_model('traditional')
    
    if not active_model:
        print("⚠️ No active model found - skipping model analysis test")
    else:
        print(f"✅ Found active model: {active_model.name}")
        model = model_service.load_model(active_model.id)
        
        if model:
            optimizer = EnhancedFinancialOptimizer(
                models=model,
                feature_columns=active_model.feature_columns,
                target_columns=active_model.target_columns
            )
            
            # Add ratios
            total_revenue = financial_data['totalRevenue']
            if total_revenue > 0:
                financial_data['profit_margin'] = financial_data['netIncome'] / total_revenue
                financial_data['operating_margin'] = financial_data['operatingIncome'] / total_revenue
                financial_data['cost_revenue_ratio'] = financial_data['costOfRevenue'] / total_revenue
                financial_data['expense_ratio'] = financial_data['totalOperatingExpenses'] / total_revenue
                financial_data['gross_margin'] = financial_data['grossProfit'] / total_revenue
            
            result = optimizer.analyze_income_statement(financial_data)
            
            print(f"\n✅ Full analysis completed!")
            print(f"   Result keys: {list(result.keys())}")
            
            if 'truth_report' in result:
                tr = result['truth_report']
                print(f"   Truth report in result: YES")
                print(f"   Recommendations count: {len(tr.get('brutally_honest_recommendations', []))}")
                print(f"   Overall risk: {tr.get('risk_assessment', {}).get('overall_risk', 'UNKNOWN')}")
            else:
                print(f"   ❌ Truth report NOT in result!")
except Exception as e:
    print(f"❌ Error during model analysis: {e}")
    import traceback
    traceback.print_exc()

# Check database for existing analyses
print(f"\n📊 Checking recent TazamaAnalysisRequest records...")
recent_analyses = TazamaAnalysisRequest.objects.filter(status='completed').order_by('-created_at')[:5]

if recent_analyses:
    print(f"✅ Found {recent_analyses.count()} completed analyses")
    for analysis in recent_analyses:
        has_truth = bool(analysis.truth_report)
        rec_count = len(analysis.truth_report.get('brutally_honest_recommendations', [])) if has_truth else 0
        risk = analysis.truth_report.get('risk_assessment', {}).get('overall_risk', 'UNKNOWN') if has_truth else 'N/A'
        
        print(f"   Analysis {str(analysis.id)[:8]}... - Truth Report: {has_truth}, Recs: {rec_count}, Risk: {risk}")
else:
    print(f"⚠️ No completed analyses found")

print("\n" + "=" * 80)
print("🎯 TEST COMPLETE")
print("=" * 80)

