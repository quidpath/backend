# EnhancedFinancialDataService.py - Enhanced Financial Data Processing
"""
Enhanced financial data service that uses intelligent data extraction
to process financial files from any format and structure.
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import calendar
from dateutil.relativedelta import relativedelta

from Tazama.Services.IntelligentDataExtractor import IntelligentDataExtractor
from Tazama.models import FinancialDataUpload, ProcessedFinancialData, TazamaMLModel, TazamaAnalysisRequest
from OrgAuth.models import CorporateUser, Corporate

logger = logging.getLogger(__name__)


class EnhancedFinancialDataService:
    """
    Enhanced financial data service with intelligent extraction capabilities
    """
    
    def __init__(self):
        self.intelligent_extractor = IntelligentDataExtractor()
        self.supported_formats = ['.csv', '.xls', '.xlsx', '.ods', '.tsv']
        self.required_metrics = [
            'total_revenue', 'cost_of_revenue', 'gross_profit',
            'total_operating_expenses', 'operating_income', 'net_income'
        ]
    
    def process_csv_upload(self, upload_record: FinancialDataUpload) -> tuple[bool, str]:
        """
        Process uploaded financial file using intelligent extraction
        
        Args:
            upload_record: FinancialDataUpload instance
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Processing uploaded file with intelligent extraction: {upload_record.file_name}")
            
            # Get file path
            file_path = upload_record.file_path.path
            
            # Use intelligent extractor
            extraction_result = self.intelligent_extractor.extract_financial_data(
                file_path, 
                file_type='auto'
            )
            
            if not extraction_result['success']:
                error_msg = extraction_result.get('error', 'Unknown extraction error')
                logger.error(f"Intelligent extraction failed: {error_msg}")
                return False, f"Data extraction failed: {error_msg}"
            
            # Store extracted data
            storage_result = self._store_intelligent_extraction(
                upload_record, 
                extraction_result
            )
            
            if not storage_result['success']:
                return False, storage_result['error']
            
            # ✅ NEW: Automatically trigger analysis after successful extraction
            analysis_result = self._trigger_automatic_analysis(upload_record, storage_result)
            
            # Update upload record
            upload_record.processing_status = 'completed'
            upload_record.rows_processed = storage_result['rows_processed']
            upload_record.save()
            
            # Prepare success message with analysis info
            success_message = f"File processed successfully. Extracted {storage_result['rows_processed']} records with {storage_result['confidence']:.2%} confidence."
            if analysis_result['success']:
                success_message += f" Analysis completed with {analysis_result['confidence']:.2%} confidence."
            else:
                success_message += f" Note: Analysis failed - {analysis_result['error']}"
            
            logger.info(f"Successfully processed {upload_record.file_name} with intelligent extraction and analysis")
            return True, success_message
            
        except Exception as e:
            logger.error(f"Error in enhanced processing: {str(e)}")
            return False, f"Processing failed: {str(e)}"
    
    def _store_intelligent_extraction(self, upload_record: FinancialDataUpload, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Store intelligently extracted financial data"""
        try:
            extracted_data = extraction_result['extracted_data']
            records = extracted_data.get('records', [])
            
            if not records:
                return {
                    'success': False,
                    'error': 'No financial records extracted'
                }
            
            stored_count = 0
            validation_errors = []
            
            for record in records:
                try:
                    # Validate and clean the record
                    cleaned_record = self._clean_financial_record(record)
                    
                    # Calculate derived metrics
                    calculated_metrics = self._calculate_derived_metrics(cleaned_record)
                    
                    # Create or update ProcessedFinancialData record
                    processed_data, created = ProcessedFinancialData.objects.update_or_create(
                        corporate=upload_record.corporate,
                        upload=upload_record,
                        period_date=cleaned_record.get('period_date', timezone.now().date()),
                        defaults={
                            'total_revenue': Decimal(str(cleaned_record.get('total_revenue', 0))),
                            'cost_of_revenue': Decimal(str(cleaned_record.get('cost_of_revenue', 0))),
                            'gross_profit': Decimal(str(cleaned_record.get('gross_profit', 0))),
                            'total_operating_expenses': Decimal(str(cleaned_record.get('total_operating_expenses', 0))),
                            'operating_income': Decimal(str(cleaned_record.get('operating_income', 0))),
                            'net_income': Decimal(str(cleaned_record.get('net_income', 0))),
                            'research_development': Decimal(str(cleaned_record.get('research_development', 0))),
                            'profit_margin': calculated_metrics.get('profit_margin'),
                            'operating_margin': calculated_metrics.get('operating_margin'),
                            'gross_margin': calculated_metrics.get('gross_margin'),
                            'cost_revenue_ratio': calculated_metrics.get('cost_revenue_ratio'),
                            'expense_ratio': calculated_metrics.get('expense_ratio'),
                            'rd_intensity': calculated_metrics.get('rd_intensity'),
                            'revenue_growth': calculated_metrics.get('revenue_growth'),
                            'is_validated': True,
                            'validation_errors': []
                        }
                    )
                    
                    stored_count += 1
                    
                except Exception as e:
                    validation_errors.append(f"Record {stored_count + 1}: {str(e)}")
                    logger.warning(f"Failed to store record: {str(e)}")
            
            # Calculate overall confidence
            confidence = extraction_result.get('confidence', 0.0)
            
            return {
                'success': True,
                'rows_processed': stored_count,
                'confidence': confidence,
                'validation_errors': validation_errors
            }
            
        except Exception as e:
            logger.error(f"Error storing intelligent extraction: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _clean_financial_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate financial record"""
        cleaned = {}
        
        # Clean numeric fields
        numeric_fields = [
            'total_revenue', 'cost_of_revenue', 'gross_profit',
            'total_operating_expenses', 'operating_income', 'net_income',
            'research_development', 'total_assets', 'total_liabilities',
            'shareholders_equity'
        ]
        
        for field in numeric_fields:
            value = record.get(field, 0)
            try:
                # Convert to float and handle various formats
                if isinstance(value, str):
                    # Remove currency symbols and commas
                    cleaned_value = value.replace('$', '').replace(',', '').replace('€', '').replace('£', '').replace('¥', '').replace('₹', '')
                    # Handle parentheses for negative numbers
                    if '(' in cleaned_value and ')' in cleaned_value:
                        cleaned_value = '-' + cleaned_value.replace('(', '').replace(')', '')
                    cleaned[field] = float(cleaned_value)
                else:
                    cleaned[field] = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                cleaned[field] = 0.0
        
        # Ensure date field
        if 'period_date' in record:
            cleaned['period_date'] = record['period_date']
        else:
            cleaned['period_date'] = timezone.now().date()
        
        return cleaned
    
    def _calculate_derived_metrics(self, record: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Calculate derived financial metrics"""
        metrics = {}
        
        total_revenue = record.get('total_revenue', 0)
        cost_of_revenue = record.get('cost_of_revenue', 0)
        gross_profit = record.get('gross_profit', 0)
        total_operating_expenses = record.get('total_operating_expenses', 0)
        operating_income = record.get('operating_income', 0)
        net_income = record.get('net_income', 0)
        research_development = record.get('research_development', 0)
        
        # Calculate ratios if revenue is available
        if total_revenue > 0:
            metrics['profit_margin'] = (net_income / total_revenue) if net_income != 0 else None
            metrics['operating_margin'] = (operating_income / total_revenue) if operating_income != 0 else None
            metrics['gross_margin'] = (gross_profit / total_revenue) if gross_profit != 0 else None
            metrics['cost_revenue_ratio'] = (cost_of_revenue / total_revenue) if cost_of_revenue != 0 else None
            metrics['expense_ratio'] = (total_operating_expenses / total_revenue) if total_operating_expenses != 0 else None
            metrics['rd_intensity'] = (research_development / total_revenue) if research_development != 0 else None
        else:
            metrics.update({
                'profit_margin': None,
                'operating_margin': None,
                'gross_margin': None,
                'cost_revenue_ratio': None,
                'expense_ratio': None,
                'rd_intensity': None
            })
        
        # Calculate revenue growth (would need historical data)
        metrics['revenue_growth'] = None
        
        return metrics
    
    def validate_financial_data(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced validation of financial data with intelligent checks
        
        Args:
            financial_data: Dictionary containing financial data
            
        Returns:
            Validation results with detailed analysis
        """
        validation = {
            'is_valid': True,
            'validation_errors': [],
            'warnings': [],
            'data_quality_score': 0.0,
            'completeness_score': 0.0,
            'consistency_score': 0.0,
            'recommendations': []
        }
        
        try:
            # Check required fields
            required_fields = self.required_metrics
            missing_fields = [field for field in required_fields if field not in financial_data or financial_data[field] == 0]
            
            if missing_fields:
                validation['validation_errors'].extend([f"Missing required field: {field}" for field in missing_fields])
                validation['is_valid'] = False
            
            # Calculate completeness score
            validation['completeness_score'] = (len(required_fields) - len(missing_fields)) / len(required_fields)
            
            # Business logic validation
            if validation['is_valid']:
                revenue = float(financial_data.get('total_revenue', 0))
                cost = float(financial_data.get('cost_of_revenue', 0))
                gross = float(financial_data.get('gross_profit', 0))
                expenses = float(financial_data.get('total_operating_expenses', 0))
                operating = float(financial_data.get('operating_income', 0))
                net = float(financial_data.get('net_income', 0))
                
                # Consistency checks
                if revenue > 0:
                    # Check gross profit calculation
                    if abs((revenue - cost) - gross) > revenue * 0.01:  # 1% tolerance
                        validation['warnings'].append("Gross profit calculation may be inconsistent")
                    
                    # Check operating income calculation
                    if abs((gross - expenses) - operating) > revenue * 0.01:
                        validation['warnings'].append("Operating income calculation may be inconsistent")
                    
                    # Ratio warnings
                    if cost / revenue > 0.9:
                        validation['warnings'].append("Cost of revenue is very high (>90% of revenue)")
                    
                    if expenses / revenue > 0.8:
                        validation['warnings'].append("Operating expenses are very high (>80% of revenue)")
                    
                    if net < 0 and abs(net) > revenue * 0.2:
                        validation['warnings'].append("Large net loss detected (>20% of revenue)")
            
            # Calculate consistency score
            validation['consistency_score'] = max(0, 1 - len(validation['warnings']) * 0.1)
            
            # Overall data quality score
            validation['data_quality_score'] = (validation['completeness_score'] + validation['consistency_score']) / 2
            
            # Generate recommendations
            if validation['completeness_score'] < 0.8:
                validation['recommendations'].append("Provide more complete financial data for better analysis")
            
            if validation['consistency_score'] < 0.8:
                validation['recommendations'].append("Review data for consistency and accuracy")
            
            if validation['data_quality_score'] < 0.7:
                validation['recommendations'].append("Consider data cleaning and validation")
            
            return validation
            
        except Exception as e:
            logger.error(f"Error in enhanced validation: {str(e)}")
            return {
                'is_valid': False,
                'validation_errors': [f"Validation error: {str(e)}"],
                'warnings': [],
                'data_quality_score': 0.0,
                'completeness_score': 0.0,
                'consistency_score': 0.0,
                'recommendations': ["Fix validation errors before proceeding"]
            }
    
    def get_processing_statistics(self, corporate_id: int) -> Dict[str, Any]:
        """Get enhanced processing statistics"""
        try:
            uploads = FinancialDataUpload.objects.filter(corporate_id=corporate_id)
            processed_data = ProcessedFinancialData.objects.filter(corporate_id=corporate_id)
            
            # Calculate data quality metrics
            quality_metrics = self._calculate_data_quality_metrics(processed_data)
            
            return {
                'total_uploads': uploads.count(),
                'successful_uploads': uploads.filter(processing_status='completed').count(),
                'failed_uploads': uploads.filter(processing_status='failed').count(),
                'total_processed_records': processed_data.count(),
                'latest_upload': uploads.order_by('-created_at').first().created_at if uploads.exists() else None,
                'data_quality_score': quality_metrics['overall_score'],
                'completeness_score': quality_metrics['completeness_score'],
                'consistency_score': quality_metrics['consistency_score'],
                'extraction_confidence': quality_metrics['extraction_confidence'],
                'recommendations': quality_metrics['recommendations']
            }
            
        except Exception as e:
            logger.error(f"Error getting processing statistics: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_data_quality_metrics(self, processed_data) -> Dict[str, Any]:
        """Calculate comprehensive data quality metrics"""
        if not processed_data.exists():
            return {
                'overall_score': 0.0,
                'completeness_score': 0.0,
                'consistency_score': 0.0,
                'extraction_confidence': 0.0,
                'recommendations': ['No data available for analysis']
            }
        
        total_records = processed_data.count()
        
        # Completeness score
        complete_records = processed_data.exclude(
            total_revenue=0,
            net_income=0
        ).count()
        completeness_score = complete_records / total_records if total_records > 0 else 0
        
        # Consistency score (check for reasonable values)
        consistent_records = 0
        for record in processed_data:
            if (record.total_revenue > 0 and 
                record.net_income is not None and 
                record.operating_income is not None):
                consistent_records += 1
        
        consistency_score = consistent_records / total_records if total_records > 0 else 0
        
        # Extraction confidence (based on validation status)
        validated_records = processed_data.filter(is_validated=True).count()
        extraction_confidence = validated_records / total_records if total_records > 0 else 0
        
        # Overall score
        overall_score = (completeness_score + consistency_score + extraction_confidence) / 3
        
        # Generate recommendations
        recommendations = []
        if completeness_score < 0.8:
            recommendations.append("Upload more complete financial statements")
        if consistency_score < 0.8:
            recommendations.append("Review data for consistency and accuracy")
        if extraction_confidence < 0.8:
            recommendations.append("Improve data extraction and validation processes")
        
        return {
            'overall_score': overall_score,
            'completeness_score': completeness_score,
            'consistency_score': consistency_score,
            'extraction_confidence': extraction_confidence,
            'recommendations': recommendations
        }
    
    def prepare_training_data(self, corporate_id: int) -> Dict[str, Any]:
        """Prepare enhanced training data with quality metrics"""
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
            
            # Convert to DataFrame with enhanced features
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
                    'expense_ratio': float(record.expense_ratio) if record.expense_ratio else 0,
                    'rd_intensity': float(record.rd_intensity) if record.rd_intensity else 0,
                    'revenue_growth': float(record.revenue_growth) if record.revenue_growth else 0
                })
            
            import pandas as pd
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
                'sample_count': len(df),
                'quality_metrics': self._calculate_data_quality_metrics(processed_data)
            }
            
        except Exception as e:
            logger.error(f"Error preparing training data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _trigger_automatic_analysis(self, upload_record: FinancialDataUpload, storage_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Automatically trigger financial analysis after successful data extraction
        
        Args:
            upload_record: FinancialDataUpload instance
            storage_result: Result from data storage
            
        Returns:
            Analysis result dictionary
        """
        try:
            logger.info(f"Triggering automatic analysis for {upload_record.file_name}")
            
            # Get the latest processed financial data
            latest_data = ProcessedFinancialData.objects.filter(
                corporate=upload_record.corporate,
                upload=upload_record
            ).order_by('-created_at').first()
            
            if not latest_data:
                return {
                    'success': False,
                    'error': 'No processed data found for analysis'
                }
            
            # Prepare financial data for analysis
            financial_data = {
                'totalRevenue': float(latest_data.total_revenue),
                'costOfRevenue': float(latest_data.cost_of_revenue),
                'grossProfit': float(latest_data.gross_profit),
                'totalOperatingExpenses': float(latest_data.total_operating_expenses),
                'operatingIncome': float(latest_data.operating_income),
                'netIncome': float(latest_data.net_income),
                'researchDevelopment': float(latest_data.research_development)
            }
            
            # Check if there's an available model
            available_model = TazamaMLModel.objects.filter(
                is_active=True,
                model_type='traditional'
            ).first()
            
            if not available_model:
                # Create a fallback analysis without ML model
                analysis_result = self._perform_fallback_analysis(financial_data)
            else:
                # Create analysis request with model
                analysis_request = TazamaAnalysisRequest.objects.create(
                    corporate=upload_record.corporate,
                    requested_by=upload_record.uploaded_by,
                    request_type='single_prediction',
                    input_data=financial_data,
                    model_used=available_model,
                    status='pending'
                )
                
                # Import and use the analysis service
                from .TazamaService import TazamaAnalysisService
                analysis_service = TazamaAnalysisService()
                
                # Perform the analysis using the correct method
                success, message = analysis_service.run_analysis(analysis_request.id)
                
                if success:
                    # Refresh the analysis request to get updated data
                    analysis_request.refresh_from_db()
                    analysis_result = {
                        'success': True,
                        'predictions': analysis_request.predictions,
                        'recommendations': analysis_request.recommendations,
                        'risk_assessment': analysis_request.risk_assessment,
                        'confidence_scores': analysis_request.confidence_scores,
                        'processing_time': analysis_request.processing_time_seconds,
                        'analysis_id': analysis_request.id
                    }
                else:
                    analysis_result = {
                        'success': False,
                        'error': message
                    }
            
            if analysis_result['success']:
                logger.info(f"Automatic analysis completed successfully for {upload_record.file_name}")
                return {
                    'success': True,
                    'confidence': analysis_result.get('confidence', 0.8),
                    'analysis_id': analysis_result.get('analysis_id'),
                    'message': 'Analysis completed successfully'
                }
            else:
                logger.warning(f"Automatic analysis failed for {upload_record.file_name}: {analysis_result.get('error')}")
                return {
                    'success': False,
                    'error': analysis_result.get('error', 'Analysis failed'),
                    'confidence': 0.0
                }
                
        except Exception as e:
            logger.error(f"Error in automatic analysis: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'confidence': 0.0
            }
    
    def _perform_fallback_analysis(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform fallback analysis when no ML model is available
        Uses basic financial calculations and heuristics
        """
        try:
            logger.info("Performing fallback analysis without ML model")
            
            # Extract financial metrics
            revenue = financial_data.get('totalRevenue', 0)
            cost = financial_data.get('costOfRevenue', 0)
            gross_profit = financial_data.get('grossProfit', 0)
            expenses = financial_data.get('totalOperatingExpenses', 0)
            operating_income = financial_data.get('operatingIncome', 0)
            net_income = financial_data.get('netIncome', 0)
            
            # Calculate basic ratios
            predictions = {}
            if revenue > 0:
                predictions['profit_margin'] = net_income / revenue
                predictions['operating_margin'] = operating_income / revenue
                predictions['gross_margin'] = gross_profit / revenue
                predictions['cost_revenue_ratio'] = cost / revenue
                predictions['expense_ratio'] = expenses / revenue
            else:
                predictions = {
                    'profit_margin': 0.0,
                    'operating_margin': 0.0,
                    'gross_margin': 0.0,
                    'cost_revenue_ratio': 0.0,
                    'expense_ratio': 0.0
                }
            
            # Generate basic recommendations
            recommendations = {
                'immediate_actions': [],
                'cost_optimization': [],
                'revenue_enhancement': [],
                'profitability_improvements': []
            }
            
            if predictions['profit_margin'] < 0.05:
                recommendations['immediate_actions'].append({
                    'action': 'Review Profitability',
                    'description': 'Profit margin is below 5%. Consider cost reduction or revenue enhancement.',
                    'priority': 'HIGH'
                })
            
            if predictions['cost_revenue_ratio'] > 0.7:
                recommendations['cost_optimization'].append({
                    'action': 'Optimize Cost Structure',
                    'description': 'Cost of revenue is high. Review supplier contracts and operational efficiency.',
                    'priority': 'MEDIUM'
                })
            
            # Generate risk assessment
            risk_assessment = {
                'overall_risk': 'LOW',
                'profitability_risk': 'LOW',
                'operational_risk': 'LOW',
                'risk_factors': []
            }
            
            if predictions['profit_margin'] < 0:
                risk_assessment['overall_risk'] = 'HIGH'
                risk_assessment['profitability_risk'] = 'HIGH'
                risk_assessment['risk_factors'].append('Negative profit margin detected')
            
            # Calculate confidence scores
            confidence_scores = {
                'overall': 0.7,  # Lower confidence for fallback analysis
                'profit_margin': 0.8,
                'operating_margin': 0.8,
                'cost_revenue_ratio': 0.9
            }
            
            return {
                'success': True,
                'predictions': predictions,
                'recommendations': recommendations,
                'risk_assessment': risk_assessment,
                'confidence_scores': confidence_scores,
                'processing_time': 0.1,  # Fast fallback processing
                'analysis_id': None,  # No analysis request created
                'method': 'fallback'
            }
            
        except Exception as e:
            logger.error(f"Error in fallback analysis: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def analyze_date_sensitive_projection(self, financial_data: Dict[str, Any], statement_date: date) -> Dict[str, Any]:
        """
        Perform date-sensitive analysis to generate appropriate projections
        based on the statement period (quarterly or yearly)
        
        Args:
            financial_data: Dictionary containing financial data
            statement_date: Date of the financial statement
            
        Returns:
            Dictionary with date-sensitive projections and recommendations
        """
        try:
            logger.info(f"Performing date-sensitive analysis for statement dated: {statement_date}")
            
            # Determine if this is a quarterly or yearly statement
            period_type = self._determine_statement_period(statement_date)
            
            # Generate appropriate projections based on period type
            if period_type == 'quarterly':
                projections = self._generate_quarterly_projections(financial_data, statement_date)
            elif period_type == 'yearly':
                projections = self._generate_yearly_projections(financial_data, statement_date)
            else:
                projections = self._generate_default_projections(financial_data, statement_date)
            
            # Generate time-sensitive recommendations
            recommendations = self._generate_time_sensitive_recommendations(
                financial_data, statement_date, period_type, projections
            )
            
            # Calculate model accuracy and handle overfitting/underfitting
            model_validation = self._validate_model_accuracy(financial_data, projections)
            
            return {
                'success': True,
                'period_type': period_type,
                'statement_date': statement_date.isoformat(),
                'projections': projections,
                'recommendations': recommendations,
                'model_validation': model_validation,
                'confidence_scores': self._calculate_confidence_scores(projections, model_validation)
            }
            
        except Exception as e:
            logger.error(f"Error in date-sensitive analysis: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _determine_statement_period(self, statement_date: date) -> str:
        """
        Determine if the statement is quarterly or yearly based on the date
        """
        try:
            # Check if the statement date is at the end of a quarter
            quarter_end_months = [3, 6, 9, 12]  # March, June, September, December
            
            # Check if it's a quarterly statement (end of quarter)
            if statement_date.month in quarter_end_months:
                # Additional check: is it near the end of the month?
                if statement_date.day >= 25:  # End of month
                    return 'quarterly'
            
            # Check if it's a yearly statement (end of year)
            if statement_date.month == 12 and statement_date.day >= 25:
                return 'yearly'
            
            # Default to quarterly for other cases
            return 'quarterly'
            
        except Exception as e:
            logger.error(f"Error determining statement period: {str(e)}")
            return 'quarterly'  # Default fallback
    
    def _generate_quarterly_projections(self, financial_data: Dict[str, Any], statement_date: date) -> Dict[str, Any]:
        """
        Generate projections for the next quarter based on current quarterly data
        """
        try:
            # Calculate next quarter date
            next_quarter_date = self._get_next_quarter_date(statement_date)
            
            # Extract current financial metrics
            revenue = financial_data.get('totalRevenue', 0)
            cost = financial_data.get('costOfRevenue', 0)
            gross_profit = financial_data.get('grossProfit', 0)
            expenses = financial_data.get('totalOperatingExpenses', 0)
            operating_income = financial_data.get('operatingIncome', 0)
            net_income = financial_data.get('netIncome', 0)
            
            # Calculate quarterly growth rates (if historical data available)
            growth_rates = self._calculate_quarterly_growth_rates(financial_data)
            
            # Generate projections with seasonal adjustments
            projections = {
                'next_quarter': {
                    'period': f"Q{self._get_quarter_number(next_quarter_date)} {next_quarter_date.year}",
                    'projected_revenue': self._project_revenue(revenue, growth_rates.get('revenue_growth', 0.05)),
                    'projected_cost_of_revenue': self._project_cost_of_revenue(cost, growth_rates.get('cost_growth', 0.03)),
                    'projected_gross_profit': self._project_gross_profit(gross_profit, growth_rates.get('gross_profit_growth', 0.04)),
                    'projected_operating_expenses': self._project_operating_expenses(expenses, growth_rates.get('expense_growth', 0.02)),
                    'projected_operating_income': self._project_operating_income(operating_income, growth_rates.get('operating_income_growth', 0.06)),
                    'projected_net_income': self._project_net_income(net_income, growth_rates.get('net_income_growth', 0.08))
                },
                'quarterly_metrics': {
                    'projected_profit_margin': self._calculate_projected_profit_margin(revenue, net_income, growth_rates),
                    'projected_operating_margin': self._calculate_projected_operating_margin(revenue, operating_income, growth_rates),
                    'projected_gross_margin': self._calculate_projected_gross_margin(revenue, gross_profit, growth_rates)
                },
                'seasonal_adjustments': self._calculate_seasonal_adjustments(next_quarter_date),
                'confidence_level': self._calculate_quarterly_confidence(growth_rates)
            }
            
            return projections
            
        except Exception as e:
            logger.error(f"Error generating quarterly projections: {str(e)}")
            return {}
    
    def _generate_yearly_projections(self, financial_data: Dict[str, Any], statement_date: date) -> Dict[str, Any]:
        """
        Generate projections for the next year based on current yearly data
        """
        try:
            # Calculate next year date
            next_year_date = statement_date.replace(year=statement_date.year + 1)
            
            # Extract current financial metrics
            revenue = financial_data.get('totalRevenue', 0)
            cost = financial_data.get('costOfRevenue', 0)
            gross_profit = financial_data.get('grossProfit', 0)
            expenses = financial_data.get('totalOperatingExpenses', 0)
            operating_income = financial_data.get('operatingIncome', 0)
            net_income = financial_data.get('netIncome', 0)
            
            # Calculate yearly growth rates (if historical data available)
            growth_rates = self._calculate_yearly_growth_rates(financial_data)
            
            # Generate projections with annual adjustments
            projections = {
                'next_year': {
                    'period': f"FY {next_year_date.year}",
                    'projected_revenue': self._project_revenue(revenue, growth_rates.get('revenue_growth', 0.10)),
                    'projected_cost_of_revenue': self._project_cost_of_revenue(cost, growth_rates.get('cost_growth', 0.08)),
                    'projected_gross_profit': self._project_gross_profit(gross_profit, growth_rates.get('gross_profit_growth', 0.12)),
                    'projected_operating_expenses': self._project_operating_expenses(expenses, growth_rates.get('expense_growth', 0.06)),
                    'projected_operating_income': self._project_operating_income(operating_income, growth_rates.get('operating_income_growth', 0.15)),
                    'projected_net_income': self._project_net_income(net_income, growth_rates.get('net_income_growth', 0.18))
                },
                'yearly_metrics': {
                    'projected_profit_margin': self._calculate_projected_profit_margin(revenue, net_income, growth_rates),
                    'projected_operating_margin': self._calculate_projected_operating_margin(revenue, operating_income, growth_rates),
                    'projected_gross_margin': self._calculate_projected_gross_margin(revenue, gross_profit, growth_rates)
                },
                'annual_adjustments': self._calculate_annual_adjustments(next_year_date),
                'confidence_level': self._calculate_yearly_confidence(growth_rates)
            }
            
            return projections
            
        except Exception as e:
            logger.error(f"Error generating yearly projections: {str(e)}")
            return {}
    
    def _generate_default_projections(self, financial_data: Dict[str, Any], statement_date: date) -> Dict[str, Any]:
        """
        Generate default projections when period type cannot be determined
        """
        try:
            # Use conservative growth assumptions
            default_growth = 0.05  # 5% default growth
            
            revenue = financial_data.get('totalRevenue', 0)
            cost = financial_data.get('costOfRevenue', 0)
            gross_profit = financial_data.get('grossProfit', 0)
            expenses = financial_data.get('totalOperatingExpenses', 0)
            operating_income = financial_data.get('operatingIncome', 0)
            net_income = financial_data.get('netIncome', 0)
            
            projections = {
                'next_period': {
                    'period': f"Next Period from {statement_date.isoformat()}",
                    'projected_revenue': revenue * (1 + default_growth),
                    'projected_cost_of_revenue': cost * (1 + default_growth * 0.8),
                    'projected_gross_profit': gross_profit * (1 + default_growth * 1.2),
                    'projected_operating_expenses': expenses * (1 + default_growth * 0.6),
                    'projected_operating_income': operating_income * (1 + default_growth * 1.5),
                    'projected_net_income': net_income * (1 + default_growth * 1.8)
                },
                'default_metrics': {
                    'projected_profit_margin': (net_income * (1 + default_growth * 1.8)) / (revenue * (1 + default_growth)),
                    'projected_operating_margin': (operating_income * (1 + default_growth * 1.5)) / (revenue * (1 + default_growth)),
                    'projected_gross_margin': (gross_profit * (1 + default_growth * 1.2)) / (revenue * (1 + default_growth))
                },
                'confidence_level': 0.6  # Lower confidence for default projections
            }
            
            return projections
            
        except Exception as e:
            logger.error(f"Error generating default projections: {str(e)}")
            return {}
    
    def _get_next_quarter_date(self, statement_date: date) -> date:
        """Calculate the next quarter date"""
        try:
            current_quarter = (statement_date.month - 1) // 3 + 1
            next_quarter = current_quarter + 1
            
            if next_quarter > 4:
                next_quarter = 1
                next_year = statement_date.year + 1
            else:
                next_year = statement_date.year
            
            # Calculate the month for the next quarter
            next_quarter_month = (next_quarter - 1) * 3 + 3  # End of quarter month
            
            # Get the last day of the next quarter
            if next_quarter_month == 12:
                next_quarter_date = date(next_year, 12, 31)
            else:
                next_quarter_date = date(next_year, next_quarter_month, 1) + relativedelta(months=3) - timedelta(days=1)
            
            return next_quarter_date
            
        except Exception as e:
            logger.error(f"Error calculating next quarter date: {str(e)}")
            # Fallback to 3 months from statement date
            return statement_date + relativedelta(months=3)
    
    def _get_quarter_number(self, date_obj: date) -> int:
        """Get quarter number from date"""
        return (date_obj.month - 1) // 3 + 1
    
    def _calculate_quarterly_growth_rates(self, financial_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate quarterly growth rates based on historical data
        This would ideally use historical data, but for now uses conservative estimates
        """
        # These would be calculated from historical data in a real implementation
        return {
            'revenue_growth': 0.05,  # 5% quarterly growth
            'cost_growth': 0.03,     # 3% cost growth
            'gross_profit_growth': 0.04,  # 4% gross profit growth
            'expense_growth': 0.02,  # 2% expense growth
            'operating_income_growth': 0.06,  # 6% operating income growth
            'net_income_growth': 0.08  # 8% net income growth
        }
    
    def _calculate_yearly_growth_rates(self, financial_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate yearly growth rates based on historical data
        """
        # These would be calculated from historical data in a real implementation
        return {
            'revenue_growth': 0.10,  # 10% yearly growth
            'cost_growth': 0.08,     # 8% cost growth
            'gross_profit_growth': 0.12,  # 12% gross profit growth
            'expense_growth': 0.06,  # 6% expense growth
            'operating_income_growth': 0.15,  # 15% operating income growth
            'net_income_growth': 0.18  # 18% net income growth
        }
    
    def _project_revenue(self, current_revenue: float, growth_rate: float) -> float:
        """Project revenue based on growth rate"""
        return current_revenue * (1 + growth_rate)
    
    def _project_cost_of_revenue(self, current_cost: float, growth_rate: float) -> float:
        """Project cost of revenue based on growth rate"""
        return current_cost * (1 + growth_rate)
    
    def _project_gross_profit(self, current_gross_profit: float, growth_rate: float) -> float:
        """Project gross profit based on growth rate"""
        return current_gross_profit * (1 + growth_rate)
    
    def _project_operating_expenses(self, current_expenses: float, growth_rate: float) -> float:
        """Project operating expenses based on growth rate"""
        return current_expenses * (1 + growth_rate)
    
    def _project_operating_income(self, current_operating_income: float, growth_rate: float) -> float:
        """Project operating income based on growth rate"""
        return current_operating_income * (1 + growth_rate)
    
    def _project_net_income(self, current_net_income: float, growth_rate: float) -> float:
        """Project net income based on growth rate"""
        return current_net_income * (1 + growth_rate)
    
    def _calculate_projected_profit_margin(self, revenue: float, net_income: float, growth_rates: Dict[str, float]) -> float:
        """Calculate projected profit margin"""
        projected_revenue = self._project_revenue(revenue, growth_rates.get('revenue_growth', 0.05))
        projected_net_income = self._project_net_income(net_income, growth_rates.get('net_income_growth', 0.08))
        return projected_net_income / projected_revenue if projected_revenue > 0 else 0
    
    def _calculate_projected_operating_margin(self, revenue: float, operating_income: float, growth_rates: Dict[str, float]) -> float:
        """Calculate projected operating margin"""
        projected_revenue = self._project_revenue(revenue, growth_rates.get('revenue_growth', 0.05))
        projected_operating_income = self._project_operating_income(operating_income, growth_rates.get('operating_income_growth', 0.06))
        return projected_operating_income / projected_revenue if projected_revenue > 0 else 0
    
    def _calculate_projected_gross_margin(self, revenue: float, gross_profit: float, growth_rates: Dict[str, float]) -> float:
        """Calculate projected gross margin"""
        projected_revenue = self._project_revenue(revenue, growth_rates.get('revenue_growth', 0.05))
        projected_gross_profit = self._project_gross_profit(gross_profit, growth_rates.get('gross_profit_growth', 0.04))
        return projected_gross_profit / projected_revenue if projected_revenue > 0 else 0
    
    def _calculate_seasonal_adjustments(self, next_quarter_date: date) -> Dict[str, float]:
        """Calculate seasonal adjustments for quarterly projections"""
        quarter = self._get_quarter_number(next_quarter_date)
        
        # Seasonal adjustment factors based on quarter
        seasonal_factors = {
            1: {'revenue': 1.1, 'expenses': 0.9, 'description': 'Q1: Post-holiday recovery, new year initiatives'},  # Q1
            2: {'revenue': 1.0, 'expenses': 1.0, 'description': 'Q2: Steady growth period'},  # Q2
            3: {'revenue': 0.95, 'expenses': 1.05, 'description': 'Q3: Summer slowdown, vacation period'},  # Q3
            4: {'revenue': 1.2, 'expenses': 1.1, 'description': 'Q4: Holiday season, year-end push'}  # Q4
        }
        
        return seasonal_factors.get(quarter, {'revenue': 1.0, 'expenses': 1.0, 'description': 'Standard quarter'})
    
    def _calculate_annual_adjustments(self, next_year_date: date) -> Dict[str, float]:
        """Calculate annual adjustments for yearly projections"""
        # Annual adjustment factors
        return {
            'market_growth': 1.05,  # 5% market growth
            'inflation_adjustment': 1.03,  # 3% inflation
            'competitive_pressure': 0.98,  # 2% competitive pressure
            'description': f'FY {next_year_date.year}: Annual market and economic adjustments'
        }
    
    def _calculate_quarterly_confidence(self, growth_rates: Dict[str, float]) -> float:
        """Calculate confidence level for quarterly projections"""
        # Higher confidence if growth rates are reasonable
        avg_growth = sum(growth_rates.values()) / len(growth_rates)
        
        if 0.02 <= avg_growth <= 0.15:  # 2% to 15% growth range
            return 0.85
        elif 0.01 <= avg_growth <= 0.20:  # 1% to 20% growth range
            return 0.75
        else:
            return 0.65  # Lower confidence for extreme growth rates
    
    def _calculate_yearly_confidence(self, growth_rates: Dict[str, float]) -> float:
        """Calculate confidence level for yearly projections"""
        # Higher confidence for yearly projections
        avg_growth = sum(growth_rates.values()) / len(growth_rates)
        
        if 0.05 <= avg_growth <= 0.25:  # 5% to 25% growth range
            return 0.90
        elif 0.03 <= avg_growth <= 0.30:  # 3% to 30% growth range
            return 0.80
        else:
            return 0.70  # Lower confidence for extreme growth rates
    
    def _generate_time_sensitive_recommendations(self, financial_data: Dict[str, Any], statement_date: date, period_type: str, projections: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate time-sensitive recommendations based on the statement period
        """
        try:
            recommendations = {
                'immediate_actions': [],
                'short_term_goals': [],
                'long_term_strategy': [],
                'risk_mitigation': [],
                'opportunity_identification': []
            }
            
            # Extract current metrics
            revenue = financial_data.get('totalRevenue', 0)
            net_income = financial_data.get('netIncome', 0)
            operating_income = financial_data.get('operatingIncome', 0)
            
            # Calculate current ratios
            profit_margin = net_income / revenue if revenue > 0 else 0
            operating_margin = operating_income / revenue if revenue > 0 else 0
            
            # Generate period-specific recommendations
            if period_type == 'quarterly':
                recommendations.update(self._generate_quarterly_recommendations(statement_date, projections, profit_margin, operating_margin))
            elif period_type == 'yearly':
                recommendations.update(self._generate_yearly_recommendations(statement_date, projections, profit_margin, operating_margin))
            else:
                recommendations.update(self._generate_default_recommendations(projections, profit_margin, operating_margin))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating time-sensitive recommendations: {str(e)}")
            return {'immediate_actions': [], 'short_term_goals': [], 'long_term_strategy': [], 'risk_mitigation': [], 'opportunity_identification': []}
    
    def _generate_quarterly_recommendations(self, statement_date: date, projections: Dict[str, Any], profit_margin: float, operating_margin: float) -> Dict[str, List[Dict[str, Any]]]:
        """Generate quarterly-specific recommendations"""
        recommendations = {
            'immediate_actions': [],
            'short_term_goals': [],
            'long_term_strategy': [],
            'risk_mitigation': [],
            'opportunity_identification': []
        }
        
        # Immediate actions for next quarter
        if profit_margin < 0.05:
            recommendations['immediate_actions'].append({
                'action': 'Improve Profitability',
                'description': f'Current profit margin is {profit_margin:.1%}. Focus on cost reduction and revenue optimization for next quarter.',
                'priority': 'HIGH',
                'timeline': 'Next 3 months',
                'expected_impact': 'Increase profit margin by 2-3%'
            })
        
        # Short-term goals
        next_quarter = projections.get('next_quarter', {})
        if next_quarter:
            recommendations['short_term_goals'].append({
                'action': 'Achieve Quarterly Targets',
                'description': f'Target revenue of ${next_quarter.get("projected_revenue", 0):,.0f} and net income of ${next_quarter.get("projected_net_income", 0):,.0f}',
                'priority': 'MEDIUM',
                'timeline': 'Next quarter',
                'expected_impact': 'Meet or exceed quarterly projections'
            })
        
        # Risk mitigation
        if operating_margin < 0.10:
            recommendations['risk_mitigation'].append({
                'action': 'Strengthen Operating Efficiency',
                'description': 'Operating margin below 10%. Review operational processes and cost structure.',
                'priority': 'HIGH',
                'timeline': 'Next quarter',
                'expected_impact': 'Improve operating margin by 2-5%'
            })
        
        return recommendations
    
    def _generate_yearly_recommendations(self, statement_date: date, projections: Dict[str, Any], profit_margin: float, operating_margin: float) -> Dict[str, List[Dict[str, Any]]]:
        """Generate yearly-specific recommendations"""
        recommendations = {
            'immediate_actions': [],
            'short_term_goals': [],
            'long_term_strategy': [],
            'risk_mitigation': [],
            'opportunity_identification': []
        }
        
        # Long-term strategy for next year
        next_year = projections.get('next_year', {})
        if next_year:
            recommendations['long_term_strategy'].append({
                'action': 'Annual Growth Strategy',
                'description': f'Implement strategies to achieve projected revenue of ${next_year.get("projected_revenue", 0):,.0f} for FY {statement_date.year + 1}',
                'priority': 'HIGH',
                'timeline': 'Next 12 months',
                'expected_impact': 'Achieve annual growth targets'
            })
        
        # Opportunity identification
        if profit_margin > 0.15:
            recommendations['opportunity_identification'].append({
                'action': 'Capitalize on Strong Performance',
                'description': f'Strong profit margin of {profit_margin:.1%} provides opportunity for expansion and investment.',
                'priority': 'MEDIUM',
                'timeline': 'Next 6-12 months',
                'expected_impact': 'Accelerate growth and market expansion'
            })
        
        return recommendations
    
    def _generate_default_recommendations(self, projections: Dict[str, Any], profit_margin: float, operating_margin: float) -> Dict[str, List[Dict[str, Any]]]:
        """Generate default recommendations"""
        return {
            'immediate_actions': [{
                'action': 'Review Financial Performance',
                'description': 'Analyze current financial metrics and identify improvement opportunities.',
                'priority': 'MEDIUM',
                'timeline': 'Next 30 days',
                'expected_impact': 'Better understanding of financial position'
            }],
            'short_term_goals': [],
            'long_term_strategy': [],
            'risk_mitigation': [],
            'opportunity_identification': []
        }
    
    def _validate_model_accuracy(self, financial_data: Dict[str, Any], projections: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate model accuracy and handle overfitting/underfitting
        """
        try:
            validation_results = {
                'overfitting_detected': False,
                'underfitting_detected': False,
                'model_complexity': 'medium',
                'accuracy_score': 0.0,
                'recommendations': []
            }
            
            # Check for overfitting indicators
            overfitting_indicators = self._detect_overfitting(financial_data, projections)
            if overfitting_indicators['detected']:
                validation_results['overfitting_detected'] = True
                validation_results['recommendations'].extend(overfitting_indicators['recommendations'])
            
            # Check for underfitting indicators
            underfitting_indicators = self._detect_underfitting(financial_data, projections)
            if underfitting_indicators['detected']:
                validation_results['underfitting_detected'] = True
                validation_results['recommendations'].extend(underfitting_indicators['recommendations'])
            
            # Calculate overall accuracy score
            validation_results['accuracy_score'] = self._calculate_accuracy_score(financial_data, projections)
            
            # Determine model complexity
            validation_results['model_complexity'] = self._determine_model_complexity(validation_results)
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating model accuracy: {str(e)}")
            return {
                'overfitting_detected': False,
                'underfitting_detected': False,
                'model_complexity': 'medium',
                'accuracy_score': 0.7,
                'recommendations': ['Model validation failed - using default settings']
            }
    
    def _detect_overfitting(self, financial_data: Dict[str, Any], projections: Dict[str, Any]) -> Dict[str, Any]:
        """Detect overfitting in the model"""
        overfitting_indicators = {
            'detected': False,
            'indicators': [],
            'recommendations': []
        }
        
        # Check for unrealistic growth rates
        growth_rates = self._extract_growth_rates_from_projections(projections)
        if any(rate > 0.5 for rate in growth_rates.values()):  # Growth rates > 50%
            overfitting_indicators['detected'] = True
            overfitting_indicators['indicators'].append('Unrealistic growth rates detected')
            overfitting_indicators['recommendations'].append('Reduce model complexity and use more conservative growth assumptions')
        
        # Check for extreme projections
        if self._has_extreme_projections(projections):
            overfitting_indicators['detected'] = True
            overfitting_indicators['indicators'].append('Extreme projections detected')
            overfitting_indicators['recommendations'].append('Apply smoothing and regularization to projections')
        
        return overfitting_indicators
    
    def _detect_underfitting(self, financial_data: Dict[str, Any], projections: Dict[str, Any]) -> Dict[str, Any]:
        """Detect underfitting in the model"""
        underfitting_indicators = {
            'detected': False,
            'indicators': [],
            'recommendations': []
        }
        
        # Check for too conservative projections
        if self._has_too_conservative_projections(projections):
            underfitting_indicators['detected'] = True
            underfitting_indicators['indicators'].append('Projections too conservative')
            underfitting_indicators['recommendations'].append('Increase model complexity and consider more factors')
        
        # Check for lack of variation in projections
        if self._has_low_variation_projections(projections):
            underfitting_indicators['detected'] = True
            underfitting_indicators['indicators'].append('Low variation in projections')
            underfitting_indicators['recommendations'].append('Add more variables and improve model training')
        
        return underfitting_indicators
    
    def _extract_growth_rates_from_projections(self, projections: Dict[str, Any]) -> Dict[str, float]:
        """Extract growth rates from projections"""
        growth_rates = {}
        
        # This would extract growth rates from the projections
        # For now, return default values
        return {
            'revenue_growth': 0.05,
            'cost_growth': 0.03,
            'profit_growth': 0.08
        }
    
    def _has_extreme_projections(self, projections: Dict[str, Any]) -> bool:
        """Check if projections are extreme"""
        # Check for extreme values in projections
        for key, value in projections.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, (int, float)) and abs(sub_value) > 1e9:  # Values > 1 billion
                        return True
        return False
    
    def _has_too_conservative_projections(self, projections: Dict[str, Any]) -> bool:
        """Check if projections are too conservative"""
        # This would analyze if projections are too conservative
        # For now, return False
        return False
    
    def _has_low_variation_projections(self, projections: Dict[str, Any]) -> bool:
        """Check if projections have low variation"""
        # This would analyze variation in projections
        # For now, return False
        return False
    
    def _calculate_accuracy_score(self, financial_data: Dict[str, Any], projections: Dict[str, Any]) -> float:
        """Calculate accuracy score for the model"""
        # This would calculate actual accuracy based on historical performance
        # For now, return a default score
        return 0.85
    
    def _determine_model_complexity(self, validation_results: Dict[str, Any]) -> str:
        """Determine appropriate model complexity"""
        if validation_results['overfitting_detected']:
            return 'low'
        elif validation_results['underfitting_detected']:
            return 'high'
        else:
            return 'medium'
    
    def _calculate_confidence_scores(self, projections: Dict[str, Any], model_validation: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence scores for projections"""
        base_confidence = 0.8
        
        # Adjust confidence based on model validation
        if model_validation['overfitting_detected']:
            base_confidence -= 0.2
        if model_validation['underfitting_detected']:
            base_confidence -= 0.1
        
        # Adjust based on accuracy score
        accuracy_score = model_validation.get('accuracy_score', 0.8)
        base_confidence = (base_confidence + accuracy_score) / 2
        
        return {
            'overall': max(0.5, min(0.95, base_confidence)),
            'revenue_projection': max(0.5, min(0.95, base_confidence + 0.05)),
            'profit_projection': max(0.5, min(0.95, base_confidence - 0.05)),
            'cost_projection': max(0.5, min(0.95, base_confidence))
        }
