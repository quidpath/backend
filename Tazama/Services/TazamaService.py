# services.py - Core business logic for Tazama integration
# FIXED VERSION - All corporate_id references changed to corporate

import os
import json
import pandas as pd
import numpy as np
from decimal import Decimal
import torch
import joblib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import logging
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from requests.compat import chardet

from OrgAuth.models import CorporateUser, Corporate
from Tazama.core.TazamaCore import FinancialDataProcessor, UnifiedFinancialModels, MultiTargetLSTM, \
    EnhancedFinancialOptimizer
from Tazama.models import TazamaMLModel, FinancialDataUpload, ProcessedFinancialData, TazamaAnalysisRequest, \
    ModelPredictionLog, ModelTrainingJob, DashboardMetric

logger = logging.getLogger(__name__)


class TazamaModelService:
    """Service for managing Tazama ML models"""

    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.processor = FinancialDataProcessor()
        self.models_cache = {}

    def load_model(self, model_id: int) -> Optional[Any]:
        """Load a trained model from database"""
        try:
            if model_id in self.models_cache:
                return self.models_cache[model_id]

            model_record = TazamaMLModel.objects.get(id=model_id, is_active=True)

            if model_record.model_type == 'traditional':
                # Load traditional model
                model = joblib.load(model_record.model_file_path.path)
                feature_scaler = joblib.load(
                    model_record.scaler_file_path.path) if model_record.scaler_file_path else None
                target_scaler = joblib.load(
                    model_record.target_scaler_file_path.path) if model_record.target_scaler_file_path else None

                unified_model = UnifiedFinancialModels(model_record.target_columns)
                unified_model.traditional_model = model
                if feature_scaler:
                    unified_model.feature_scaler = feature_scaler
                if target_scaler:
                    unified_model.target_scaler = target_scaler

                self.models_cache[model_id] = unified_model
                return unified_model

            elif model_record.model_type == 'lstm':
                # Load LSTM model
                model_info_path = model_record.model_file_path.path.replace('.pth', '_info.json')
                with open(model_info_path, 'r') as f:
                    model_info = json.load(f)

                lstm_model = MultiTargetLSTM(
                    input_size=model_info['input_size'],
                    hidden_size=model_info['hidden_size'],
                    num_layers=model_info['num_layers'],
                    output_size=model_info['output_size']
                ).to(self.device)

                lstm_model.load_state_dict(torch.load(model_record.model_file_path.path, map_location=self.device))

                unified_model = UnifiedFinancialModels(model_record.target_columns)
                unified_model.lstm_model = lstm_model
                unified_model.lstm_feature_scaler = joblib.load(model_record.scaler_file_path.path)
                unified_model.lstm_target_scaler = joblib.load(model_record.target_scaler_file_path.path)

                self.models_cache[model_id] = unified_model
                return unified_model

        except Exception as e:
            logger.error(f"Error loading model {model_id}: {str(e)}")
            return None

    def get_active_model(self, model_type: str = 'traditional') -> Optional[TazamaMLModel]:
        """Get the most recent active model of specified type"""
        return TazamaMLModel.objects.filter(
            model_type=model_type,
            is_active=True
        ).order_by('-created_at').first()

    def save_model(self, unified_model: UnifiedFinancialModels, name: str, version: str) -> TazamaMLModel:
        """Save a trained model to database"""
        models_dir = os.path.join(settings.MEDIA_ROOT, 'tazama_models')
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(os.path.join(models_dir, 'scalers'), exist_ok=True)

        # Save traditional model
        if unified_model.traditional_model:
            model_path = os.path.join(models_dir, f'{name}_traditional_v{version}.joblib')
            scaler_path = os.path.join(models_dir, 'scalers', f'{name}_traditional_feature_scaler_v{version}.joblib')
            target_scaler_path = os.path.join(models_dir, 'scalers',
                                              f'{name}_traditional_target_scaler_v{version}.joblib')

            joblib.dump(unified_model.traditional_model, model_path)
            joblib.dump(unified_model.feature_scaler, scaler_path)
            joblib.dump(unified_model.target_scaler, target_scaler_path)

            model_record = TazamaMLModel.objects.create(
                name=f"{name}_traditional",
                model_type='traditional',
                version=version,
                model_file_path=f'tazama_models/{name}_traditional_v{version}.joblib',
                scaler_file_path=f'tazama_models/scalers/{name}_traditional_feature_scaler_v{version}.joblib',
                target_scaler_file_path=f'tazama_models/scalers/{name}_traditional_target_scaler_v{version}.joblib',
                feature_columns=self.processor.feature_columns,
                target_columns=unified_model.target_columns,
                performance_metrics=unified_model.training_history.get('traditional', {}),
                training_history=unified_model.training_history
            )

        # Save LSTM model
        if unified_model.lstm_model:
            model_path = os.path.join(models_dir, f'{name}_lstm_v{version}.pth')
            scaler_path = os.path.join(models_dir, 'scalers', f'{name}_lstm_feature_scaler_v{version}.joblib')
            target_scaler_path = os.path.join(models_dir, 'scalers', f'{name}_lstm_target_scaler_v{version}.joblib')
            info_path = os.path.join(models_dir, f'{name}_lstm_v{version}_info.json')

            torch.save(unified_model.lstm_model.state_dict(), model_path)
            joblib.dump(unified_model.lstm_feature_scaler, scaler_path)
            joblib.dump(unified_model.lstm_target_scaler, target_scaler_path)

            # Save model architecture info
            model_info = {
                'input_size': unified_model.lstm_model.lstm.input_size,
                'hidden_size': unified_model.lstm_model.hidden_size,
                'num_layers': unified_model.lstm_model.num_layers,
                'output_size': len(unified_model.target_columns),
                'target_columns': unified_model.target_columns
            }
            with open(info_path, 'w') as f:
                json.dump(model_info, f)

            model_record = TazamaMLModel.objects.create(
                name=f"{name}_lstm",
                model_type='lstm',
                version=version,
                model_file_path=f'tazama_models/{name}_lstm_v{version}.pth',
                scaler_file_path=f'tazama_models/scalers/{name}_lstm_feature_scaler_v{version}.joblib',
                target_scaler_file_path=f'tazama_models/scalers/{name}_lstm_target_scaler_v{version}.joblib',
                feature_columns=self.processor.feature_columns,
                target_columns=unified_model.target_columns,
                performance_metrics=unified_model.training_history.get('lstm', {}).get('metrics', {}),
                training_history=unified_model.training_history
            )

        return model_record


class FinancialDataService:
    """Service for processing uploaded financial data"""

    def __init__(self):
        self.processor = FinancialDataProcessor()

    def detect_encoding(self, file_path: str) -> str:
        """Detect the encoding of a file using chardet"""
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(10000)  # Read first 10KB for detection
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8'  # Fallback to utf-8
        except Exception as e:
            return 'latin1'  # Fallback to latin1 if detection fails

    def process_csv_upload(self, upload_record: FinancialDataUpload) -> Tuple[bool, str]:
        """Process uploaded CSV or Excel file and extract financial data"""
        try:
            upload_record.processing_status = 'processing'
            upload_record.save()

            file_path = upload_record.file_path.path
            try:
                if file_path.endswith('.csv'):
                    # Detect encoding for CSV files
                    encoding = self.detect_encoding(file_path)
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                    except UnicodeDecodeError:
                        # Fallback to latin1 if detected encoding fails
                        df = pd.read_csv(file_path, encoding='latin1')
                elif file_path.endswith(('.xlsx', '.xls')):
                    # Excel files handle encoding internally
                    df = pd.read_excel(file_path, engine='openpyxl' if file_path.endswith('.xlsx') else 'xlrd')
                else:
                    return False, "Unsupported file format. Only CSV, XLS, and XLSX are supported."
            except Exception as e:
                return False, f"Error reading file: {str(e)}"

            # Validate required columns
            required_columns = [
                'totalRevenue', 'costOfRevenue', 'grossProfit',
                'totalOperatingExpenses', 'operatingIncome',
                'netIncome', 'researchDevelopment'
            ]

            # Check for period date column
            date_columns = ['date', 'period_date', 'endDate', 'reportDate']
            date_column = None
            for col in date_columns:
                if col in df.columns:
                    date_column = col
                    break

            if not date_column:
                return False, "No valid date column found. Expected one of: " + ", ".join(date_columns)

            # Process each row
            processed_count = 0
            errors = []

            for index, row in df.iterrows():
                try:
                    # Parse date
                    period_date = pd.to_datetime(row[date_column]).date()

                    # Create base financial data with defaults
                    financial_data = {}
                    for col in required_columns:
                        financial_data[col] = float(row.get(col, 0))

                    # Process using Tazama processor
                    processed_df = self.processor._create_financial_features(pd.DataFrame([financial_data]))
                    processed_row = processed_df.iloc[0]

                    # Update or create processed financial data
                    ProcessedFinancialData.objects.update_or_create(
                        corporate=upload_record.corporate,
                        period_date=period_date,
                        upload=upload_record,
                        defaults={
                            'total_revenue': Decimal(str(financial_data['totalRevenue'])),
                            'cost_of_revenue': Decimal(str(financial_data['costOfRevenue'])),
                            'gross_profit': Decimal(str(financial_data['grossProfit'])),
                            'total_operating_expenses': Decimal(str(financial_data['totalOperatingExpenses'])),
                            'operating_income': Decimal(str(financial_data['operatingIncome'])),
                            'net_income': Decimal(str(financial_data['netIncome'])),
                            'research_development': Decimal(str(financial_data['researchDevelopment'])),
                            'profit_margin': Decimal(str(processed_row.get('profit_margin', 0))),
                            'operating_margin': Decimal(str(processed_row.get('operating_margin', 0))),
                            'gross_margin': Decimal(str(processed_row.get('gross_margin', 0))),
                            'cost_revenue_ratio': Decimal(str(processed_row.get('cost_revenue_ratio', 0))),
                            'expense_ratio': Decimal(str(processed_row.get('expense_ratio', 0))),
                            'rd_intensity': Decimal(str(processed_row.get('rd_intensity', 0))),
                            'revenue_growth': Decimal(str(processed_row.get('revenue_growth', 0))),
                            'additional_features': processed_row.to_dict(),
                            'is_validated': True
                        }
                    )
                    processed_count += 1

                except Exception as e:
                    errors.append(f"Row {index}: {str(e)}")

            # Update upload record
            upload_record.rows_processed = processed_count
            upload_record.processing_status = 'completed' if not errors else 'failed'
            upload_record.error_message = "; ".join(errors) if errors else None
            upload_record.save()

            return True, f"Successfully processed {processed_count} rows"

        except Exception as e:
            upload_record.processing_status = 'failed'
            upload_record.error_message = f"File processing error: {str(e)}"
            upload_record.save()
            return False, f"File processing error: {str(e)}"


class TazamaAnalysisService:
    """Service for running financial analysis using Tazama models"""

    def __init__(self):
        self.model_service = TazamaModelService()

    def run_analysis(self, request_id: int) -> Tuple[bool, str]:
        """Execute analysis request"""
        try:
            request_obj = TazamaAnalysisRequest.objects.get(id=request_id)
            request_obj.status = 'processing'
            request_obj.save()

            start_time = datetime.now()

            # Load the model
            model = self.model_service.load_model(request_obj.model_used.id)
            if not model:
                raise Exception("Failed to load model")

            # Create optimizer
            optimizer = EnhancedFinancialOptimizer(
                models=model,
                feature_columns=request_obj.model_used.feature_columns,
                target_columns=request_obj.model_used.target_columns
            )

            # Run analysis
            analysis_results = optimizer.analyze_income_statement(request_obj.input_data)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            # ✅ FIXED: Use corporate instead of corporate_id
            input_hash = hashlib.sha256(json.dumps(request_obj.input_data, sort_keys=True).encode()).hexdigest()
            ModelPredictionLog.objects.create(
                model=request_obj.model_used,
                corporate=request_obj.corporate,
                input_hash=input_hash,
                predictions=analysis_results['predictions'],
                confidence_scores=analysis_results.get('confidence_scores', {}),
                processing_time_ms=processing_time * 1000,
                model_version=request_obj.model_used.version
            )

            # Update request with results
            request_obj.predictions = analysis_results['predictions']
            request_obj.recommendations = analysis_results['recommendations']
            request_obj.risk_assessment = analysis_results['risk_assessment']
            request_obj.confidence_scores = analysis_results.get('confidence_scores', {})
            request_obj.processing_time_seconds = processing_time
            request_obj.status = 'completed'
            request_obj.save()

            return True, "Analysis completed successfully"

        except Exception as e:
            request_obj.status = 'failed'
            request_obj.error_message = str(e)
            request_obj.save()
            return False, str(e)

    def create_analysis_request(self, corporate, user, input_data: Dict,
                                request_type: str = 'single_prediction') -> TazamaAnalysisRequest:
        """Create a new analysis request"""

        if not isinstance(corporate, Corporate):
            raise ValueError("corporate must be a Corporate model instance")

        if not isinstance(user, CorporateUser):
            raise ValueError("user must be a CorporateUser model instance")

        # Get the best available model
        model = self.model_service.get_active_model('traditional')
        if not model:
            model = self.model_service.get_active_model('lstm')

        if not model:
            raise Exception("No trained models available")

        request_obj = TazamaAnalysisRequest.objects.create(
            corporate=corporate,
            requested_by=user,
            request_type=request_type,
            input_data=input_data,
            model_used=model
        )

        return request_obj


class ModelTrainingService:
    """Service for training and retraining models"""

    def __init__(self):
        self.model_service = TazamaModelService()
        self.data_service = FinancialDataService()

    def start_training_job(
            self,
            job_type: str,
            user,
            corporate_id: Optional[int] = None,
            dataset: Optional[pd.DataFrame] = None
    ) -> ModelTrainingJob:
        """Start a new model training job"""

        # Ensure user is a CorporateUser instance
        if isinstance(user, CorporateUser):
            corporate_user = user
        else:
            user_id = user.get("id") if isinstance(user, dict) else getattr(user, 'id', None)

            if not user_id:
                raise ValueError("User ID not found")

            try:
                corporate_user = CorporateUser.objects.get(customuser_ptr_id=user_id)
            except CorporateUser.DoesNotExist:
                raise ValueError("Provided user is not a CorporateUser and cannot be resolved")

        job = ModelTrainingJob.objects.create(
            job_type=job_type,
            triggered_by=corporate_user,
            status='queued'
        )

        # Queue the job for background processing
        self._execute_training_job(job.id, corporate_id, dataset=dataset)

        return job

    def _execute_training_job(
            self,
            job_id: int,
            corporate_id: Optional[int] = None,
            dataset: Optional[pd.DataFrame] = None
    ):
        """Execute training job (should be run in background task)"""
        try:
            job = ModelTrainingJob.objects.get(id=job_id)
            job.status = 'running'
            job.started_at = timezone.now()
            job.save()

            # If dataset provided, use it instead of DB query
            if dataset is not None:
                df = dataset.copy()
                if 'symbol' not in df.columns:
                    if 'corporate_id' in df.columns:
                        df['symbol'] = df['corporate_id'].astype(str)
                    else:
                        df['symbol'] = 'UNKNOWN'
                else:
                    df['symbol'] = df['symbol'].astype(str)
            else:
                # ✅ FIXED: Use corporate instead of corporate_id in filter
                if corporate_id:
                    training_data = ProcessedFinancialData.objects.filter(
                        corporate_id=corporate_id,  # This is OK - Django ORM allows this
                        is_validated=True
                    ).order_by('period_date')
                else:
                    training_data = ProcessedFinancialData.objects.filter(
                        is_validated=True
                    ).order_by('period_date')

                if len(training_data) < 50:
                    raise Exception(f"Insufficient training data: {len(training_data)} records (minimum 50 required)")

                df_data = []
                for record in training_data:
                    df_data.append({
                        'corporate_id': record.corporate.id,  # ✅ Changed from record.corporate_id
                        'date': record.period_date,
                        'totalRevenue': float(record.total_revenue),
                        'costOfRevenue': float(record.cost_of_revenue),
                        'grossProfit': float(record.gross_profit),
                        'totalOperatingExpenses': float(record.total_operating_expenses),
                        'operatingIncome': float(record.operating_income),
                        'netIncome': float(record.net_income),
                        'researchDevelopment': float(record.research_development),
                    })

                df = pd.DataFrame(df_data)
                df['symbol'] = df['corporate_id'].astype(str)

            # Validate minimum data requirements
            if len(df) < 50:
                raise Exception(f"Insufficient training data: {len(df)} records (minimum 50 required)")

            # Check for required columns
            required_cols = ['totalRevenue', 'costOfRevenue', 'grossProfit',
                             'totalOperatingExpenses', 'operatingIncome', 'netIncome']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise Exception(f"Missing required columns: {', '.join(missing_cols)}")

            # Remove rows with all NaN values in required columns
            df = df.dropna(subset=required_cols, how='all')

            # Fill remaining NaN values with 0 for numeric columns
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].fillna(0)

            if len(df) < 50:
                raise Exception(f"After cleaning, insufficient training data: {len(df)} records (minimum 50 required)")

            # Continue with processor + models
            processor = FinancialDataProcessor()
            df = processor._create_financial_features(df)

            # Validate processed dataframe
            if df.empty:
                raise Exception("Feature creation resulted in empty dataframe")

            processor.feature_columns = [
                'profit_margin', 'gross_margin', 'operating_margin',
                'cost_revenue_ratio', 'expense_ratio', 'rd_intensity',
                'revenue_per_expense'
            ]

            # Ensure all feature columns exist in dataframe
            available_features = [col for col in processor.feature_columns if col in df.columns]
            if not available_features:
                raise Exception("No feature columns found in processed dataframe")

            processor.feature_columns = available_features

            X, y, metadata = processor.prepare_features_and_targets(df)

            # Validate X and y
            if X.empty or y.empty:
                raise Exception("Feature preparation resulted in empty training data")

            job.training_data_count = len(X)
            job.save()

            models = UnifiedFinancialModels(processor.target_columns)
            traditional_metrics = models.train_traditional_models(X, y)

            lstm_df = X.copy()
            lstm_df['symbol'] = metadata['symbol']
            lstm_df['date'] = metadata['date']
            for i, target_col in enumerate(processor.target_columns):
                lstm_df[target_col] = y.iloc[:, i]

            lstm_metrics = models.train_lstm_model(lstm_df)

            model_name = f"tazama_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            version = "1.0.0"
            saved_model = self.model_service.save_model(models, model_name, version)

            job.model = saved_model
            job.training_metrics = traditional_metrics
            job.validation_metrics = lstm_metrics if lstm_metrics else {}
            job.overfitting_analysis = models.training_history.get('lstm', {})
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
            job.save()

        except Exception as e:
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = timezone.now()
            if job.started_at:
                job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
            job.save()
            logger.error(f"Training job {job_id} failed: {str(e)}")


class DashboardService:
    """Service for generating dashboard metrics and data"""

    def calculate_dashboard_metrics(self, corporate_id: int, start_date, end_date):
        """Calculate and cache dashboard metrics"""
        analysis_requests = TazamaAnalysisRequest.objects.filter(
            corporate_id=corporate_id,
            status='completed',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )

        if not analysis_requests.exists():
            return {}

        # Calculate aggregated metrics
        total_predictions = analysis_requests.count()
        risk_levels = [req.risk_assessment.get('overall_risk', 'LOW') for req in analysis_requests]

        risk_distribution = {
            'HIGH': risk_levels.count('HIGH') / total_predictions * 100,
            'MEDIUM': risk_levels.count('MEDIUM') / total_predictions * 100,
            'LOW': risk_levels.count('LOW') / total_predictions * 100,
        }

        # Average predictions
        avg_predictions = {}
        prediction_keys = ['profit_margin', 'operating_margin', 'cost_revenue_ratio', 'expense_ratio']

        for key in prediction_keys:
            values = []
            for req in analysis_requests:
                if key in req.predictions:
                    values.append(float(req.predictions[key]))
            avg_predictions[key] = sum(values) / len(values) if values else 0

        corporate = Corporate.objects.get(id=corporate_id)

        # Store/update dashboard metrics
        DashboardMetric.objects.update_or_create(
            corporate=corporate,
            metric_type='risk_distribution',
            metric_name='Risk Distribution',  # ← Add this to lookup
            period_start=start_date,
            period_end=end_date,
            defaults={
                'metric_value': Decimal(str(risk_distribution['HIGH'])),
                'metric_data': risk_distribution
            }
        )

        # ✅ FIX: Move metric_name to lookup parameters
        for key, value in avg_predictions.items():
            DashboardMetric.objects.update_or_create(
                corporate=corporate,
                metric_type='prediction_accuracy',
                metric_name=key,  # ← This must be in lookup, not defaults
                period_start=start_date,
                period_end=end_date,
                defaults={
                    'metric_value': Decimal(str(value)),
                    'metric_data': {'average': value, 'count': total_predictions}
                }
            )

        return {
            'risk_distribution': risk_distribution,
            'average_predictions': avg_predictions,
            'total_analyses': total_predictions
        }