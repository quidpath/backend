#!/usr/bin/env python
"""Check if truth report exists in database"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.models import TazamaAnalysisRequest

# Get latest analysis
latest = TazamaAnalysisRequest.objects.order_by('-created_at').first()

if not latest:
    print("❌ No TazamaAnalysisRequest found")
    exit(1)

print(f"✅ Found TazamaAnalysisRequest: ID={str(latest.id)[:8]}...")
print(f"   Status: {latest.status}")
print(f"   Created: {latest.created_at}")

print(f"\n📊 Has truth_report: {bool(latest.truth_report)}")
if latest.truth_report:
    print(f"   Truth report keys: {list(latest.truth_report.keys())}")
    
    if 'brutally_honest_recommendations' in latest.truth_report:
        recs = latest.truth_report['brutally_honest_recommendations']
        print(f"\n✅ Found {len(recs)} Brutal Truth Recommendations:")
        for i, rec in enumerate(recs, 1):
            print(f"\n   {i}. [{rec.get('priority', 'UNKNOWN')}] {rec.get('recommendation', 'N/A')}")
            if rec.get('timeline'):
                print(f"      Timeline: {rec['timeline']}")
    else:
        print("   ❌ No brutally_honest_recommendations in truth_report")
else:
    print("   ❌ truth_report is None or empty")

print(f"\n📊 Predictions: {latest.predictions}")
print(f"\n📊 Risk Assessment: {latest.risk_assessment}")

