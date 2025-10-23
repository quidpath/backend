# EnhancedFinancialDataService.py - Enhanced Financial Data Processing
"""
Enhanced financial data service that uses intelligent data extraction
to process financial files from any format and structure.
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

from Tazama.Services.IntelligentDataExtractor import IntelligentDataExtractor
from Tazama.models import FinancialDataUpload, ProcessedFinancialData, TazamaMLModel
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
                    user=upload_record.uploaded_by,
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
