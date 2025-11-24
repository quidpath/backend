# models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
import json
from decimal import Decimal

from OrgAuth.models import CorporateUser, Corporate
from quidpath_backend.core.base_models.base import BaseModel


class TazamaMLModel(BaseModel):
    """Store trained Tazama models and metadata"""
    MODEL_TYPES = [
        ('traditional', 'Traditional ML Model'),
        ('lstm', 'LSTM Neural Network Model'),
    ]

    name = models.CharField(max_length=100)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    version = models.CharField(max_length=20, default='1.0.0')
    model_file_path = models.FileField(upload_to='tazama_models/')
    scaler_file_path = models.FileField(upload_to='tazama_models/scalers/', null=True, blank=True)
    target_scaler_file_path = models.FileField(upload_to='tazama_models/scalers/', null=True, blank=True)
    feature_columns = models.JSONField(default=list)
    target_columns = models.JSONField(default=list)
    performance_metrics = models.JSONField(default=dict)
    training_history = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'tazama_ml_models'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.model_type}) v{self.version}"


class FinancialDataUpload(BaseModel):
    """Track uploaded financial data files"""
    UPLOAD_TYPES = [
        ('income_statement', 'Income Statement'),
        ('balance_sheet', 'Balance Sheet'),
        ('cash_flow', 'Cash Flow Statement'),
    ]

    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(CorporateUser, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    file_path = models.FileField(
        upload_to='financial_uploads/',
        validators=[FileExtensionValidator(allowed_extensions=['csv', 'xlsx', 'xls'])]
    )
    upload_type = models.CharField(max_length=20, choices=UPLOAD_TYPES)
    file_size = models.IntegerField()
    rows_processed = models.IntegerField(null=True, blank=True)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'financial_data_uploads'
        ordering = ['-created_at']


class ProcessedFinancialData(BaseModel):
    """Store processed financial data for ML training"""
    upload = models.ForeignKey(FinancialDataUpload, on_delete=models.CASCADE)
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    period_date = models.DateField()

    # Raw financial data
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cost_of_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_operating_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    operating_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    research_development = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Engineered features (calculated ratios)
    profit_margin = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    operating_margin = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    gross_margin = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    cost_revenue_ratio = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    expense_ratio = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    rd_intensity = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    revenue_growth = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    # Additional features as JSON for flexibility
    additional_features = models.JSONField(default=dict)

    # Processing metadata
    is_validated = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list)

    class Meta:
        db_table = 'processed_financial_data'
        ordering = ['-period_date']
        unique_together = ['corporate', 'period_date', 'upload']


class TazamaAnalysisRequest(BaseModel):
    """Track analysis requests made to Tazama models"""
    REQUEST_TYPES = [
        ('single_prediction', 'Single Company Prediction'),
        ('batch_analysis', 'Batch Analysis'),
        ('comparative_analysis', 'Comparative Analysis'),
    ]

    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(CorporateUser, on_delete=models.CASCADE)
    request_type = models.CharField(max_length=30, choices=REQUEST_TYPES)
    input_data = models.JSONField()  # Store the financial data used for analysis
    model_used = models.ForeignKey(TazamaMLModel, on_delete=models.SET_NULL, null=True)

    # Analysis results
    predictions = models.JSONField(default=dict)
    recommendations = models.JSONField(default=dict)
    risk_assessment = models.JSONField(default=dict)
    confidence_scores = models.JSONField(default=dict)
    truth_report = models.JSONField(default=dict)  # ✅ Brutal truth report with specific recommendations

    # Request status
    status = models.CharField(
        max_length=20,
        choices=[
            ('queued', 'Queued'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='queued'
    )
    error_message = models.TextField(null=True, blank=True)
    processing_time_seconds = models.FloatField(null=True, blank=True)


    class Meta:
        db_table = 'tazama_analysis_requests'
        ordering = ['-created_at']


class FinancialReport(BaseModel):
    """Generated financial analysis reports"""
    REPORT_TYPES = [
        ('ai_analysis', 'AI Financial Analysis'),
        ('comparative', 'Comparative Analysis'),
        ('trend_analysis', 'Trend Analysis'),
        ('risk_assessment', 'Risk Assessment Report'),
    ]

    FORMAT_CHOICES = [
        ('pdf', 'PDF Report'),
        ('json', 'JSON Data'),
        ('excel', 'Excel Workbook'),
    ]

    analysis_request = models.ForeignKey(TazamaAnalysisRequest, on_delete=models.CASCADE)
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE,related_name='financial_reports')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=255)

    # Report content
    executive_summary = models.TextField()
    detailed_analysis = models.JSONField(default=dict)
    recommendations = models.JSONField(default=dict)
    charts_data = models.JSONField(default=dict)  # Data for dashboard charts

    # File storage
    report_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='pdf')
    report_file = models.FileField(upload_to='financial_reports/', null=True, blank=True)

    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    download_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'financial_reports'
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.title} - {self.generated_at.strftime('%Y-%m-%d')}"


class ModelTrainingJob(BaseModel):
    """Track model training and retraining jobs"""
    JOB_TYPES = [
        ('initial_training', 'Initial Model Training'),
        ('incremental_training', 'Incremental Training'),
        ('full_retrain', 'Full Model Retraining'),
    ]

    job_type = models.CharField(max_length=20, choices=JOB_TYPES)
    model = models.ForeignKey(TazamaMLModel, on_delete=models.CASCADE, null=True, blank=True)
    triggered_by = models.ForeignKey(CorporateUser, on_delete=models.CASCADE)

    # Training configuration
    training_data_count = models.IntegerField(default=0)
    validation_split = models.FloatField(default=0.2)
    epochs = models.IntegerField(null=True, blank=True)
    hyperparameters = models.JSONField(default=dict)

    # Job status and results
    status = models.CharField(
        max_length=20,
        choices=[
            ('queued', 'Queued'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='queued'
    )
    progress_percentage = models.FloatField(default=0.0)
    training_metrics = models.JSONField(default=dict)
    validation_metrics = models.JSONField(default=dict)
    overfitting_analysis = models.JSONField(default=dict)

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    # Logs and errors
    training_logs = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)



    class Meta:
        db_table = 'model_training_jobs'
        ordering = ['-created_at']


class DashboardMetric(BaseModel):
    """Store aggregated metrics for dashboard display"""
    METRIC_TYPES = [
        ('prediction_accuracy', 'Prediction Accuracy'),
        ('model_performance', 'Model Performance'),
        ('data_quality', 'Data Quality Score'),
        ('risk_distribution', 'Risk Distribution'),
        ('trend_analysis', 'Trend Analysis'),
    ]

    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, blank=True, null=True)
    metric_type = models.CharField(max_length=30, choices=METRIC_TYPES)
    metric_name = models.CharField(max_length=100)
    metric_value = models.DecimalField(max_digits=10, decimal_places=4)
    metric_data = models.JSONField(default=dict)

    # Time-based grouping
    period_start = models.DateField()
    period_end = models.DateField()
    calculation_date = models.DateTimeField(auto_now_add=True)

    # Metadata
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [
            ('corporate', 'metric_type', 'metric_name', 'period_start', 'period_end')
        ]
        # Or if using constraints:
        constraints = [
            models.UniqueConstraint(
                fields=['corporate', 'metric_type', 'metric_name', 'period_start', 'period_end'],
                name='dashboard_metrics_unique'
            )
        ]

class ModelPredictionLog(BaseModel):
    """Log all predictions made by models for audit and monitoring"""
    model = models.ForeignKey(TazamaMLModel, on_delete=models.CASCADE)
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE, blank=True, null=True)

    # Input data
    input_data = models.TextField(default="")
    input_hash = models.CharField(max_length=64)

    # Prediction details
    predictions = models.JSONField()
    confidence_scores = models.JSONField(default=dict)
    processing_time_ms = models.FloatField()

    # Model state at prediction time
    model_version = models.CharField(max_length=20)
    feature_importance = models.JSONField(default=dict)

    # Feedback and validation
    actual_values = models.JSONField(null=True, blank=True)  # For later validation
    feedback_score = models.IntegerField(null=True, blank=True)  # User feedback 1-5
    is_validated = models.BooleanField(default=False)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'model_prediction_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['corporate', 'timestamp']),
            models.Index(fields=['model', 'timestamp']),
        ]


class SystemConfiguration(BaseModel):
    """Store system-wide configuration for Tazama integration"""
    CONFIG_TYPES = [
        ('model_settings', 'Model Settings'),
        ('training_config', 'Training Configuration'),
        ('api_settings', 'API Settings'),
        ('dashboard_config', 'Dashboard Configuration'),
    ]

    config_type = models.CharField(max_length=20, choices=CONFIG_TYPES)
    config_key = models.CharField(max_length=100)
    config_value = models.JSONField()
    description = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'tazama_system_config'
        unique_together = ['config_type', 'config_key']

    def __str__(self):
        return f"{self.config_type}.{self.config_key}"