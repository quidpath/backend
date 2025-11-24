#!/usr/bin/env python
"""
Generate a test JSON response matching what the frontend expects
Run: docker exec django-backend-dev python test_frontend_data.py > test_response.json
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.models import TazamaAnalysisRequest
from django.core.serializers.json import DjangoJSONEncoder

# Get the latest analysis
latest = TazamaAnalysisRequest.objects.order_by('-created_at').first()

if not latest:
    print(json.dumps({"error": "No analysis found"}, indent=2))
    exit(1)

# Build response matching frontend expectations
response = {
    "code": 200,
    "message": "Analysis successful",
    "data": {
        "analysis_id": str(latest.id),
        "id": str(latest.id),
        "status": latest.status,
        "request_type": latest.request_type,
        "predictions": latest.predictions,
        "input_data": latest.input_data,
        "recommendations": latest.recommendations,
        "risk_assessment": latest.risk_assessment,
        "confidence_scores": latest.confidence_scores,
        "truth_report": latest.truth_report,  # ✅ This is the key field
        "processing_time": latest.processing_time_seconds,
        "processing_time_seconds": latest.processing_time_seconds,
        "created_at": latest.created_at.isoformat(),
        "model_used": {
            "id": str(latest.model_used.id) if latest.model_used else "",
            "name": latest.model_used.name if latest.model_used else "Unknown",
            "type": latest.model_used.model_type if latest.model_used else "traditional",
            "version": latest.model_used.version if latest.model_used else "1.0"
        }
    }
}

print("=" * 80)
print("🎯 TEST DATA FOR FRONTEND")
print("=" * 80)
print(f"\n✅ Analysis ID: {latest.id}")
print(f"✅ Created: {latest.created_at}")
print(f"✅ Status: {latest.status}")

if latest.truth_report:
    print(f"\n📊 Truth Report Status:")
    print(f"   Keys: {list(latest.truth_report.keys())}")
    recs = latest.truth_report.get('brutally_honest_recommendations', [])
    print(f"   Recommendations: {len(recs)}")
    for i, rec in enumerate(recs, 1):
        print(f"      {i}. [{rec.get('priority')}] {rec.get('category')} - {rec.get('timeline')}")
    
    flags = latest.truth_report.get('fraud_red_flags', [])
    print(f"   Fraud Flags: {len(flags)}")
    
    risk = latest.truth_report.get('risk_assessment', {})
    print(f"   Overall Risk: {risk.get('overall_risk')}")

print("\n" + "=" * 80)
print("📋 JSON RESPONSE (copy this for frontend testing)")
print("=" * 80)
print(json.dumps(response, indent=2, cls=DjangoJSONEncoder))

