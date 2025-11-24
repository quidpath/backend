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

@admin.register(DashboardMetric)
class DashboardMetricAdmin(admin.ModelAdmin):
    list_display = ['id', 'corporate', 'metric_type', 'metric_name', 'metric_value', 'period_start', 'period_end', 'is_active']
    list_filter = ['metric_type', 'is_active', 'corporate', 'period_start']
    search_fields = ['metric_name', 'metric_type']
    readonly_fields = ['created_at', 'calculation_date']

@admin.register(ModelPredictionLog)
class ModelPredictionLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'model', 'corporate', 'model_version', 'processing_time_ms', 'is_validated', 'timestamp']
    list_filter = ['model', 'corporate', 'is_validated', 'timestamp']
    search_fields = ['model_version', 'input_hash']
    readonly_fields = ['timestamp', 'created_at']

@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ['id', 'config_type', 'config_key', 'is_active', 'created_at']
    list_filter = ['config_type', 'is_active', 'created_at']
    search_fields = ['config_key', 'description']
    readonly_fields = ['created_at', 'updated_at']
