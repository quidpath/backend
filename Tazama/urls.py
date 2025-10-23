from django.urls import path
from . import views

urlpatterns = [
    # Financial data upload and processing
    path('upload-financial-data/', views.upload_financial_data, name='upload_financial_data'),
    path('validate-financial-data/', views.validate_financial_data, name='validate_financial_data'),
    path('get-processed-data-history/', views.get_processed_data_history, name='get_processed_data_history'),

    # AI Analysis endpoints
    path('analyze-financial-data/', views.analyze_financial_data, name='analyze_financial_data'),
    path('get-analysis-history/', views.get_analysis_history, name='get_analysis_history'),

    # Dashboard and reporting
    path('get-financial-dashboard/', views.get_financial_dashboard, name='get_financial_dashboard'),
    path('download-analysis-report/', views.download_analysis_report, name='download_analysis_report'),

    # Model management
    path('train-model/', views.train_model, name='train_model'),
    path('get-training-status/', views.get_training_status, name='get_training_status'),
    path('get-model-performance/', views.get_model_performance, name='get_model_performance'),
    
    # Intelligent data extraction
    path('test-intelligent-extraction/', views.test_intelligent_extraction, name='test_intelligent_extraction'),
]