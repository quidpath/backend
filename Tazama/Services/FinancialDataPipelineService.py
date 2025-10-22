# FinancialDataPipelineService.py - Django Integration Service
"""
Django service for integrating the financial data pipeline with Tazama
Handles file uploads, processing, and model training integration
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone

from Tazama.core.financial_data_pipeline import FinancialDataPipeline
from Tazama.models import FinancialDataUpload, ProcessedFinancialData, TazamaMLModel
from OrgAuth.models import CorporateUser, Corporate

logger = logging.getLogger(__name__)


class FinancialDataPipelineService:
    """Django service for financial data pipeline integration"""
    
    def __init__(self):
        self.pipeline = FinancialDataPipeline()
        self.supported_formats = ['.csv', '.xls', '.xlsx', '.ods', '.tsv']
    
    def process_uploaded_file(self, upload_record: FinancialDataUpload) -> Dict[str, Any]:
        """
        Process an uploaded financial file using the pipeline
        
        Args:
            upload_record: FinancialDataUpload instance
            
        Returns:
            Dictionary with processing results
        """
        try:
            logger.info(f"Processing uploaded file: {upload_record.file_name}")
            
            # Get file path
            file_path = upload_record.file_path.path
            
            # Process the file
            result = self.pipeline.process_file(file_path)
            
            if result['success']:
                # Store processed data in database
                self._store_processed_data(upload_record, result)
                
                # Update upload record
                upload_record.processing_status = 'completed'
                upload_record.rows_processed = self._count_processed_rows(result)
                upload_record.save()
                
                logger.info(f"Successfully processed {upload_record.file_name}")
                return {
                    'success': True,
                    'message': 'File processed successfully',
                    'processed_tables': len(result.get('financial_tables', {})),
                    'time_series_ready': len(result.get('time_series_data', {}))
                }
            else:
                # Update upload record with error
                upload_record.processing_status = 'failed'
                upload_record.error_message = result.get('error', 'Unknown error')
                upload_record.save()
                
                logger.error(f"Failed to process {upload_record.file_name}: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }
                
        except Exception as e:
            logger.error(f"Error processing file {upload_record.file_name}: {str(e)}")
            
            # Update upload record with error
            upload_record.processing_status = 'failed'
            upload_record.error_message = str(e)
            upload_record.save()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _store_processed_data(self, upload_record: FinancialDataUpload, result: Dict[str, Any]):
        """Store processed financial data in the database"""
        try:
            financial_tables = result.get('financial_tables', {})
            time_series_data = result.get('time_series_data', {})
            
            for sheet_name, table_info in financial_tables.items():
                df = table_info['data']
                
                # Create ProcessedFinancialData record for each row
                for index, row in df.iterrows():
                    # Extract financial metrics
                    financial_data = self._extract_financial_metrics(row, table_info)
                    
                    # Create or update record
                    ProcessedFinancialData.objects.update_or_create(
                        corporate=upload_record.corporate,
                        upload=upload_record,
                        period_date=self._extract_period_date(row, table_info),
                        defaults=financial_data
                    )
            
            logger.info(f"Stored {len(financial_tables)} financial tables in database")
            
        except Exception as e:
            logger.error(f"Error storing processed data: {str(e)}")
            raise
    
    def _extract_financial_metrics(self, row: pd.Series, table_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract financial metrics from a data row"""
        metrics = {}
        
        # Map common financial metrics
        metric_mapping = {
            'total_revenue': ['revenue', 'sales', 'total_revenue', 'net_sales'],
            'cost_of_revenue': ['cost_of_revenue', 'cogs', 'cost_of_goods_sold'],
            'gross_profit': ['gross_profit', 'gross_income'],
            'total_operating_expenses': ['operating_expenses', 'total_operating_expenses', 'opex'],
            'operating_income': ['operating_income', 'operating_profit', 'ebit'],
            'net_income': ['net_income', 'net_profit', 'net_earnings'],
            'research_development': ['research_development', 'rd', 'r&d']
        }
        
        for metric_name, possible_columns in metric_mapping.items():
            value = self._find_metric_value(row, possible_columns)
            if value is not None:
                metrics[metric_name] = value
        
        # Calculate derived metrics
        if 'total_revenue' in metrics and metrics['total_revenue'] != 0:
            if 'cost_of_revenue' in metrics:
                metrics['gross_profit'] = metrics['total_revenue'] - metrics['cost_of_revenue']
            
            if 'gross_profit' in metrics and 'total_operating_expenses' in metrics:
                metrics['operating_income'] = metrics['gross_profit'] - metrics['total_operating_expenses']
            
            if 'operating_income' in metrics:
                metrics['net_income'] = metrics['operating_income']  # Simplified
        
        return metrics
    
    def _find_metric_value(self, row: pd.Series, possible_columns: List[str]) -> Optional[float]:
        """Find a metric value from possible column names"""
        for col_name in possible_columns:
            for col in row.index:
                if col_name.lower() in str(col).lower():
                    try:
                        value = float(row[col])
                        if not pd.isna(value):
                            return value
                    except (ValueError, TypeError):
                        continue
        return None
    
    def _extract_period_date(self, row: pd.Series, table_info: Dict[str, Any]) -> datetime.date:
        """Extract period date from row data"""
        date_columns = table_info.get('date_columns', [])
        
        for col in date_columns:
            if col in row.index and not pd.isna(row[col]):
                try:
                    if isinstance(row[col], pd.Timestamp):
                        return row[col].date()
                    else:
                        return pd.to_datetime(row[col]).date()
                except:
                    continue
        
        # Default to current date if no date found
        return timezone.now().date()
    
    def _count_processed_rows(self, result: Dict[str, Any]) -> int:
        """Count total processed rows"""
        total_rows = 0
        for table_info in result.get('financial_tables', {}).values():
            total_rows += table_info['data'].shape[0]
        return total_rows
    
    def get_processing_statistics(self, corporate_id: int) -> Dict[str, Any]:
        """Get processing statistics for a corporate"""
        try:
            uploads = FinancialDataUpload.objects.filter(corporate_id=corporate_id)
            processed_data = ProcessedFinancialData.objects.filter(corporate_id=corporate_id)
            
            return {
                'total_uploads': uploads.count(),
                'successful_uploads': uploads.filter(processing_status='completed').count(),
                'failed_uploads': uploads.filter(processing_status='failed').count(),
                'total_processed_records': processed_data.count(),
                'latest_upload': uploads.order_by('-created_at').first().created_at if uploads.exists() else None,
                'data_quality_score': self._calculate_data_quality_score(processed_data)
            }
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_data_quality_score(self, processed_data) -> float:
        """Calculate data quality score"""
        if not processed_data.exists():
            return 0.0
        
        total_records = processed_data.count()
        complete_records = processed_data.exclude(
            total_revenue=0,
            net_income=0
        ).count()
        
        return complete_records / total_records if total_records > 0 else 0.0
    
    def prepare_training_data(self, corporate_id: int) -> Dict[str, Any]:
        """Prepare data for model training"""
        try:
            # Get processed financial data
            processed_data = ProcessedFinancialData.objects.filter(
                corporate_id=corporate_id,
                is_validated=True
            ).order_by('period_date')
            
            if not processed_data.exists():
                return {
                    'success': False,
                    'error': 'No validated financial data available for training'
                }
            
            # Convert to DataFrame
            training_data = []
            for record in processed_data:
                training_data.append({
                    'date': record.period_date,
                    'total_revenue': float(record.total_revenue),
                    'cost_of_revenue': float(record.cost_of_revenue),
                    'gross_profit': float(record.gross_profit),
                    'operating_income': float(record.operating_income),
                    'net_income': float(record.net_income),
                    'research_development': float(record.research_development),
                    'profit_margin': float(record.profit_margin) if record.profit_margin else 0,
                    'operating_margin': float(record.operating_margin) if record.operating_margin else 0,
                    'cost_revenue_ratio': float(record.cost_revenue_ratio) if record.cost_revenue_ratio else 0,
                    'expense_ratio': float(record.expense_ratio) if record.expense_ratio else 0
                })
            
            df = pd.DataFrame(training_data)
            
            if df.empty:
                return {
                    'success': False,
                    'error': 'No valid training data available'
                }
            
            # Prepare for model training
            df = df.set_index('date').sort_index()
            
            return {
                'success': True,
                'training_data': df,
                'data_shape': df.shape,
                'date_range': {
                    'start': df.index.min().isoformat(),
                    'end': df.index.max().isoformat()
                },
                'features': list(df.columns),
                'sample_count': len(df)
            }
            
        except Exception as e:
            logger.error(f"Error preparing training data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_data_report(self, corporate_id: int) -> Dict[str, Any]:
        """Generate comprehensive data report"""
        try:
            processed_data = ProcessedFinancialData.objects.filter(corporate_id=corporate_id)
            
            if not processed_data.exists():
                return {
                    'success': False,
                    'error': 'No processed data available'
                }
            
            # Calculate statistics
            total_revenue = processed_data.aggregate(
                total=Sum('total_revenue')
            )['total'] or 0
            
            avg_profit_margin = processed_data.aggregate(
                avg=Avg('profit_margin')
            )['avg'] or 0
            
            # Get date range
            date_range = processed_data.aggregate(
                min_date=Min('period_date'),
                max_date=Max('period_date')
            )
            
            # Calculate trends
            recent_data = processed_data.order_by('-period_date')[:12]
            if len(recent_data) >= 2:
                latest = recent_data[0]
                previous = recent_data[1]
                
                revenue_growth = ((latest.total_revenue - previous.total_revenue) / previous.total_revenue * 100) if previous.total_revenue > 0 else 0
                profit_growth = ((latest.net_income - previous.net_income) / abs(previous.net_income) * 100) if previous.net_income != 0 else 0
            else:
                revenue_growth = 0
                profit_growth = 0
            
            return {
                'success': True,
                'report': {
                    'total_records': processed_data.count(),
                    'date_range': date_range,
                    'total_revenue': float(total_revenue),
                    'average_profit_margin': float(avg_profit_margin),
                    'revenue_growth': float(revenue_growth),
                    'profit_growth': float(profit_growth),
                    'data_quality': self._calculate_data_quality_score(processed_data),
                    'recommendations': self._generate_data_recommendations(processed_data)
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating data report: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_data_recommendations(self, processed_data) -> List[str]:
        """Generate recommendations based on data analysis"""
        recommendations = []
        
        # Check data completeness
        total_records = processed_data.count()
        complete_records = processed_data.exclude(
            total_revenue=0,
            net_income=0
        ).count()
        
        if complete_records / total_records < 0.8:
            recommendations.append("Data completeness is low. Consider uploading more complete financial statements.")
        
        # Check for recent data
        latest_date = processed_data.order_by('-period_date').first().period_date
        days_since_latest = (timezone.now().date() - latest_date).days
        
        if days_since_latest > 90:
            recommendations.append("Data is outdated. Consider uploading more recent financial statements.")
        
        # Check for sufficient data for training
        if total_records < 12:
            recommendations.append("Insufficient data for reliable model training. Consider uploading more historical data.")
        
        return recommendations


# Import required modules
import pandas as pd
from django.db.models import Sum, Avg, Min, Max
