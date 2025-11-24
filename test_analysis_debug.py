#!/usr/bin/env python
"""
Quick test script to debug the analysis issue
Run: docker exec django-backend-dev python test_analysis_debug.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.models import ProcessedFinancialData, TazamaAnalysisRequest
from Tazama.Services.TazamaService import TazamaAnalysisService

# Get the latest processed data
latest = ProcessedFinancialData.objects.order_by('-created_at').first()

if not latest:
    print("❌ No ProcessedFinancialData found")
    exit(1)

print(f"✅ Found ProcessedFinancialData: ID={latest.id}")
print(f"   Revenue: {latest.total_revenue:,.0f}")
print(f"   COGS: {latest.cost_of_revenue:,.0f}")
print(f"   OPEX: {latest.total_operating_expenses:,.0f}")
print(f"   Net Income: {latest.net_income:,.0f}")

# Build financial_data dict (same as views.py)
financial_data = {
    'totalRevenue': float(latest.total_revenue or 0),
    'costOfRevenue': float(latest.cost_of_revenue or 0),
    'grossProfit': float(latest.gross_profit or 0),
    'totalOperatingExpenses': float(latest.total_operating_expenses or 0),
    'operatingIncome': float(latest.operating_income or 0),
    'netIncome': float(latest.net_income or 0),
}

print(f"\n📊 Financial Data Dict:")
for key, value in financial_data.items():
    print(f"   {key}: {value:,.0f}")

# Calculate ratios
total_revenue = financial_data['totalRevenue']
if total_revenue > 0:
    financial_data['profit_margin'] = financial_data['netIncome'] / total_revenue
    financial_data['operating_margin'] = financial_data['operatingIncome'] / total_revenue
    financial_data['cost_revenue_ratio'] = financial_data['costOfRevenue'] / total_revenue
    financial_data['expense_ratio'] = financial_data['totalOperatingExpenses'] / total_revenue
    financial_data['gross_margin'] = financial_data['grossProfit'] / total_revenue

print(f"\n📊 Calculated Ratios:")
print(f"   profit_margin: {financial_data.get('profit_margin', 0):.4f}")
print(f"   expense_ratio: {financial_data.get('expense_ratio', 0):.4f}")

# Try to analyze
print(f"\n🔍 Attempting analysis...")
try:
    from Tazama.core.TazamaCore import EnhancedFinancialOptimizer
    
    # Get model
    from Tazama.Services.TazamaService import TazamaModelService
    model_service = TazamaModelService()
    active_model = model_service.get_active_model('traditional')
    
    if not active_model:
        print("❌ No active model found")
        exit(1)
    
    print(f"✅ Found active model: {active_model.name}")
    
    # Load model
    model = model_service.load_model(active_model.id)
    if not model:
        print("❌ Failed to load model")
        exit(1)
    
    print(f"✅ Model loaded successfully")
    
    # Create optimizer
    optimizer = EnhancedFinancialOptimizer(
        models=model,
        feature_columns=active_model.feature_columns,
        target_columns=active_model.target_columns
    )
    
    print(f"✅ Optimizer created")
    print(f"   Feature columns: {active_model.feature_columns}")
    print(f"   Target columns: {active_model.target_columns}")
    
    # Try analysis
    print(f"\n🚀 Running analyze_income_statement...")
    result = optimizer.analyze_income_statement(financial_data)
    
    print(f"\n✅ Analysis completed!")
    print(f"   Keys: {list(result.keys())}")
    if 'predictions' in result:
        print(f"   Predictions: {result['predictions']}")
    if 'truth_report' in result:
        print(f"   Truth report keys: {list(result['truth_report'].keys())}")
        if 'brutally_honest_recommendations' in result['truth_report']:
            print(f"   Recommendations count: {len(result['truth_report']['brutally_honest_recommendations'])}")
    
except Exception as e:
    print(f"❌ Analysis failed: {e}")
    import traceback
    traceback.print_exc()


