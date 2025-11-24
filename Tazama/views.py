# views.py - Django views for Tazama integration
import json
import os
import requests

import numpy as np
import pandas as pd
from decimal import Decimal
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.Logbase import TransactionLogBase
from .Services.TazamaService import FinancialDataService, TazamaAnalysisService, DashboardService, ModelTrainingService
from .Services.EnhancedFinancialDataService import EnhancedFinancialDataService, logger
from .Services.CompleteAnalysisPipeline import CompleteAnalysisPipeline
from .core.TazamaCore import FinancialDataProcessor
from .core.report_generator import TazamaReportGenerator

from .models import (
    FinancialDataUpload, ProcessedFinancialData, TazamaAnalysisRequest,
    FinancialReport, TazamaMLModel, ModelTrainingJob, DashboardMetric, ModelPredictionLog
)

# Currency conversion helper
def convert_currency(amount: float, from_currency: str = 'KES', to_currency: str = 'USD') -> dict:
    """
    Convert currency using exchangerate-api.io (free tier)
    Returns conversion rate and converted amount
    """
    try:
        if from_currency == to_currency:
            return {'rate': 1.0, 'converted_amount': amount, 'from': from_currency, 'to': to_currency}
        
        # Using exchangerate-api.io free tier (no API key required for basic usage)
        url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rates', {})
            rate = rates.get(to_currency, 1.0)
            converted = amount * rate
            return {
                'rate': round(rate, 6),
                'converted_amount': round(converted, 2),
                'from': from_currency,
                'to': to_currency,
                'timestamp': data.get('date')
            }
        else:
            # Fallback to approximate conversion if API fails
            fallback_rates = {
                'USD': 1.0,
                'KES': 0.0067,  # ~1 KES = 0.0067 USD
                'EUR': 1.08,
                'GBP': 1.27,
                'JPY': 0.0068,
                'CAD': 0.74,
                'AUD': 0.67,
                'CHF': 1.11,
                'CNY': 0.14,
                'INR': 0.012
            }
            if from_currency in fallback_rates and to_currency in fallback_rates:
                rate = fallback_rates[to_currency] / fallback_rates[from_currency]
                return {
                    'rate': round(rate, 6),
                    'converted_amount': round(amount * rate, 2),
                    'from': from_currency,
                    'to': to_currency,
                    'warning': 'Using fallback rates - API unavailable'
                }
            return {'rate': 1.0, 'converted_amount': amount, 'error': 'Currency conversion failed'}
    except Exception as e:
        return {'rate': 1.0, 'converted_amount': amount, 'error': str(e)}

def sanitize_report_data_for_json(data):
    """
    Sanitize report data to ensure all values are JSON-serializable
    This is especially important for frontend consumption
    """
    if isinstance(data, dict):
        return {k: sanitize_report_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_report_data_for_json(item) for item in data]
    elif hasattr(data, '__float__'):  # Decimal, numpy types
        return float(data)
    elif hasattr(data, '__int__'):
        return int(data)
    elif isinstance(data, (str, bool, type(None))):
        return data
    else:
        return str(data)

@csrf_exempt
def upload_financial_data(request):
    """
    Upload CSV or Excel financial data for processing and model training

    Expected data:
    - file: CSV, XLS, or XLSX file with financial data
    - upload_type: 'income_statement', 'balance_sheet', or 'cash_flow'
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Handle file upload
        if 'file' not in request.FILES:
            return ResponseProvider(message="No file provided", code=400).bad_request()

        uploaded_file = request.FILES['file']
        upload_type = data.get('upload_type', 'income_statement')

        # Validate file type
        if not uploaded_file.name.endswith(('.csv', '.xlsx', '.xls')):
            return ResponseProvider(
                message="Invalid file format. Only CSV, XLS, and XLSX files are supported",
                code=400
            ).bad_request()

        # Create upload record
        upload_record = FinancialDataUpload.objects.create(
            corporate_id=corporate_id,
            uploaded_by_id=user_id,
            file_name=uploaded_file.name,
            file_path=uploaded_file,
            upload_type=upload_type,
            file_size=uploaded_file.size
        )

        # Process the file using complete analysis pipeline
        complete_pipeline = CompleteAnalysisPipeline()
        pipeline_result = complete_pipeline.process_complete_workflow(upload_record)
        
        if pipeline_result['success']:
            success = True
            message = pipeline_result['message']
        else:
            success = False
            message = pipeline_result['error']

        if success:
            TransactionLogBase.log(
                transaction_type="FINANCIAL_DATA_UPLOADED",
                user=user,
                message=f"Financial data uploaded and processed successfully: {message}",
                state_name="Success",
                extra={
                    "upload_id": upload_record.id,
                    "file_name": uploaded_file.name,
                    "rows_processed": upload_record.rows_processed
                },
                request=request,
            )

            return ResponseProvider(
                data={
                    "upload_id": upload_record.id,
                    "file_name": uploaded_file.name,
                    "rows_processed": upload_record.rows_processed,
                    "status": upload_record.processing_status,
                    "pipeline_results": pipeline_result.get('results', {}),
                    "analysis_id": pipeline_result.get('analysis_id'),
                    "report_id": pipeline_result.get('report_id'),
                    "pipeline_status": pipeline_result.get('pipeline_status', {})
                },
                message=message,
                code=200
            ).success()
        else:
            TransactionLogBase.log(
                transaction_type="FINANCIAL_DATA_UPLOAD_FAILED",
                user=user,
                message=message,
                state_name="Failed",
                request=request,
            )
            return ResponseProvider(
                message=f"Processing failed: {message}",
                code=400
            ).bad_request()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="FINANCIAL_DATA_UPLOAD_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"An error occurred while uploading financial data: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def analyze_financial_data(request):
    """
    Analyze financial data using Tazama AI models

    Expected data:
    - financial_data: Dictionary with financial metrics or upload_id for processed data
    - analysis_type: 'single_prediction', 'batch_analysis', or 'comparative_analysis'
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_user_dict = corporate_users[0]

        # Convert dictionary to actual model instances
        from OrgAuth.models import CorporateUser, Corporate

        corporate_user = CorporateUser.objects.get(
            customuser_ptr_id=corporate_user_dict['customuser_ptr_id']
        )
        corporate = corporate_user.corporate

        strict_service = EnhancedFinancialDataService()

        # Get financial data
        financial_data = data.get('financial_data')
        upload_id = data.get('upload_id')
        analysis_type = data.get('analysis_type', 'single_prediction')

        if not financial_data and not upload_id:
            return ResponseProvider(message="Either financial_data or upload_id must be provided",
                                    code=400).bad_request()

        # If upload_id is provided, select a valid processed row (prefer non-zero revenue)
        if upload_id:
            try:
                upload_record = FinancialDataUpload.objects.get(id=upload_id, corporate_id=corporate.id)
                # ✅ FIXED: Order by created_at first to get the most recent upload
                # ✅ CRITICAL: Always get the LATEST processed data, even if an analysis already exists
                qs = ProcessedFinancialData.objects.filter(upload=upload_record).order_by('-created_at', '-period_date')
                latest_data = qs.exclude(total_revenue=0).first() or \
                              qs.exclude(
                                  total_revenue=0,
                                  cost_of_revenue=0,
                                  gross_profit=0,
                                  total_operating_expenses=0,
                                  operating_income=0,
                                  net_income=0
                              ).first() or \
                              qs.first()

                if not latest_data:
                    return ResponseProvider(message="No processed data found for this upload", code=400).bad_request()
                
                # ✅ LOGGING: Show which record we're using
                logger.info(f"📊 Using ProcessedFinancialData record: ID={latest_data.id}, Created={latest_data.created_at}")
                logger.info(f"   Revenue: {latest_data.total_revenue:,.2f}, OPEX: {latest_data.total_operating_expenses:,.2f}, NI: {latest_data.net_income:,.2f}")

                # Build robust financial snapshot with derivations if needed
                tr = float(latest_data.total_revenue or 0)
                cr = float(latest_data.cost_of_revenue or 0)
                gp = float(latest_data.gross_profit or 0)
                opex = float(latest_data.total_operating_expenses or 0)
                oi = float(latest_data.operating_income or 0)
                ni = float(latest_data.net_income or 0)
                rd = float(latest_data.research_development or 0)

                # ✅ CRITICAL: Log extracted values for debugging
                logger.info(f"📊 Extracted from database (Record ID={latest_data.id}, Created={latest_data.created_at}):")
                logger.info(f"   Revenue: {tr:,.0f}, COGS: {cr:,.0f}, GP: {gp:,.0f}, OPEX: {opex:,.0f}, OI: {oi:,.0f}, NI: {ni:,.0f}")
                if opex == 0.0:
                    logger.warning(f"⚠️ Operating Expenses is 0.0 in database record ID={latest_data.id}")
                    logger.warning(f"   This may be an old record. Check if a newer record exists with correct OPEX.")
                
                # ✅ STRICT MODE: Use ONLY the extracted values - NO modifications, NO calculations, NO corrections
                # Log warnings for inconsistencies but DO NOT fix them
                if tr > 0 and ni > 0 and tr < ni:
                    logger.warning(f"⚠️ STRICT MODE: Revenue ({tr:,.0f}) < Net Income ({ni:,.0f}) - using values as-is (no correction)")
                
                if oi > gp and gp > 0:
                    logger.warning(f"⚠️ STRICT MODE: Operating Income ({oi:,.0f}) > Gross Profit ({gp:,.0f}) - mathematically impossible, but using as-is")
                
                # ✅ STRICT MODE: Use exact values from database - no calculations, no tax deductions, no corrections
                financial_data = {
                    'totalRevenue': tr,
                    'costOfRevenue': cr,
                    'grossProfit': gp,
                    'totalOperatingExpenses': opex,
                    'operatingIncome': oi,
                    'netIncome': ni,  # ✅ Use exact value - no tax deductions
                    'researchDevelopment': rd,
                    'incomeTaxExpense': 0,  # Only include if explicitly in the statement
                }
                
                # ✅ FINAL VALIDATION: Log final financial data being sent to model (STRICT MODE - no modifications)
                logger.info(f"📊 STRICT MODE - Final financial_data for analysis (exact values from database):")
                logger.info(f"   Revenue: {tr:,.0f}, COGS: {cr:,.0f}, GP: {gp:,.0f}, OPEX: {opex:,.0f}, OI: {oi:,.0f}, NI: {ni:,.0f}")
            except FinancialDataUpload.DoesNotExist:
                return ResponseProvider(message="Upload record not found", code=404).not_found()

        # ✅ CRITICAL FIX: Calculate ALL features that the model expects
        total_revenue = float(financial_data.get('totalRevenue', 0) or 0)
        cost_of_revenue = float(financial_data.get('costOfRevenue', 0) or 0)
        gross_profit = float(financial_data.get('grossProfit', 0) or 0)
        total_expenses = float(financial_data.get('totalOperatingExpenses', 0) or 0)
        operating_income = float(financial_data.get('operatingIncome', 0) or 0)
        net_income = float(financial_data.get('netIncome', 0) or 0)
        rd_expenses = float(financial_data.get('researchDevelopment', 0) or 0)

        # ✅ STRICT MODE: NO corrections, NO calculations - use values exactly as extracted
        # Log inconsistencies but DO NOT modify values
        if total_revenue > 0 and cost_of_revenue > 0:
            cost_ratio = cost_of_revenue / total_revenue
            expense_ratio = total_expenses / total_revenue if total_expenses > 0 else 0
            if cost_ratio < 0.15 and expense_ratio < 0.10 and total_expenses > 0:
                logger.warning(f"⚠️ STRICT MODE: Unusual ratios detected (cost: {cost_ratio:.2%}, expense: {expense_ratio:.2%}) - using values as-is (no correction)")

        if total_expenses == 0 and gross_profit > 0 and operating_income > 0:
            logger.warning(f"⚠️ STRICT MODE: Operating Expenses is 0 but GP ({gross_profit:,.0f}) and OI ({operating_income:,.0f}) exist - using 0 as-is (no calculation)")

        # ✅ CORRECT FORMULAS (verified):
        # Profit Margin = Net Income / Total Revenue
        # Operating Margin = Operating Income / Total Revenue  
        # Cost Ratio = Cost of Revenue / Total Revenue
        # Expense Ratio = Operating Expenses / Total Revenue
        if total_revenue > 0:
            financial_data['profit_margin'] = (net_income / total_revenue)
            financial_data['operating_margin'] = (operating_income / total_revenue)
            financial_data['cost_revenue_ratio'] = (cost_of_revenue / total_revenue)
            financial_data['expense_ratio'] = (total_expenses / total_revenue)
            financial_data['gross_margin'] = (gross_profit / total_revenue)
            financial_data['rd_intensity'] = (rd_expenses / total_revenue)
            financial_data['revenue_per_expense'] = (total_revenue / max(total_expenses, 1))
            
            # ✅ Validate expense ratio is not zero when expenses exist
            if financial_data['expense_ratio'] == 0 and total_expenses > 0:
                financial_data['expense_ratio'] = total_expenses / total_revenue
                logger.warning(f"⚠️ Recalculated expense_ratio: {financial_data['expense_ratio']}")
        else:
            financial_data['profit_margin'] = 0
            financial_data['operating_margin'] = 0
            financial_data['cost_revenue_ratio'] = 0
            financial_data['expense_ratio'] = 0
            financial_data['gross_margin'] = 0
            financial_data['rd_intensity'] = 0
            financial_data['revenue_per_expense'] = 0

        # Clip values to reasonable ranges (same as in training)
        financial_data['profit_margin'] = np.clip(financial_data['profit_margin'], -1, 1)
        financial_data['gross_margin'] = np.clip(financial_data['gross_margin'], -1, 1)
        financial_data['operating_margin'] = np.clip(financial_data['operating_margin'], -1, 1)
        financial_data['cost_revenue_ratio'] = np.clip(financial_data['cost_revenue_ratio'], 0, 2)
        financial_data['expense_ratio'] = np.clip(financial_data['expense_ratio'], 0, 2)
        financial_data['rd_intensity'] = np.clip(financial_data['rd_intensity'], 0, 1)
        financial_data['revenue_per_expense'] = np.clip(financial_data['revenue_per_expense'], 0, 10)

        # Try model-backed analysis; if no model available, use fallback (no 500)
        try:
            # Check for an active model first
            from .Services.TazamaService import TazamaModelService
            model_service = TazamaModelService()
            active_model = model_service.get_active_model('traditional') or model_service.get_active_model('lstm')

            if not active_model:
                # Fallback: compute simple ratios without creating a request
                predictions = {
                    'profit_margin': float(financial_data['profit_margin']),
                    'operating_margin': float(financial_data['operating_margin']),
                    'gross_margin': float(financial_data['gross_margin']),
                    'cost_revenue_ratio': float(financial_data['cost_revenue_ratio']),
                    'expense_ratio': float(financial_data['expense_ratio'])
                }
                risk_assessment = {
                    'overall_risk': 'LOW',
                    'profitability_risk': 'LOW',
                    'operational_risk': 'LOW',
                    'risk_factors': []
                }
                truth_report = strict_service._generate_truth_report(financial_data, predictions)
                logger.info(f"📤 Fallback mode - Generated truth report with {len(truth_report.get('brutally_honest_recommendations', []))} recommendations")
                return ResponseProvider(
                    data={
                        "analysis_id": None,
                        "input_data": financial_data,  # ✅ Include input_data
                        "predictions": predictions,
                        "recommendations": {},
                        "risk_assessment": risk_assessment,
                        "confidence_scores": { 'overall': 0.7 },
                        "truth_report": truth_report,  # ✅ Already included
                        "processing_time": 0.05,
                        "model_used": { 'id': None, 'name': 'Fallback', 'type': 'traditional', 'version': '1.0' }
                    },
                    message="Financial analysis (fallback) completed successfully",
                    code=200
                ).success()

            # ✅ STRICT MODE: Validate financial_data before creating analysis request
            if not financial_data:
                logger.error(f"❌ ERROR: financial_data is None or empty - cannot create analysis request")
                return ResponseProvider(message="Financial data is empty or invalid", code=400).bad_request()
            
            # Validate that we have at least revenue
            if not financial_data.get('totalRevenue', 0):
                logger.warning(f"⚠️ STRICT MODE: Total Revenue is 0 - proceeding with analysis using exact extracted values")
            
            # Proceed with model-backed analysis
            analysis_service = TazamaAnalysisService()
            request_obj = analysis_service.create_analysis_request(
                corporate=corporate,
                user=corporate_user,
                input_data=financial_data,  # ✅ STRICT MODE: Use exact extracted values
                request_type=analysis_type
            )

            # ✅ STRICT MODE: Ensure input_data is set with exact extracted values (no modifications)
            request_obj.input_data = financial_data.copy()
            request_obj.save()
            logger.info(f"✅ STRICT MODE: Created analysis request with exact extracted values (no modifications)")

            # Execute analysis
            success, message = analysis_service.run_analysis(request_obj.id)

            if success:
                request_obj.refresh_from_db()
                
                # ✅ CRITICAL: Ensure input_data is saved correctly with operating expenses
                # Refresh input_data to ensure it includes all fields
                if not request_obj.input_data or request_obj.input_data.get('totalOperatingExpenses', 0) == 0:
                    request_obj.input_data = financial_data
                    request_obj.save()
                    logger.info(f"✅ Updated analysis request input_data with correct operating expenses: {financial_data.get('totalOperatingExpenses', 0):,.0f}")

                TransactionLogBase.log(
                    transaction_type="FINANCIAL_ANALYSIS_COMPLETED",
                    user=user,
                    message="Financial analysis completed successfully",
                    state_name="Success",
                    extra={
                        "analysis_request_id": request_obj.id,
                        "analysis_type": analysis_type,
                        "predictions": request_obj.predictions
                    },
                    request=request,
                )

                # Get optimization analysis if available
                optimization_analysis = {}
                if hasattr(request_obj, 'optimization_analysis'):
                    optimization_analysis = request_obj.optimization_analysis

                # ✅ STRICT MODE: Use exact extracted financial_data - no calculations, no modifications
                # Ensure input_data is always set (use extracted values from database)
                response_input_data = financial_data.copy() if financial_data else {}
                
                # ✅ CRITICAL: Ensure input_data is set on the request object (prevents "Empty or None" error)
                if financial_data:
                    response_input_data = financial_data.copy()
                    # Update stored input_data to match extracted values (strict mode - no modifications)
                    if not request_obj.input_data or request_obj.input_data != financial_data:
                        request_obj.input_data = financial_data.copy()
                        request_obj.save()
                        logger.info(f"✅ STRICT MODE: Updated stored input_data with exact extracted values (no modifications)")
                else:
                    logger.error(f"❌ ERROR: financial_data is empty or None - cannot proceed with analysis")
                    return ResponseProvider(message="Financial data is empty or invalid", code=400).bad_request()
                
                # ✅ VALIDATION: Log what we're sending
                logger.info(f"📤 Sending analysis response with input_data:")
                logger.info(f"   Revenue: {response_input_data.get('totalRevenue', 0):,.2f}")
                logger.info(f"   OPEX: {response_input_data.get('totalOperatingExpenses', 0):,.2f}")
                logger.info(f"   Net Income: {response_input_data.get('netIncome', 0):,.2f}")
                logger.info(f"   Expense Ratio: {response_input_data.get('expense_ratio', 0):.4f} ({response_input_data.get('expense_ratio', 0) * 100:.2f}%)")
                
                # ✅ STRICT MODE: Log inconsistencies but DO NOT calculate or modify values
                if response_input_data.get('totalOperatingExpenses', 0) == 0 and response_input_data.get('totalRevenue', 0) > 0:
                    logger.warning(f"⚠️ STRICT MODE: Operating Expenses is 0 but Revenue exists - using 0 as-is (no calculation)")
                    logger.warning(f"   Revenue: {response_input_data.get('totalRevenue', 0):,.2f}")
                    logger.warning(f"   Operating Income: {response_input_data.get('operatingIncome', 0):,.2f}")
                    logger.warning(f"   Gross Profit: {response_input_data.get('grossProfit', 0):,.2f}")
                
                # ✅ CRITICAL FIX: ALWAYS use the truth_report that was saved to database
                truth_report = request_obj.truth_report or {}
                logger.info("="* 80)
                logger.info(f"📤 TRUTH REPORT CHECK FOR ANALYSIS ID: {request_obj.id}")
                logger.info(f"   Truth report exists: {bool(truth_report)}")
                logger.info(f"   Truth report keys: {list(truth_report.keys()) if truth_report else 'None'}")
                if truth_report.get('brutally_honest_recommendations'):
                    logger.info(f"   ✅ Recommendations count: {len(truth_report['brutally_honest_recommendations'])}")
                    logger.info(f"   ✅ First recommendation: {truth_report['brutally_honest_recommendations'][0] if truth_report['brutally_honest_recommendations'] else 'None'}")
                else:
                    logger.error(f"❌ CRITICAL: No recommendations in truth_report! Regenerating immediately...")
                    truth_report = strict_service._generate_truth_report(response_input_data, request_obj.predictions or {})
                    logger.info(f"   Regenerated truth_report has recommendations: {bool(truth_report.get('brutally_honest_recommendations'))}")
                    if truth_report.get('brutally_honest_recommendations'):
                        logger.info(f"   ✅ Regenerated {len(truth_report['brutally_honest_recommendations'])} recommendations")
                        # Save regenerated truth_report back to database
                        request_obj.truth_report = truth_report
                        request_obj.save()
                        logger.info(f"   ✅ Saved regenerated truth_report to database")
                
                logger.info(f"   Truth report fraud flags: {len(truth_report.get('fraud_red_flags', []))} flags")
                logger.info(f"   Truth report overall risk: {truth_report.get('risk_assessment', {}).get('overall_risk', 'UNKNOWN')}")
                logger.info("=" * 80)

                return ResponseProvider(
                    data={
                        "analysis_id": request_obj.id,
                        "input_data": response_input_data,  # ✅ ADD: Include input_data for frontend
                        "predictions": request_obj.predictions,
                        "recommendations": request_obj.recommendations,
                        "risk_assessment": request_obj.risk_assessment,
                        "confidence_scores": request_obj.confidence_scores,
                        "truth_report": truth_report,  # ✅ Now uses saved truth_report from database!
                        "optimization_analysis": optimization_analysis,
                        "processing_time": request_obj.processing_time_seconds,
                        "model_used": {
                            "id": request_obj.model_used.id,
                            "name": request_obj.model_used.name,
                            "type": request_obj.model_used.model_type,
                            "version": request_obj.model_used.version
                        }
                    },
                    message="Financial analysis completed successfully",
                    code=200
                ).success()

            return ResponseProvider(message=f"Analysis failed: {message}", code=500).exception()
        except Exception as e:
            # As a last resort, return fallback without raising
            logger.error(f"❌ Exception in analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            predictions = {
                'profit_margin': float(financial_data.get('profit_margin', 0)),
                'operating_margin': float(financial_data.get('operating_margin', 0)),
                'gross_margin': float(financial_data.get('gross_margin', 0)),
                'cost_revenue_ratio': float(financial_data.get('cost_revenue_ratio', 0)),
                'expense_ratio': float(financial_data.get('expense_ratio', 0))
            }
            # ✅ STRICT MODE: If analysis failed, mark as HIGH risk (something went wrong)
            risk_assessment = {
                'overall_risk': 'HIGH',
                'profitability_risk': 'HIGH',
                'operational_risk': 'HIGH',
                'risk_factors': ['Analysis failed - requires manual review', 'Unable to complete automated risk assessment']
            }
            # ✅ Generate truth report even in exception case
            try:
                truth_report = strict_service._generate_truth_report(financial_data, predictions)
                logger.info(f"📤 Exception fallback - Generated truth report with {len(truth_report.get('brutally_honest_recommendations', []))} recommendations")
            except:
                truth_report = {}
                logger.error(f"❌ Failed to generate truth report in exception fallback")
            
            return ResponseProvider(
                data={
                    "analysis_id": None,
                    "input_data": financial_data,  # ✅ Include input_data
                    "predictions": predictions,
                    "recommendations": {},
                    "risk_assessment": risk_assessment,
                    "confidence_scores": { 'overall': 0.6 },
                    "truth_report": truth_report,  # ✅ Include truth_report
                    "processing_time": 0.01,
                    "model_used": { 'id': None, 'name': 'Fallback', 'type': 'traditional', 'version': '1.0' }
                },
                message="Financial analysis (fallback) returned due to error",
                code=200
            ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="FINANCIAL_ANALYSIS_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred during financial analysis",
            code=500
        ).exception()


@csrf_exempt
def get_financial_dashboard(request):
    """
    Get dashboard data with statement-time-aligned projections

    Expected data (optional):
    - start_date: Start date for historical aggregates window
    - end_date: End date for historical aggregates window
    - statement_date: ISO date string to align projections to this statement timeline
    - upload_id: If provided, derive statement_date and financial snapshot from this upload
    - currency: Target currency code (default: KES, options: USD, EUR, GBP, etc.)
    """
    data, metadata = get_clean_data(request)

    # Get requested currency or default to KES
    requested_currency = data.get('currency', 'KES').upper()
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Parse window dates for aggregates (defaults to last 365 days)
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = date.today() - timedelta(days=365)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = date.today()

        # Determine statement-aligned context
        statement_date_str = data.get("statement_date") or data.get("reference_date")
        upload_id = data.get("upload_id")
        resolved_statement_date = None
        resolved_snapshot = None

        # Helper: build minimal financial_data dict from a ProcessedFinancialData row
        def build_financial_data_dict(pfd):
            if not pfd:
                return {}
            total_revenue = float(pfd.total_revenue or 0)
            cost_of_revenue = float(pfd.cost_of_revenue or 0)
            gross_profit = float(pfd.gross_profit or 0)
            total_operating_expenses = float(pfd.total_operating_expenses or 0)
            operating_income = float(pfd.operating_income or 0)
            net_income = float(pfd.net_income or 0)

            # Recompute derived fields if missing or clearly inconsistent
            if gross_profit == 0 and (total_revenue or cost_of_revenue):
                gross_profit = total_revenue - cost_of_revenue
            if operating_income == 0 and (gross_profit or total_operating_expenses):
                operating_income = gross_profit - total_operating_expenses
            # If taxes were tracked, they would be subtracted; otherwise keep provided net_income

            # ✅ CRITICAL: Always recalculate ratios from actual values (source of truth)
            # This ensures ratios are accurate even if stored values are incorrect
            calculated_ratios = {}
            if total_revenue and total_revenue > 0:
                calculated_ratios = {
                    "profit_margin": max(0.0, min(1.0, net_income / total_revenue)),
                    "operating_margin": max(0.0, min(1.0, operating_income / total_revenue)),
                    "gross_margin": max(0.0, min(1.0, gross_profit / total_revenue)),
                    "cost_revenue_ratio": max(0.0, min(2.0, cost_of_revenue / total_revenue)),
                    "expense_ratio": max(0.0, min(2.0, total_operating_expenses / total_revenue)),
                }
            else:
                calculated_ratios = {
                    "profit_margin": 0.0,
                    "operating_margin": 0.0,
                    "gross_margin": 0.0,
                    "cost_revenue_ratio": 0.0,
                    "expense_ratio": 0.0,
                }
            
            # ✅ Use calculated ratios (always accurate) instead of stored values
            snapshot = {
                "total_revenue": total_revenue,
                "cost_of_revenue": cost_of_revenue,
                "gross_profit": gross_profit,
                "total_operating_expenses": total_operating_expenses,
                "operating_income": operating_income,
                "net_income": net_income,
                "profit_margin": calculated_ratios["profit_margin"],
                "operating_margin": calculated_ratios["operating_margin"],
                "gross_margin": calculated_ratios["gross_margin"],
                "cost_revenue_ratio": calculated_ratios["cost_revenue_ratio"],
                "expense_ratio": calculated_ratios["expense_ratio"],
                "rd_intensity": float(pfd.rd_intensity or 0) if pfd.rd_intensity is not None else 0.0,
                "revenue_growth": float(pfd.revenue_growth or 0) if pfd.revenue_growth is not None else 0.0,
                "additional_features": pfd.additional_features or {},
            }
            
            # ✅ LOGGING: Show calculated ratios for debugging
            if total_operating_expenses == 0.0 and total_revenue > 0:
                logger.warning(f"⚠️ Dashboard: Operating Expenses is 0, expense_ratio will be 0")
            else:
                logger.info(f"✅ Dashboard: Calculated expense_ratio = {calculated_ratios['expense_ratio']:.4f} "
                           f"({calculated_ratios['expense_ratio'] * 100:.2f}%) from OPEX={total_operating_expenses:,.2f}, Revenue={total_revenue:,.2f}")

            # ✅ ENHANCED LOGGING: Show which record and what data is being used
            try:
                debug_data = {
                    "debug_snapshot_before_fx": {
                        "total_revenue": snapshot["total_revenue"],
                        "cost_of_revenue": snapshot["cost_of_revenue"],
                        "gross_profit": snapshot["gross_profit"],
                        "operating_expenses": snapshot["total_operating_expenses"],
                        "operating_income": snapshot["operating_income"],
                        "net_income": snapshot["net_income"],
                    }
                }
                print(debug_data)
                # ✅ Also log to logger for better visibility
                logger.info(f"📊 Dashboard Snapshot (before FX): Revenue={snapshot['total_revenue']:,.2f}, "
                           f"OPEX={snapshot['total_operating_expenses']:,.2f}, "
                           f"OI={snapshot['operating_income']:,.2f}, NI={snapshot['net_income']:,.2f}")
                if snapshot["total_operating_expenses"] == 0.0:
                    logger.warning(f"⚠️ Dashboard showing Operating Expenses = 0.0 - this may be old data!")
            except Exception as e:
                logger.error(f"Error in debug logging: {e}")

            return snapshot

        # ✅ FIX: Proper try-except block structure
        try:
            # If upload_id provided, verify upload completed, then resolve its processed snapshot and date
            if upload_id:
                try:
                    upload_rec = FinancialDataUpload.objects.get(id=upload_id, corporate_id=corporate_id)
                except FinancialDataUpload.DoesNotExist:
                    return ResponseProvider(message="Upload not found for this corporate.", code=404).not_found()
                if upload_rec.processing_status != 'completed':
                    return ResponseProvider(
                        message="Processing not completed yet for this upload. Please wait until status is 'completed'.",
                        code=202
                    ).success()
                pfd_qs = ProcessedFinancialData.objects.filter(upload_id=upload_id, corporate_id=corporate_id).order_by(
                    '-period_date')
                resolved_snapshot = pfd_qs.first()
                if resolved_snapshot:
                    resolved_statement_date = resolved_snapshot.period_date

            # Else if a statement_date was provided, use it and pick the latest snapshot at or before that date
            if not resolved_statement_date and statement_date_str:
                try:
                    candidate_date = datetime.strptime(statement_date_str, '%Y-%m-%d').date()
                except Exception:
                    return ResponseProvider(message="Invalid statement_date format; expected YYYY-MM-DD",
                                            code=400).bad_request()
                pfd_qs = ProcessedFinancialData.objects.filter(corporate_id=corporate_id,
                                                               period_date__lte=candidate_date).order_by('-period_date')
                resolved_snapshot = pfd_qs.first()
                resolved_statement_date = candidate_date

            # Fallback: if nothing specified, use the most recent processed snapshot and its date
            # ✅ FIXED: Order by created_at first (most recent upload), then period_date
            if not resolved_statement_date:
                pfd_qs = ProcessedFinancialData.objects.filter(corporate_id=corporate_id).order_by('-created_at', '-period_date')
                resolved_snapshot = pfd_qs.first()
                if not resolved_snapshot:
                    return ResponseProvider(
                        message="No processed financial data found. Please upload and complete processing first.",
                        code=404
                    ).not_found()
                resolved_statement_date = resolved_snapshot.period_date
                # ✅ LOGGING: Show which record is being used
                logger.info(f"📊 Dashboard using latest record: ID={resolved_snapshot.id}, Created={resolved_snapshot.created_at}, "
                           f"OPEX={resolved_snapshot.total_operating_expenses:,.2f}")

            # Final gate: ensure snapshot exists
            if not resolved_snapshot:
                return ResponseProvider(message="No processed snapshot available for analysis.", code=404).not_found()

        except Exception as e:
            logger.error(f"Error resolving statement snapshot: {str(e)}")
            return ResponseProvider(
                message=f"Error resolving financial snapshot: {str(e)}",
                code=500
            ).exception()

        # ✅ Get all completed analyses in date range
        all_analyses = TazamaAnalysisRequest.objects.filter(
            corporate_id=corporate_id,
            status='completed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).order_by('-created_at')

        total_analyses = all_analyses.count()

        # ✅ Calculate average predictions across all analyses
        average_predictions = {
            'profit_margin': 0,
            'operating_margin': 0,
            'cost_revenue_ratio': 0,
            'expense_ratio': 0
        }

        if total_analyses > 0:
            for target in average_predictions.keys():
                total = sum(
                    analysis.predictions.get(target, 0)
                    for analysis in all_analyses
                    if analysis.predictions
                )
                average_predictions[target] = round(total / total_analyses, 4)

        # ✅ Calculate risk distribution
        risk_distribution = {
            'LOW': 0,
            'MEDIUM': 0,
            'HIGH': 0
        }

        for analysis in all_analyses:
            if analysis.risk_assessment:
                risk_level = analysis.risk_assessment.get('overall_risk', 'LOW')
                risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1

        # ✅ Get recent analyses with full details (last 20)
        recent_analyses = all_analyses[:20]

        analyses_data = []
        for analysis in recent_analyses:
            base_preds = analysis.predictions or {}
            inp = analysis.input_data or {}
            # Recompute display predictions from input totals if available
            try:
                tr = float(inp.get('totalRevenue', 0) or 0)
                ni = float(inp.get('netIncome', 0) or 0)
                oi = float(inp.get('operatingIncome', 0) or 0)
                gp = float(inp.get('grossProfit', 0) or 0)
                cor = float(inp.get('costOfRevenue', 0) or 0)
                opex = float(inp.get('totalOperatingExpenses', 0) or 0)
                def sratio(num, den):
                    return max(0.0, min(1.0, (num / den) if den and den > 0 else 0.0))
                display_preds = {
                    'profit_margin': sratio(ni, tr),
                    'operating_margin': sratio(oi, tr),
                    'cost_revenue_ratio': sratio(cor, tr),
                    'expense_ratio': sratio(opex, tr),
                    'gross_margin': sratio(gp, tr),
                } if tr > 0 else {}
            except Exception:
                display_preds = {}

            # Extract date and frequency metadata from predictions
            date_metadata = {}
            if isinstance(base_preds, dict):
                # Extract date metadata from predictions
                if 'projection_date' in base_preds:
                    date_metadata['projection_date'] = base_preds.get('projection_date')
                if 'frequency' in base_preds:
                    date_metadata['frequency'] = base_preds.get('frequency')
                if 'next_quarter_date' in base_preds:
                    date_metadata['next_quarter_date'] = base_preds.get('next_quarter_date')
                if 'next_quarter_year' in base_preds:
                    date_metadata['next_quarter_year'] = base_preds.get('next_quarter_year')
                if 'next_quarter_quarter' in base_preds:
                    date_metadata['next_quarter_quarter'] = base_preds.get('next_quarter_quarter')
                if 'next_annual_date' in base_preds:
                    date_metadata['next_annual_date'] = base_preds.get('next_annual_date')
                if 'next_annual_year' in base_preds:
                    date_metadata['next_annual_year'] = base_preds.get('next_annual_year')
            
            # Also check if date_metadata exists in the analysis request (from EnhancedFinancialOptimizer)
            # This would be stored in a separate field if we added it to the model
            # For now, we'll extract from predictions as above
            
            analyses_data.append({
                'id': str(analysis.id),
                'date': analysis.created_at.date().isoformat(),
                'datetime': analysis.created_at.isoformat(),
                'predictions': base_preds,
                'display_predictions': display_preds if display_preds else base_preds,
                'input_data': inp,
                'recommendations_count': len(
                    analysis.recommendations.get('immediate_actions', [])) if analysis.recommendations else 0,
                'risk_level': analysis.risk_assessment.get('overall_risk',
                                                           'LOW') if analysis.risk_assessment else 'LOW',
                'risk_factors_count': len(
                    analysis.risk_assessment.get('risk_factors', [])) if analysis.risk_assessment else 0,
                'processing_time': round(analysis.processing_time_seconds,
                                         2) if analysis.processing_time_seconds else 0,
                'confidence_scores': analysis.confidence_scores or {},
                'truth_report': analysis.truth_report or {},  # ✅ Include truth report for dashboard
                'model_info': {
                    'name': analysis.model_used.name,
                    'type': analysis.model_used.model_type,
                    'version': analysis.model_used.version
                } if analysis.model_used else None,
                'date_metadata': date_metadata if date_metadata else None
            })

        # ✅ Get uploads summary
        total_uploads = FinancialDataUpload.objects.filter(
            corporate_id=corporate_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).count()

        successful_uploads = FinancialDataUpload.objects.filter(
            corporate_id=corporate_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            processing_status='completed'
        ).count()

        # ✅ Get model performance data
        available_models = TazamaMLModel.objects.filter(is_active=True)
        models_data = []
        for model in available_models:
            predictions_count = ModelPredictionLog.objects.filter(
                model=model,
                corporate_id=corporate_id
            ).count()

            recent_predictions = ModelPredictionLog.objects.filter(
                model=model,
                corporate_id=corporate_id,
                timestamp__gte=timezone.now() - timedelta(days=30)
            ).count()

            models_data.append({
                'id': model.id,
                'name': model.name,
                'type': model.model_type,
                'version': model.version,
                'performance_metrics': model.performance_metrics or {},
                'usage_count': predictions_count,
                'recent_usage_30d': recent_predictions,
                'created_at': model.created_at.isoformat(),
                'last_used': ModelPredictionLog.objects.filter(
                    model=model,
                    corporate_id=corporate_id
                ).order_by('-timestamp').first().timestamp.isoformat() if predictions_count > 0 else None
            })

        # ✅ Calculate trends
        trend_data = []
        for analysis in reversed(analyses_data):
            trend_data.append({
                'date': analysis['date'],
                'profit_margin': analysis.get('display_predictions', {}).get('profit_margin', analysis['predictions'].get('profit_margin', 0)),
                'operating_margin': analysis.get('display_predictions', {}).get('operating_margin', analysis['predictions'].get('operating_margin', 0)),
                'cost_revenue_ratio': analysis.get('display_predictions', {}).get('cost_revenue_ratio', analysis['predictions'].get('cost_revenue_ratio', 0)),
                'expense_ratio': analysis.get('display_predictions', {}).get('expense_ratio', analysis['predictions'].get('expense_ratio', 0)),
                'risk_level': analysis['risk_level']
            })

        # ✅ Calculate period-over-period changes
        latest_analysis = all_analyses.first()
        previous_analysis = all_analyses[1] if all_analyses.count() > 1 else None

        changes = {}
        if latest_analysis and previous_analysis and latest_analysis.predictions and previous_analysis.predictions:
            for metric in ['profit_margin', 'operating_margin', 'cost_revenue_ratio', 'expense_ratio']:
                current = latest_analysis.predictions.get(metric, 0)
                previous = previous_analysis.predictions.get(metric, 0)
                if previous != 0:
                    change_pct = ((current - previous) / abs(previous)) * 100
                    changes[metric] = {
                        'current': round(current, 4),
                        'previous': round(previous, 4),
                        'change': round(current - previous, 4),
                        'change_percentage': round(change_pct, 2)
                    }

        # ✅ Time-sensitive, statement-aligned intelligent analysis
        enhanced_service = EnhancedFinancialDataService()
        financial_data_snapshot = build_financial_data_dict(resolved_snapshot)

        # ✅ FIX: Validate snapshot has data before calling intelligent analysis
        def snapshot_has_signal(snap: dict) -> bool:
            keys_to_check = ['total_revenue', 'gross_profit', 'operating_income', 'net_income']
            return any((snap.get(k) or 0) not in (0, None) for k in keys_to_check)

        if not snapshot_has_signal(financial_data_snapshot):
            # Try to find an alternative snapshot with data
            alt_qs = ProcessedFinancialData.objects.filter(
                corporate_id=corporate_id,
                period_date__lte=resolved_statement_date
            ).order_by('-period_date')
            for alt in alt_qs:
                alt_snap = build_financial_data_dict(alt)
                if snapshot_has_signal(alt_snap):
                    financial_data_snapshot = alt_snap
                    break

        intelligent = enhanced_service.analyze_intelligent_date_driven_projection(
            financial_data=financial_data_snapshot,
            statement_date=resolved_statement_date,
            corporate_id=corporate_id
        )

        # ✅ Currency conversion
        monetary_keys = set([
            'total_revenue', 'cost_of_revenue', 'gross_profit', 'total_operating_expenses',
            'operating_income', 'net_income', 'revenue', 'expenses', 'costs', 'cash',
            'projected_revenue', 'projected_net_income', 'projected_gross_profit',
            'projected_operating_income', 'projected_cost_of_revenue'
        ])

        def is_monetary_field(key: str, value) -> bool:
            if not isinstance(key, str):
                return False
            lower = key.lower()
            if any(s in lower for s in ['margin', 'ratio', 'rate', 'percent', 'growth', 'score']) or lower.endswith(
                    '_pct'):
                return False
            if key in monetary_keys:
                return True
            endings = ['_revenue', '_income', '_expenses', '_expense', '_cost', '_cash', '_amount', '_spend']
            if any(lower.endswith(end) for end in endings):
                return isinstance(value, (int, float))
            contains_terms = ['revenue', 'income', 'expense', 'expenses', 'cost', 'profit', 'cash', 'amount', 'spend']
            if any(term in lower for term in contains_terms):
                return isinstance(value, (int, float))
            return False

        def convert_nested(obj, rate: float):
            if isinstance(obj, dict):
                new_obj = {}
                for k, v in obj.items():
                    if is_monetary_field(k, v) and isinstance(v, (int, float)):
                        new_obj[k] = round(float(v) * rate, 2)
                    else:
                        new_obj[k] = convert_nested(v, rate)
                return new_obj
            elif isinstance(obj, list):
                return [convert_nested(x, rate) for x in obj]
            else:
                return obj

        # Get currency conversion rate
        currency_info = convert_currency(1.0, 'KES', requested_currency)
        rate = float(currency_info.get('rate', 1.0))

        # Convert all monetary values
        converted_snapshot = convert_nested(financial_data_snapshot, rate)
        converted_intelligent = convert_nested(intelligent, rate)

        # Debug logging after conversion
        try:
            print({
                "debug_snapshot_after_fx": {
                    "total_revenue": converted_snapshot.get("total_revenue"),
                    "cost_of_revenue": converted_snapshot.get("cost_of_revenue"),
                    "gross_profit": converted_snapshot.get("gross_profit"),
                    "operating_expenses": converted_snapshot.get("total_operating_expenses"),
                    "operating_income": converted_snapshot.get("operating_income"),
                    "net_income": converted_snapshot.get("net_income"),
                }
            })
        except Exception:
            pass

        # ✅ Recompute KPI trends dynamically from recent analyses
        def compute_trends_from_history(history: list) -> dict:
            if not history:
                return {}
            # Use last two points if available
            latest = history[-1]
            prev = history[-2] if len(history) > 1 else None
            trends_out = {}
            keys = ['profit_margin', 'operating_margin', 'gross_margin', 'cost_revenue_ratio', 'expense_ratio']
            for k in keys:
                cur = latest.get(k, 0)
                if prev is None:
                    trends_out[k] = {'trend': 'stable', 'change': 0}
                    continue
                pr = prev.get(k, 0)
                delta = cur - pr
                # classify movement
                if k in ['cost_revenue_ratio', 'expense_ratio']:
                    # lower is better
                    if delta <= -0.02:
                        t = 'improving'
                    elif delta >= 0.02:
                        t = 'declining'
                    elif abs(delta) < 0.005:
                        t = 'stable'
                    else:
                        t = 'declining' if delta > 0 else 'improving'
                else:
                    if delta >= 0.02:
                        t = 'improving'
                    elif delta <= -0.02:
                        t = 'declining'
                    elif abs(delta) < 0.005:
                        t = 'stable'
                    else:
                        t = 'improving' if delta > 0 else 'declining'
                # critical state checks
                critical = False
                if k in ['profit_margin', 'operating_margin'] and cur < 0.02:
                    critical = True
                if k in ['cost_revenue_ratio', 'expense_ratio'] and cur > 0.90:
                    critical = True
                trends_out[k] = {'trend': 'critical' if critical else t, 'change': round(delta, 4)}
            return trends_out

        dynamic_trends = compute_trends_from_history(trend_data)

        # ✅ Sync benchmark current values from statement snapshot explicitly
        def safe_ratio(num: float, den: float) -> float:
            try:
                return max(0.0, min(1.0, (num / den) if den and den > 0 else 0.0))
            except Exception:
                return 0.0

        snap_rev = float(converted_snapshot.get('total_revenue', 0) or 0)
        snapshot_ratios = {
            'profit_margin': safe_ratio(float(converted_snapshot.get('net_income', 0) or 0), snap_rev),
            'operating_margin': safe_ratio(float(converted_snapshot.get('operating_income', 0) or 0), snap_rev),
            'gross_margin': safe_ratio(float(converted_snapshot.get('gross_profit', 0) or 0), snap_rev),
            'cost_revenue_ratio': safe_ratio(float(converted_snapshot.get('cost_of_revenue', 0) or 0), snap_rev),
            'expense_ratio': safe_ratio(float(converted_snapshot.get('total_operating_expenses', 0) or 0), snap_rev)
        }

        # Mutate intelligent analysis with dynamic trends and benchmark current values
        try:
            if isinstance(converted_intelligent, dict):
                # KPI trends update
                kp = converted_intelligent.get('kpi_predictions', {})
                if kp:
                    # update trends
                    if 'kpi_trends' in kp and isinstance(kp['kpi_trends'], dict):
                        kp['kpi_trends'].update(dynamic_trends)
                    else:
                        kp['kpi_trends'] = dynamic_trends
                    # sync benchmarks
                    if 'profitability_kpis' in kp:
                        pass
                    ba = kp.get('benchmark_analysis', {})
                    for k in ['profit_margin', 'operating_margin', 'gross_margin', 'cost_revenue_ratio', 'expense_ratio']:
                        if ba.get(k):
                            ba[k]['current_value'] = snapshot_ratios[k]
                        else:
                            ba[k] = {
                                'current_value': snapshot_ratios[k]
                            }
                    kp['benchmark_analysis'] = ba
                    converted_intelligent['kpi_predictions'] = kp
                # Dynamic confidence based on variance in recent analyses
                try:
                    import statistics
                    vals = []
                    for it in analyses_data[-10:]:
                        preds = it.get('predictions', {})
                        row = [
                            float(preds.get('profit_margin', 0)),
                            float(preds.get('operating_margin', 0)),
                            float(preds.get('cost_revenue_ratio', 0)),
                            float(preds.get('expense_ratio', 0))
                        ]
                        vals.append(row)
                    flat = [x for row in vals for x in row] if vals else []
                    stdv = statistics.pstdev(flat) if flat else 0.0
                    # Map std dev (~0..0.3) to confidence 1..0.5
                    conf_overall = max(0.4, min(1.0, 1.0 - (stdv * 1.2)))
                except Exception:
                    conf_overall = 0.8
                ca = converted_intelligent.get('confidence_analysis', {})
                ca['overall'] = round(float(conf_overall), 3)
                converted_intelligent['confidence_analysis'] = ca
                # Dynamic overall risk based on benchmark gaps
                ba = converted_intelligent.get('kpi_predictions', {}).get('benchmark_analysis', {})
                total_gap = 0.0
                for k, item in ba.items():
                    if isinstance(item, dict):
                        total_gap += float(item.get('gap', 0) or 0)
                if total_gap > 1.2:
                    overall = 'HIGH'
                elif total_gap > 0.6:
                    overall = 'MEDIUM'
                else:
                    overall = 'LOW'
                # Attach summarized risk level for dashboard recent card
                converted_intelligent['risk_summary'] = {'overall_risk': overall}
        except Exception:
            pass

        # Convert input_data in recent analyses
        for item in analyses_data:
            if 'input_data' in item and isinstance(item['input_data'], dict):
                item['input_data'] = convert_nested(item['input_data'], rate)

        # Determine frequency from statement date
        statement_frequency = 'quarterly' if resolved_statement_date.month in [3, 6, 9, 12] else 'annual'
        
        # Calculate next period dates based on frequency
        next_period_info = {}
        if statement_frequency == 'quarterly':
            next_quarter_date = resolved_statement_date + relativedelta(months=3)
            next_period_info = {
                'next_quarter_date': next_quarter_date.isoformat(),
                'next_quarter_year': next_quarter_date.year,
                'next_quarter_quarter': ((next_quarter_date.month - 1) // 3) + 1
            }
        else:
            next_annual_date = resolved_statement_date + relativedelta(years=1)
            next_period_info = {
                'next_annual_date': next_annual_date.isoformat(),
                'next_annual_year': next_annual_date.year
            }
        
        # Add date metadata to intelligent analysis if not already present
        if isinstance(converted_intelligent, dict):
            if 'date_metadata' not in converted_intelligent:
                converted_intelligent['date_metadata'] = {}
            converted_intelligent['date_metadata'].update({
                'statement_date': resolved_statement_date.isoformat(),
                'frequency': statement_frequency,
                **next_period_info
            })
        
        # ✅ Get the latest truth report for dashboard display
        # Find the most recent analysis with a valid truth report containing recommendations
        latest_truth_report = {}
        for analysis in all_analyses[:10]:  # Check last 10 analyses
            truth_report = analysis.truth_report or {}
            if (truth_report and
                truth_report.get('brutally_honest_recommendations') and
                len(truth_report.get('brutally_honest_recommendations', [])) > 0):
                latest_truth_report = truth_report
                logger.info(f"📤 Dashboard: Found truth_report with {len(truth_report.get('brutally_honest_recommendations', []))} recommendations from analysis {analysis.id}")
                break

        if not latest_truth_report:
            logger.warning("📤 Dashboard: No valid truth_report found in recent analyses - this may cause frontend display issues")
        
        # Build dashboard response
        dashboard_data = {
            "alignment": {
                "reference_statement_date": resolved_statement_date.isoformat(),
                "source": "upload_id" if upload_id else ("explicit_date" if statement_date_str else "latest_snapshot"),
                "frequency": statement_frequency,
                **next_period_info
            },
            "currency": {
                "code": requested_currency,
                "rate": currency_info.get('rate', 1.0),
                "from": "KES",
                "to": requested_currency,
                "timestamp": currency_info.get('timestamp')
            },
            "intelligent_analysis": converted_intelligent,
            "truth_report": latest_truth_report,  # ✅ Latest truth report for dashboard display
            'summary': {
                'total_analyses': total_analyses,
                'total_uploads': total_uploads,
                'successful_uploads': successful_uploads,
                'average_predictions': average_predictions,
                'risk_distribution': risk_distribution
            },
            'recent_analyses': analyses_data,
            'statement_snapshot': {
                **converted_snapshot,
                'period_date': resolved_statement_date.isoformat(),
                'frequency': statement_frequency
            },
            'trends': {
                'data': trend_data
            },
            'period_over_period_changes': changes,
            'available_models': models_data,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }

        TransactionLogBase.log(
            transaction_type="DASHBOARD_DATA_RETRIEVED",
            user=user,
            message="Dashboard data retrieved successfully",
            state_name="Success",
            extra={
                "period": f"{start_date} to {end_date}",
                "total_analyses": total_analyses
            },
            request=request,
        )

        return ResponseProvider(
            data=dashboard_data,
            message="Time-sensitive dashboard data retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        TransactionLogBase.log(
            transaction_type="DASHBOARD_DATA_RETRIEVAL_FAILED",
            user=user,
            message=f"{str(e)} | Trace: {error_trace}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"An error occurred while retrieving dashboard data: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def train_model(request):
    """
    Trigger model training/retraining using income statement data.

    Expected data:
    - training_type: 'initial_training', 'incremental_training', or 'full_retrain'
    - include_all_data: Boolean to include data from all corporates or just current user's
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        training_type = data.get('training_type', 'incremental_training')
        include_all_data = bool(data.get('include_all_data', False))

        # 🔑 Load dataset from Tazama/data folder
        base_path = os.path.join(settings.BASE_DIR, "Tazama", "data")

        annual_path = os.path.join(base_path, "incomeStatementHistory_annually.csv")
        quarterly_path = os.path.join(base_path, "incomeStatementHistory_quarterly.csv")

        df_annual = pd.read_csv(annual_path)
        df_annual["frequency"] = "annual"
        # Convert endDate to date column for consistency
        if 'endDate' in df_annual.columns:
            df_annual['date'] = pd.to_datetime(df_annual['endDate'], errors='coerce')
        elif 'date' not in df_annual.columns:
            raise ValueError("No date column found in annual data")

        df_quarterly = pd.read_csv(quarterly_path)
        df_quarterly["frequency"] = "quarterly"
        # Convert endDate to date column for consistency
        if 'endDate' in df_quarterly.columns:
            df_quarterly['date'] = pd.to_datetime(df_quarterly['endDate'], errors='coerce')
        elif 'date' not in df_quarterly.columns:
            raise ValueError("No date column found in quarterly data")

        dataset = pd.concat([df_annual, df_quarterly], ignore_index=True)

        # Ensure date column is properly formatted and drop rows with invalid dates
        dataset = dataset.dropna(subset=['date'])
        dataset['date'] = pd.to_datetime(dataset['date'])
        
        # Ensure symbol column exists (use 'stock' if available, otherwise create from symbol)
        if 'stock' in dataset.columns and 'symbol' not in dataset.columns:
            dataset['symbol'] = dataset['stock'].astype(str)
        elif 'symbol' not in dataset.columns:
            dataset['symbol'] = 'UNKNOWN'

        # Optional preprocessing
        dataset = dataset.dropna(how="all")  # drop fully empty rows
        
        # Sort by symbol, frequency, and date for proper time series ordering
        dataset = dataset.sort_values(['symbol', 'frequency', 'date'])

        # ✅ Pass dataset into training service
        training_service = ModelTrainingService()
        job = training_service.start_training_job(
            job_type=training_type,
            user=user,
            corporate_id=None if include_all_data else corporate_id,
            dataset=dataset
        )

        TransactionLogBase.log(
            transaction_type="MODEL_TRAINING_STARTED",
            user=user,
            message=f"Model training job started: {training_type}",
            state_name="Success",
            extra={
                "job_id": job.id,
                "training_type": training_type,
                "include_all_data": include_all_data,
                "num_records": len(dataset),
            },
            request=request,
        )

        return ResponseProvider(
            data={
                "job_id": job.id,
                "status": job.status,
                "training_type": job.job_type,
                "created_at": job.created_at.isoformat(),
                "records_used": len(dataset),
                "message": "Training job started successfully with income statement data"
            },
            message="Model training initiated successfully",
            code=200
        ).success()

    except Exception as e:
        import traceback
        TransactionLogBase.log(
            transaction_type="MODEL_TRAINING_START_FAILED",
            user=user,
            message=f"{str(e)} | Traceback: {traceback.format_exc()}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while starting model training",
            code=500
        ).exception()



@csrf_exempt
def get_training_status(request):
    """
    Get status of model training jobs
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        # Get recent training jobs
        recent_jobs = ModelTrainingJob.objects.filter(
            triggered_by=user
        ).order_by('-created_at')[:10]

        jobs_data = []
        for job in recent_jobs:
            job_data = {
                'id': job.id,
                'job_type': job.job_type,
                'status': job.status,
                'progress_percentage': job.progress_percentage,
                'training_data_count': job.training_data_count,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'duration_seconds': job.duration_seconds,
                'error_message': job.error_message,
                'training_metrics': job.training_metrics,
                'validation_metrics': job.validation_metrics,
                'overfitting_analysis': job.overfitting_analysis
            }

            if job.model:
                job_data['model_info'] = {
                    'id': job.model.id,
                    'name': job.model.name,
                    'version': job.model.version,
                    'type': job.model.model_type
                }

            jobs_data.append(job_data)

        return ResponseProvider(
            data={
                "training_jobs": jobs_data,
                "total_jobs": len(jobs_data)
            },
            message="Training status retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving training status",
            code=500
        ).exception()


@csrf_exempt
def download_analysis_report(request):
    """
    Generate and download comprehensive analysis report

    Expected data:
    - analysis_id: ID of the analysis request
    - format: 'pdf', 'json', 'excel', or 'html'
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)

    try:
        analysis_id = data.get('analysis_id')
        report_format = data.get('format', 'html')  # ✅ Default now is 'html'

        if not analysis_id:
            return ResponseProvider(message="Analysis ID is required", code=400).bad_request()

        # Get analysis request
        from OrgAuth.models import CorporateUser

        if isinstance(user, dict):
            corporate_user = CorporateUser.objects.get(customuser_ptr_id=user_id)
        else:
            corporate_user = user

        analysis_request = TazamaAnalysisRequest.objects.get(
            id=analysis_id,
            requested_by=corporate_user,
            status='completed'
        )

        # Generate report
        report_generator = TazamaReportGenerator()
        report_file_path, content_type = report_generator.generate_report(
            analysis_request, report_format
        )

        # ✅ FIX: Extract only the relative path
        import os
        relative_path = os.path.relpath(report_file_path, settings.MEDIA_ROOT)

        # ✅ FIX: Safe title and summary
        date_str = analysis_request.created_at.strftime('%Y-%m-%d')
        title = f"Report {date_str}"[:90]
        summary = "AI financial analysis"[:255]

        # Create FinancialReport record
        report = FinancialReport.objects.create(
            analysis_request=analysis_request,
            corporate=analysis_request.corporate,
            report_type='ai_analysis'[:50],
            title=title,
            executive_summary=summary,
            detailed_analysis=analysis_request.predictions or {},
            recommendations=analysis_request.recommendations or {},
            report_format=report_format[:20],
            report_file=relative_path
        )

        # ✅ Serve the file according to requested format
        if report_format == 'json':
            from Tazama.core.report_generator import sanitize_report_data_for_json
            sanitized_predictions = sanitize_report_data_for_json(analysis_request.predictions)
            response = JsonResponse(sanitized_predictions, safe=False)

        elif report_format == 'html':
            with open(report_file_path, 'r', encoding='utf-8') as f:
                response = HttpResponse(f.read(), content_type='text/html')

        else:  # pdf, excel, etc.
            with open(report_file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type=content_type)
            safe_filename = f"report_{analysis_request.id}.{report_format}"
            response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'

        # Update download count
        report.download_count += 1
        report.save()

        TransactionLogBase.log(
            transaction_type="ANALYSIS_REPORT_DOWNLOADED",
            user=user,
            message=f"Analysis report downloaded: {report_format}",
            state_name="Success",
            extra={
                "analysis_id": analysis_id,
                "report_id": report.id,
                "format": report_format
            },
            request=request,
        )

        return response

    except TazamaAnalysisRequest.DoesNotExist:
        return ResponseProvider(message="Analysis request not found", code=404).not_found()
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        TransactionLogBase.log(
            transaction_type="ANALYSIS_REPORT_DOWNLOAD_FAILED",
            user=user,
            message=f"{str(e)} | Trace: {error_trace}",
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"An error occurred while generating the report: {str(e)}",
            code=500
        ).exception()

@csrf_exempt
def get_processed_data_history(request):
    """
    Get history of processed financial data for a corporate

    Expected data (optional):
    - start_date: Start date filter
    - end_date: End date filter
    - limit: Number of records to return (default: 50)
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        # Parse filters
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        limit = int(data.get("limit", 50))

        # Build query
        queryset = ProcessedFinancialData.objects.filter(corporate_id=corporate_id)

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            queryset = queryset.filter(period_date__gte=start_date)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            queryset = queryset.filter(period_date__lte=end_date)

        # Get data
        financial_data = queryset.order_by('-period_date')[:limit]

        data_list = []
        for record in financial_data:
            data_list.append({
                'id': record.id,
                'period_date': record.period_date.isoformat(),
                'total_revenue': str(record.total_revenue),
                'cost_of_revenue': str(record.cost_of_revenue),
                'gross_profit': str(record.gross_profit),
                'operating_income': str(record.operating_income),
                'net_income': str(record.net_income),
                'profit_margin': str(record.profit_margin) if record.profit_margin else None,
                'operating_margin': str(record.operating_margin) if record.operating_margin else None,
                'cost_revenue_ratio': str(record.cost_revenue_ratio) if record.cost_revenue_ratio else None,
                'expense_ratio': str(record.expense_ratio) if record.expense_ratio else None,
                'upload_info': {
                    'id': record.upload.id,
                    'file_name': record.upload.file_name,
                    'upload_date': record.upload.created_at.isoformat()
                } if record.upload else None,
                'is_validated': record.is_validated,
                'created_at': record.created_at.isoformat()
            })

        return ResponseProvider(
            data={
                "financial_data": data_list,
                "total_records": len(data_list),
                "filters": {
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "limit": limit
                }
            },
            message="Financial data history retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        TransactionLogBase.log(
            transaction_type="FINANCIAL_DATA_HISTORY_RETRIEVAL_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message="An error occurred while retrieving financial data history",
            code=500
        ).exception()


@csrf_exempt
def get_model_performance(request):
    """
    Get performance metrics and details of available models
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        # Get all active models
        models = TazamaMLModel.objects.filter(is_active=True).order_by('-created_at')

        models_data = []
        for model in models:
            model_data = {
                'id': model.id,
                'name': model.name,
                'model_type': model.model_type,
                'version': model.version,
                'created_at': model.created_at.isoformat(),
                'updated_at': model.updated_at.isoformat(),
                'feature_columns': model.feature_columns,
                'target_columns': model.target_columns,
                'performance_metrics': model.performance_metrics,
                'training_history': model.training_history
            }

            # Calculate usage statistics
            usage_count = ModelPredictionLog.objects.filter(model=model).count()
            recent_usage = ModelPredictionLog.objects.filter(
                model=model,
                timestamp__gte=timezone.now() - timedelta(days=30)
            ).count()

            model_data['usage_stats'] = {
                'total_predictions': usage_count,
                'recent_predictions_30d': recent_usage,
                'avg_processing_time_ms': ModelPredictionLog.objects.filter(
                    model=model
                ).aggregate(avg_time=models.Avg('processing_time_ms'))['avg_time'] or 0
            }

            models_data.append(model_data)

        return ResponseProvider(
            data={
                "models": models_data,
                "total_models": len(models_data)
            },
            message="Model performance data retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving model performance data",
            code=500
        ).exception()


# Additional utility views for API integration

@csrf_exempt
def validate_financial_data(request):
    """
    Enhanced financial data validation with intelligent checks
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        financial_data = data.get('financial_data', {})

        # Use enhanced validation service
        enhanced_service = EnhancedFinancialDataService()
        validation_result = enhanced_service.validate_financial_data(financial_data)

        return ResponseProvider(
            data=validation_result,
            message="Enhanced data validation completed",
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(
            message="An error occurred during enhanced data validation",
            code=500
        ).exception()


@csrf_exempt
def test_intelligent_extraction(request):
    """
    Test intelligent data extraction with sample data
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        # Get test file path or sample data
        test_file_path = data.get('test_file_path')
        sample_data = data.get('sample_data')
        
        if not test_file_path and not sample_data:
            return ResponseProvider(
                message="Either test_file_path or sample_data must be provided",
                code=400
            ).bad_request()

        # Use enhanced service for testing
        enhanced_service = EnhancedFinancialDataService()
        
        if test_file_path:
            # Test with actual file
            from Tazama.Services.IntelligentDataExtractor import IntelligentDataExtractor
            extractor = IntelligentDataExtractor()
            extraction_result = extractor.extract_financial_data(test_file_path)
        else:
            # Test with sample data
            extraction_result = {
                'success': True,
                'extracted_data': {
                    'test_sheet': {
                        'metrics': sample_data,
                        'confidence': 0.9
                    }
                },
                'confidence': 0.9,
                'extraction_method': 'sample_data'
            }

        return ResponseProvider(
            data={
                "extraction_result": extraction_result,
                "test_timestamp": timezone.now().isoformat(),
                "enhanced_features": [
                    "Fuzzy string matching",
                    "Pattern recognition", 
                    "Context-aware extraction",
                    "Multi-language support",
                    "Intelligent validation"
                ]
            },
            message="Intelligent extraction test completed",
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(
            message=f"Intelligent extraction test failed: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def get_complete_pipeline_status(request):
    """
    Get the status of the complete analysis pipeline
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    try:
        upload_id = data.get('upload_id')
        if not upload_id:
            return ResponseProvider(
                message="Upload ID is required",
                code=400
            ).bad_request()

        # Resolve user's corporate properly (dict or model instance)
        try:
            from OrgAuth.models import CorporateUser
            if isinstance(user, dict):
                corporate_user = CorporateUser.objects.get(customuser_ptr_id=user.get('id'))
            else:
                corporate_user = user
            corporate = corporate_user.corporate
        except Exception:
            return ResponseProvider(message="Unable to resolve user's corporate", code=400).bad_request()

        # Get upload record scoped to corporate
        try:
            upload_record = FinancialDataUpload.objects.get(id=upload_id, corporate=corporate)
        except FinancialDataUpload.DoesNotExist:
            return ResponseProvider(message="Upload record not found", code=404).not_found()

        # Get pipeline status
        pipeline = CompleteAnalysisPipeline()
        pipeline_status = pipeline.get_pipeline_status()

        # Get analysis results if available
        analysis_results = {}
        if upload_record.processing_status == 'completed':
            # Get latest analysis
            latest_analysis = TazamaAnalysisRequest.objects.filter(
                corporate=user.corporate
            ).order_by('-created_at').first()
            
            if latest_analysis:
                analysis_results = {
                    'analysis_id': latest_analysis.id,
                    'status': latest_analysis.status,
                    'confidence_scores': latest_analysis.confidence_scores,
                    'processing_time': latest_analysis.processing_time_seconds,
                    'created_at': latest_analysis.created_at.isoformat()
                }

        return ResponseProvider(
            data={
                "upload_id": upload_id,
                "file_name": upload_record.file_name,
                "processing_status": upload_record.processing_status,
                "pipeline_status": pipeline_status,
                "analysis_results": analysis_results,
                "rows_processed": upload_record.rows_processed
            },
            message="Pipeline status retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(
            message=f"Error retrieving pipeline status: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def convert_currency_endpoint(request):
    """
    Currency conversion endpoint
    """
    data, metadata = get_clean_data(request)
    
    try:
        amount = float(data.get('amount', 1.0))
        from_currency = data.get('from', 'KES').upper()
        to_currency = data.get('to', 'USD').upper()
        
        result = convert_currency(amount, from_currency, to_currency)
        
        return ResponseProvider(
            data=result,
            message="Currency conversion successful",
            code=200
        ).success()
    except Exception as e:
        return ResponseProvider(
            message=f"Currency conversion failed: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def get_analysis_history(request):
    """
    Get history of analysis requests for a corporate
    """
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)
    if not user_id:
        return ResponseProvider(message="User ID not found", code=400).bad_request()

    try:
        registry = ServiceRegistry()

        # Get corporate association
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user_id, "is_active": True}
        )
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()

        corporate_id = corporate_users[0]["corporate_id"]

        limit = int(data.get("limit", 20))

        # Get analysis history
        analyses = TazamaAnalysisRequest.objects.filter(
            corporate_id=corporate_id
        ).order_by('-created_at')[:limit]

        analysis_data = []
        for analysis in analyses:
            analysis_data.append({
                'id': analysis.id,
                'request_type': analysis.request_type,
                'status': analysis.status,
                'predictions': analysis.predictions if analysis.status == 'completed' else None,
                'risk_level': analysis.risk_assessment.get('overall_risk') if analysis.risk_assessment else None,
                'processing_time': analysis.processing_time_seconds,
                'model_used': {
                    'name': analysis.model_used.name,
                    'type': analysis.model_used.model_type,
                    'version': analysis.model_used.version
                } if analysis.model_used else None,
                'created_at': analysis.created_at.isoformat(),
                'updated_at': analysis.updated_at.isoformat()
            })

        return ResponseProvider(
            data={
                "analyses": analysis_data,
                "total_analyses": len(analysis_data)
            },
            message="Analysis history retrieved successfully",
            code=200
        ).success()

    except Exception as e:
        return ResponseProvider(
            message="An error occurred while retrieving analysis history",
            code=500
        ).exception()