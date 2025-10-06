from django.contrib import admin

from django.contrib import admin
from .models import (
    TazamaMLModel, FinancialDataUpload, ProcessedFinancialData,
    TazamaAnalysisRequest, FinancialReport, ModelTrainingJob,
    DashboardMetric, ModelPredictionLog, SystemConfiguration
)

@admin.register(TazamaMLModel)
class TazamaMLModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'model_type', 'version', 'is_active', 'created_at']
    list_filter = ['model_type', 'is_active', 'created_at']
    search_fields = ['name', 'version']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(FinancialDataUpload)
class FinancialDataUploadAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'corporate_id', 'upload_type', 'processing_status', 'rows_processed', 'created_at']
    list_filter = ['upload_type', 'processing_status', 'created_at']
    search_fields = ['file_name', 'corporate_id']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ProcessedFinancialData)
class ProcessedFinancialDataAdmin(admin.ModelAdmin):
    list_display = ['corporate_id', 'period_date', 'total_revenue', 'net_income', 'profit_margin', 'is_validated']
    list_filter = ['is_validated', 'period_date']
    search_fields = ['corporate_id']
    readonly_fields = ['created_at']

@admin.register(TazamaAnalysisRequest)
class TazamaAnalysisRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'corporate_id', 'request_type', 'status', 'processing_time_seconds', 'created_at']
    list_filter = ['request_type', 'status', 'created_at']
    search_fields = ['corporate_id']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ModelTrainingJob)
class ModelTrainingJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'job_type', 'status', 'progress_percentage', 'training_data_count', 'duration_seconds']
    list_filter = ['job_type', 'status', 'started_at']
    readonly_fields = ['created_at', 'started_at', 'completed_at']

@admin.register(FinancialReport)
class FinancialReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'corporate_id', 'report_type', 'report_format', 'download_count', 'generated_at']
    list_filter = ['report_type', 'report_format', 'generated_at']
    search_fields = ['title', 'corporate_id']
