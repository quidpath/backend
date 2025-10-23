# views.py - Django views for Tazama integration
import json
import os

import numpy as np
import pandas as pd
from decimal import Decimal
from datetime import datetime, date, timedelta

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
from .Services.EnhancedFinancialDataService import EnhancedFinancialDataService
from .core.TazamaCore import FinancialDataProcessor
from .core.report_generator import TazamaReportGenerator

from .models import (
    FinancialDataUpload, ProcessedFinancialData, TazamaAnalysisRequest,
    FinancialReport, TazamaMLModel, ModelTrainingJob, DashboardMetric, ModelPredictionLog
)

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

        # Process the file using enhanced intelligent extraction
        enhanced_data_service = EnhancedFinancialDataService()
        success, message = enhanced_data_service.process_csv_upload(upload_record)

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
                    "status": upload_record.processing_status
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

        # Get financial data
        financial_data = data.get('financial_data')
        upload_id = data.get('upload_id')
        analysis_type = data.get('analysis_type', 'single_prediction')

        if not financial_data and not upload_id:
            return ResponseProvider(message="Either financial_data or upload_id must be provided",
                                    code=400).bad_request()

        # If upload_id is provided, get the latest processed data
        if upload_id:
            try:
                upload_record = FinancialDataUpload.objects.get(id=upload_id, corporate_id=corporate.id)
                latest_data = ProcessedFinancialData.objects.filter(
                    upload=upload_record
                ).order_by('-period_date').first()

                if not latest_data:
                    return ResponseProvider(message="No processed data found for this upload", code=400).bad_request()

                financial_data = {
                    'totalRevenue': float(latest_data.total_revenue),
                    'costOfRevenue': float(latest_data.cost_of_revenue),
                    'grossProfit': float(latest_data.gross_profit),
                    'totalOperatingExpenses': float(latest_data.total_operating_expenses),
                    'operatingIncome': float(latest_data.operating_income),
                    'netIncome': float(latest_data.net_income),
                    'researchDevelopment': float(latest_data.research_development),
                }
            except FinancialDataUpload.DoesNotExist:
                return ResponseProvider(message="Upload record not found", code=404).not_found()

        # ✅ CRITICAL FIX: Calculate ALL features that the model expects
        total_revenue = financial_data.get('totalRevenue', 0)
        cost_of_revenue = financial_data.get('costOfRevenue', 0)
        gross_profit = financial_data.get('grossProfit', 0)
        total_expenses = financial_data.get('totalOperatingExpenses', 0)
        operating_income = financial_data.get('operatingIncome', 0)
        net_income = financial_data.get('netIncome', 0)
        rd_expenses = financial_data.get('researchDevelopment', 0)

        if total_revenue > 0:
            financial_data['profit_margin'] = (net_income / total_revenue)
            financial_data['operating_margin'] = (operating_income / total_revenue)
            financial_data['cost_revenue_ratio'] = (cost_of_revenue / total_revenue)
            financial_data['expense_ratio'] = (total_expenses / total_revenue)
            financial_data['gross_margin'] = (gross_profit / total_revenue)
            financial_data['rd_intensity'] = (rd_expenses / total_revenue)
            financial_data['revenue_per_expense'] = (total_revenue / max(total_expenses, 1))
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

        # Create analysis request
        analysis_service = TazamaAnalysisService()
        request_obj = analysis_service.create_analysis_request(
            corporate=corporate,
            user=corporate_user,
            input_data=financial_data,
            request_type=analysis_type
        )

        # Update request object with validated features
        request_obj.input_data = financial_data
        request_obj.save()

        # Execute analysis
        success, message = analysis_service.run_analysis(request_obj.id)

        if success:
            request_obj.refresh_from_db()

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

            return ResponseProvider(
                data={
                    "analysis_id": request_obj.id,
                    "predictions": request_obj.predictions,
                    "recommendations": request_obj.recommendations,
                    "risk_assessment": request_obj.risk_assessment,
                    "confidence_scores": request_obj.confidence_scores,
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
        else:
            return ResponseProvider(message=f"Analysis failed: {message}", code=500).exception()

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
    Get dashboard data for financial analysis visualization

    Expected data (optional):
    - start_date: Start date for metrics calculation
    - end_date: End date for metrics calculation
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

        # Parse dates
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = date.today() - timedelta(days=365)  # Last year by default

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = date.today()

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
            analyses_data.append({
                'id': analysis.id,
                'date': analysis.created_at.date().isoformat(),
                'datetime': analysis.created_at.isoformat(),
                'predictions': analysis.predictions or {},
                'input_data': analysis.input_data or {},  # ✅ ADD: Include actual cash figures
                'recommendations_count': len(analysis.recommendations.get('immediate_actions', [])) if analysis.recommendations else 0,
                'risk_level': analysis.risk_assessment.get('overall_risk', 'LOW') if analysis.risk_assessment else 'LOW',
                'risk_factors_count': len(analysis.risk_assessment.get('risk_factors', [])) if analysis.risk_assessment else 0,
                'processing_time': round(analysis.processing_time_seconds, 2) if analysis.processing_time_seconds else 0,
                'confidence_scores': analysis.confidence_scores or {},
                'model_info': {
                    'name': analysis.model_used.name,
                    'type': analysis.model_used.model_type,
                    'version': analysis.model_used.version
                } if analysis.model_used else None
            })

        # ✅ Get uploads summary with proper counts
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

        failed_uploads = FinancialDataUpload.objects.filter(
            corporate_id=corporate_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            processing_status='failed'
        ).count()

        # ✅ Get model performance data
        available_models = TazamaMLModel.objects.filter(is_active=True)
        models_data = []
        for model in available_models:
            # Count predictions made by this model
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

        # ✅ Calculate trends with proper data aggregation
        trend_data = []
        for analysis in reversed(analyses_data):  # Chronological order for trends
            trend_data.append({
                'date': analysis['date'],
                'profit_margin': analysis['predictions'].get('profit_margin', 0),
                'operating_margin': analysis['predictions'].get('operating_margin', 0),
                'cost_revenue_ratio': analysis['predictions'].get('cost_revenue_ratio', 0),
                'expense_ratio': analysis['predictions'].get('expense_ratio', 0),
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
                else:
                    changes[metric] = {
                        'current': round(current, 4),
                        'previous': 0,
                        'change': round(current, 4),
                        'change_percentage': None
                    }

        # ✅ Get processed data statistics
        processed_data_count = ProcessedFinancialData.objects.filter(
            corporate_id=corporate_id,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).count()

        latest_processed_data = ProcessedFinancialData.objects.filter(
            corporate_id=corporate_id
        ).order_by('-period_date').first()

        dashboard_data = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days_in_period': (end_date - start_date).days
            },
            'summary': {
                'total_analyses': total_analyses,
                'average_predictions': average_predictions,
                'risk_distribution': risk_distribution,
                'uploads': {
                    'total': total_uploads,
                    'successful': successful_uploads,
                    'failed': failed_uploads
                },
                'processed_records': processed_data_count,
                'latest_analysis_date': latest_analysis.created_at.isoformat() if latest_analysis else None,
                'latest_data_period': latest_processed_data.period_date.isoformat() if latest_processed_data else None
            },
            'period_over_period_changes': changes,
            'recent_analyses': analyses_data,
            'available_models': models_data,
            'trends': {
                'data': trend_data,
                'metrics': ['profit_margin', 'operating_margin', 'cost_revenue_ratio', 'expense_ratio'],
                'dates': [item['date'] for item in trend_data]
            },
            'insights': {
                'most_common_risk_level': max(risk_distribution.items(), key=lambda x: x[1])[0] if total_analyses > 0 else None,
                'average_processing_time': round(
                    sum(a.processing_time_seconds or 0 for a in all_analyses) / total_analyses, 2
                ) if total_analyses > 0 else 0,
                'analyses_per_day': round(total_analyses / max((end_date - start_date).days, 1), 2)
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
            message="Dashboard data retrieved successfully",
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

        df_quarterly = pd.read_csv(quarterly_path)
        df_quarterly["frequency"] = "quarterly"

        dataset = pd.concat([df_annual, df_quarterly], ignore_index=True)

        # Optional preprocessing
        dataset = dataset.dropna(how="all")  # drop fully empty rows

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