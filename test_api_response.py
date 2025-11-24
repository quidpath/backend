#!/usr/bin/env python
"""Check what the API returns"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quidpath_backend.settings.dev')
django.setup()

from Tazama.models import TazamaAnalysisRequest

# Get latest analysis
latest = TazamaAnalysisRequest.objects.order_by('-created_at').first()

# Simulate what the API returns
response_data = {
    "id": str(latest.id),
    "status": latest.status,
    "predictions": latest.predictions,
    "recommendations": latest.recommendations,
    "risk_assessment": latest.risk_assessment,
    "confidence_scores": latest.confidence_scores,
    "truth_report": latest.truth_report,  # ← THIS IS THE KEY!
    "processing_time": latest.processing_time_seconds,
    "model_used": {
        "id": str(latest.model_used.id),
        "name": latest.model_used.name,
        "type": latest.model_used.model_type,
        "version": latest.model_used.version
    },
    "input_data": latest.input_data
}

print("📤 API Response Structure:")
print(json.dumps({
    "id": "...",
    "status": response_data["status"],
    "has_truth_report": bool(response_data.get("truth_report")),
    "truth_report_keys": list(response_data.get("truth_report", {}).keys()) if response_data.get("truth_report") else [],
    "truth_report_recommendations_count": len(response_data.get("truth_report", {}).get("brutally_honest_recommendations", [])),
    "predictions": response_data["predictions"],
    "has_input_data": bool(response_data.get("input_data")),
}, indent=2))

print(f"\n✅ Truth Report IS being returned in API response!")
print(f"   Recommendations: {len(response_data['truth_report']['brutally_honest_recommendations'])}")

