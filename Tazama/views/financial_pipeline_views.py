# financial_pipeline_views.py - Enhanced Django Views for Financial Data Pipeline
"""
Django views for the enhanced financial data pipeline
Integrates with existing Tazama system for comprehensive financial analysis
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.db import transaction

from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.Logbase import TransactionLogBase

from Tazama.Services.FinancialDataPipelineService import FinancialDataPipelineService
from Tazama.Services.TazamaService import TazamaAnalysisService, ModelTrainingService
from Tazama.models import FinancialDataUpload, ProcessedFinancialData, TazamaAnalysisRequest
from OrgAuth.models import CorporateUser, Corporate


@csrf_exempt
def upload_financial_document(request):
    """
    Enhanced file upload endpoint with advanced processing
    
    Expected data:
    - file: Financial document (CSV, XLS, XLSX, ODS, TSV)
    - upload_type: 'income_statement', 'balance_sheet', 'cash_flow'
    - auto_process: Boolean to automatically process after upload
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
        corporate = Corporate.objects.get(id=corporate_id)
        corporate_user = CorporateUser.objects.get(customuser_ptr_id=user_id)
        
        # Handle file upload
        if 'file' not in request.FILES:
            return ResponseProvider(message="No file provided", code=400).bad_request()
        
        uploaded_file = request.FILES['file']
        upload_type = data.get('upload_type', 'income_statement')
        auto_process = data.get('auto_process', True)
        
        # Validate file type
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        supported_formats = ['.csv', '.xls', '.xlsx', '.ods', '.tsv']
        
        if file_extension not in supported_formats:
            return ResponseProvider(
                message=f"Unsupported file format: {file_extension}. Supported formats: {', '.join(supported_formats)}",
                code=400
            ).bad_request()
        
        # Create upload record
        upload_record = FinancialDataUpload.objects.create(
            corporate=corporate,
            uploaded_by=corporate_user,
            file_name=uploaded_file.name,
            file_path=uploaded_file,
            upload_type=upload_type,
            file_size=uploaded_file.size
        )
        
        # Process file if auto_process is enabled
        processing_result = None
        if auto_process:
            pipeline_service = FinancialDataPipelineService()
            processing_result = pipeline_service.process_uploaded_file(upload_record)
        
        # Log transaction
        TransactionLogBase.log(
            transaction_type="FINANCIAL_DOCUMENT_UPLOADED",
            user=user,
            message=f"Financial document uploaded: {uploaded_file.name}",
            state_name="Success",
            extra={
                "upload_id": upload_record.id,
                "file_name": uploaded_file.name,
                "file_size": uploaded_file.size,
                "auto_processed": auto_process,
                "processing_result": processing_result
            },
            request=request,
        )
        
        response_data = {
            "upload_id": upload_record.id,
            "file_name": uploaded_file.name,
            "file_size": uploaded_file.size,
            "upload_type": upload_type,
            "processing_status": upload_record.processing_status,
            "auto_processed": auto_process
        }
        
        if processing_result:
            response_data.update({
                "processed_tables": processing_result.get('processed_tables', 0),
                "time_series_ready": processing_result.get('time_series_ready', 0),
                "processing_success": processing_result.get('success', False)
            })
        
        return ResponseProvider(
            data=response_data,
            message="Financial document uploaded successfully",
            code=200
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="FINANCIAL_DOCUMENT_UPLOAD_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"An error occurred while uploading the document: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def process_financial_document(request):
    """
    Process an uploaded financial document with advanced pipeline
    
    Expected data:
    - upload_id: ID of the uploaded file
    - processing_options: Optional processing configuration
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
        
        upload_id = data.get('upload_id')
        if not upload_id:
            return ResponseProvider(message="Upload ID is required", code=400).bad_request()
        
        # Get upload record
        try:
            upload_record = FinancialDataUpload.objects.get(
                id=upload_id,
                corporate_id=corporate_id
            )
        except FinancialDataUpload.DoesNotExist:
            return ResponseProvider(message="Upload record not found", code=404).not_found()
        
        # Process the document
        pipeline_service = FinancialDataPipelineService()
        processing_result = pipeline_service.process_uploaded_file(upload_record)
        
        if processing_result['success']:
            TransactionLogBase.log(
                transaction_type="FINANCIAL_DOCUMENT_PROCESSED",
                user=user,
                message=f"Financial document processed successfully: {upload_record.file_name}",
                state_name="Success",
                extra={
                    "upload_id": upload_id,
                    "processed_tables": processing_result.get('processed_tables', 0),
                    "time_series_ready": processing_result.get('time_series_ready', 0)
                },
                request=request,
            )
            
            return ResponseProvider(
                data={
                    "upload_id": upload_id,
                    "processing_status": upload_record.processing_status,
                    "processed_tables": processing_result.get('processed_tables', 0),
                    "time_series_ready": processing_result.get('time_series_ready', 0),
                    "rows_processed": upload_record.rows_processed
                },
                message="Document processed successfully",
                code=200
            ).success()
        else:
            return ResponseProvider(
                message=f"Processing failed: {processing_result.get('error', 'Unknown error')}",
                code=500
            ).exception()
            
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="FINANCIAL_DOCUMENT_PROCESSING_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"An error occurred while processing the document: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def get_processing_statistics(request):
    """
    Get processing statistics for financial documents
    
    Expected data (optional):
    - start_date: Start date for statistics
    - end_date: End date for statistics
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
        
        # Get processing statistics
        pipeline_service = FinancialDataPipelineService()
        statistics = pipeline_service.get_processing_statistics(corporate_id)
        
        if 'error' in statistics:
            return ResponseProvider(
                message=f"Error retrieving statistics: {statistics['error']}",
                code=500
            ).exception()
        
        return ResponseProvider(
            data=statistics,
            message="Processing statistics retrieved successfully",
            code=200
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while retrieving statistics: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def prepare_training_data(request):
    """
    Prepare financial data for model training
    
    Expected data (optional):
    - include_all_corporates: Boolean to include data from all corporates
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
        include_all = data.get('include_all_corporates', False)
        
        # Prepare training data
        pipeline_service = FinancialDataPipelineService()
        training_data = pipeline_service.prepare_training_data(
            corporate_id if not include_all else None
        )
        
        if not training_data['success']:
            return ResponseProvider(
                message=f"Error preparing training data: {training_data.get('error', 'Unknown error')}",
                code=500
            ).exception()
        
        return ResponseProvider(
            data=training_data,
            message="Training data prepared successfully",
            code=200
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while preparing training data: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def generate_data_report(request):
    """
    Generate comprehensive data report for financial documents
    
    Expected data (optional):
    - start_date: Start date for report
    - end_date: End date for report
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
        
        # Generate data report
        pipeline_service = FinancialDataPipelineService()
        report = pipeline_service.generate_data_report(corporate_id)
        
        if not report['success']:
            return ResponseProvider(
                message=f"Error generating report: {report.get('error', 'Unknown error')}",
                code=500
            ).exception()
        
        return ResponseProvider(
            data=report,
            message="Data report generated successfully",
            code=200
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while generating the report: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def analyze_processed_data(request):
    """
    Analyze processed financial data using Tazama AI models
    
    Expected data:
    - upload_id: ID of the processed upload (optional)
    - analysis_type: Type of analysis to perform
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
        corporate = Corporate.objects.get(id=corporate_id)
        corporate_user = CorporateUser.objects.get(customuser_ptr_id=user_id)
        
        upload_id = data.get('upload_id')
        analysis_type = data.get('analysis_type', 'comprehensive')
        
        # Get processed financial data
        if upload_id:
            # Analyze specific upload
            processed_data = ProcessedFinancialData.objects.filter(
                corporate_id=corporate_id,
                upload_id=upload_id,
                is_validated=True
            ).order_by('-period_date')
        else:
            # Analyze latest data
            processed_data = ProcessedFinancialData.objects.filter(
                corporate_id=corporate_id,
                is_validated=True
            ).order_by('-period_date')[:12]  # Last 12 records
        
        if not processed_data.exists():
            return ResponseProvider(
                message="No processed financial data available for analysis",
                code=400
            ).bad_request()
        
        # Get latest financial data for analysis
        latest_data = processed_data.first()
        financial_data = {
            'totalRevenue': float(latest_data.total_revenue),
            'costOfRevenue': float(latest_data.cost_of_revenue),
            'grossProfit': float(latest_data.gross_profit),
            'totalOperatingExpenses': float(latest_data.total_operating_expenses),
            'operatingIncome': float(latest_data.operating_income),
            'netIncome': float(latest_data.net_income),
            'researchDevelopment': float(latest_data.research_development)
        }
        
        # Create analysis request
        analysis_service = TazamaAnalysisService()
        request_obj = analysis_service.create_analysis_request(
            corporate=corporate,
            user=corporate_user,
            input_data=financial_data,
            request_type=analysis_type
        )
        
        # Execute analysis
        success, message = analysis_service.run_analysis(request_obj.id)
        
        if success:
            request_obj.refresh_from_db()
            
            TransactionLogBase.log(
                transaction_type="PROCESSED_DATA_ANALYZED",
                user=user,
                message="Processed financial data analyzed successfully",
                state_name="Success",
                extra={
                    "analysis_request_id": request_obj.id,
                    "upload_id": upload_id,
                    "analysis_type": analysis_type
                },
                request=request,
            )
            
            return ResponseProvider(
                data={
                    "analysis_id": request_obj.id,
                    "predictions": request_obj.predictions,
                    "recommendations": request_obj.recommendations,
                    "risk_assessment": request_obj.risk_assessment,
                    "optimization_analysis": getattr(request_obj, 'optimization_analysis', {}),
                    "processing_time": request_obj.processing_time_seconds,
                    "data_source": "processed_financial_data",
                    "upload_id": upload_id
                },
                message="Processed data analyzed successfully",
                code=200
            ).success()
        else:
            return ResponseProvider(
                message=f"Analysis failed: {message}",
                code=500
            ).exception()
            
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="PROCESSED_DATA_ANALYSIS_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"An error occurred during analysis: {str(e)}",
            code=500
        ).exception()


@csrf_exempt
def train_model_with_processed_data(request):
    """
    Train Tazama models using processed financial data
    
    Expected data:
    - training_type: Type of training to perform
    - include_all_corporates: Boolean to include data from all corporates
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
        
        training_type = data.get('training_type', 'incremental_training')
        include_all = data.get('include_all_corporates', False)
        
        # Prepare training data
        pipeline_service = FinancialDataPipelineService()
        training_data = pipeline_service.prepare_training_data(
            corporate_id if not include_all else None
        )
        
        if not training_data['success']:
            return ResponseProvider(
                message=f"Error preparing training data: {training_data.get('error', 'Unknown error')}",
                code=500
            ).exception()
        
        # Start training job
        training_service = ModelTrainingService()
        job = training_service.start_training_job(
            job_type=training_type,
            user=user,
            corporate_id=corporate_id if not include_all else None,
            dataset=training_data['training_data']
        )
        
        TransactionLogBase.log(
            transaction_type="MODEL_TRAINING_STARTED_WITH_PROCESSED_DATA",
            user=user,
            message=f"Model training started with processed data: {training_type}",
            state_name="Success",
            extra={
                "job_id": job.id,
                "training_type": training_type,
                "include_all_corporates": include_all,
                "training_samples": training_data.get('sample_count', 0)
            },
            request=request,
        )
        
        return ResponseProvider(
            data={
                "job_id": job.id,
                "status": job.status,
                "training_type": job.job_type,
                "created_at": job.created_at.isoformat(),
                "training_samples": training_data.get('sample_count', 0),
                "data_shape": training_data.get('data_shape'),
                "message": "Model training initiated with processed financial data"
            },
            message="Model training initiated successfully",
            code=200
        ).success()
        
    except Exception as e:
        TransactionLogBase.log(
            transaction_type="MODEL_TRAINING_WITH_PROCESSED_DATA_FAILED",
            user=user,
            message=str(e),
            state_name="Failed",
            request=request,
        )
        return ResponseProvider(
            message=f"An error occurred while starting model training: {str(e)}",
            code=500
        ).exception()
