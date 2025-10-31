# CompleteAnalysisPipeline.py - End-to-End Analysis Pipeline
"""
Complete analysis pipeline that handles the entire workflow from data extraction
to financial analysis and results generation.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from django.utils import timezone

from Tazama.models import (
    FinancialDataUpload, ProcessedFinancialData, TazamaAnalysisRequest,
    FinancialReport, TazamaMLModel
)
from OrgAuth.models import CorporateUser, Corporate
from .IntelligentDataExtractor import IntelligentDataExtractor
from .EnhancedFinancialDataService import EnhancedFinancialDataService
from .UniversalFinancialParser import UniversalFinancialParser

logger = logging.getLogger(__name__)


class CompleteAnalysisPipeline:
    """
    Complete analysis pipeline that handles the entire workflow:
    1. Intelligent data extraction
    2. Data validation and cleaning
    3. Automatic financial analysis
    4. Results generation and storage
    """
    
    def __init__(self):
        self.intelligent_extractor = IntelligentDataExtractor()
        self.enhanced_data_service = EnhancedFinancialDataService()
        self.universal_parser = UniversalFinancialParser()
        self.pipeline_status = {
            'extraction': 'pending',
            'validation': 'pending', 
            'analysis': 'pending',
            'results': 'pending'
        }
    
    def process_complete_workflow(self, upload_record: FinancialDataUpload) -> Dict[str, Any]:
        """
        Process complete workflow from file upload to analysis results
        
        Args:
            upload_record: FinancialDataUpload instance
            
        Returns:
            Complete workflow results
        """
        try:
            logger.info(f"Starting complete analysis pipeline for {upload_record.file_name}")
            
            # Step 1: Intelligent Data Extraction
            extraction_result = self._perform_intelligent_extraction(upload_record)
            if not extraction_result['success']:
                return self._create_error_result('extraction', extraction_result['error'])
            
            # Step 2: Data Validation and Storage
            validation_result = self._perform_data_validation(upload_record, extraction_result)
            if not validation_result['success']:
                return self._create_error_result('validation', validation_result['error'])
            
            # Step 3: Automatic Financial Analysis
            analysis_result = self._perform_financial_analysis(upload_record, validation_result)
            if not analysis_result['success']:
                return self._create_error_result('analysis', analysis_result['error'])
            
            # Step 4: Results Generation and Storage
            results_result = self._generate_and_store_results(upload_record, analysis_result)
            if not results_result['success']:
                return self._create_error_result('results', results_result['error'])
            
            # Mark upload as completed and persist rows processed
            try:
                upload_record.processing_status = 'completed'
                # Prefer rows from validation_result if available
                if isinstance(validation_result, dict) and 'rows_processed' in validation_result:
                    upload_record.rows_processed = validation_result.get('rows_processed') or 0
                upload_record.save()
            except Exception as e:
                logger.warning(f"Could not update upload record completion state: {str(e)}")

            # Complete workflow summary
            return self._create_success_result(upload_record, {
                'extraction': extraction_result,
                'validation': validation_result,
                'analysis': analysis_result,
                'results': results_result
            })
            
        except Exception as e:
            logger.error(f"Error in complete analysis pipeline: {str(e)}")
            try:
                upload_record.processing_status = 'failed'
                upload_record.error_message = str(e)
                upload_record.save()
            except Exception:
                pass
            return {
                'success': False,
                'error': str(e),
                'pipeline_status': self.pipeline_status
            }
    
    def _perform_intelligent_extraction(self, upload_record: FinancialDataUpload) -> Dict[str, Any]:
        """Step 1: Perform intelligent data extraction using Universal Parser"""
        try:
            logger.info(f"Step 1: Performing intelligent extraction for {upload_record.file_name}")
            self.pipeline_status['extraction'] = 'processing'
            
            file_path = upload_record.file_path.path
            
            # Use Universal Parser for robust extraction
            try:
                parse_result = self.universal_parser.parse_file(file_path)
                
                if parse_result.get('success'):
                    # Convert to format expected by downstream pipeline
                    structured_data = parse_result['structured_data']
                    metrics = structured_data['current_metrics']
                    metadata = structured_data['metadata']
                    
                    extraction_result = {
                        'success': True,
                        'confidence': 0.95,  # High confidence from universal parser
                        'extracted_data': {
                            'sheet_0': {
                                'metrics': {
                                    'totalRevenue': metrics.get('total_revenue', 0),
                                    'costOfRevenue': metrics.get('cost_of_revenue', 0),
                                    'grossProfit': metrics.get('gross_profit', 0),
                                    'totalOperatingExpenses': metrics.get('total_operating_expenses', 0),
                                    'operatingIncome': metrics.get('operating_income', 0),
                                    'netIncome': metrics.get('net_income', 0),
                                    'researchDevelopment': 0,
                                    # Include ratios
                                    'profit_margin': metrics.get('profit_margin', 0) / 100,
                                    'operating_margin': metrics.get('operating_margin', 0) / 100,
                                    'gross_margin': metrics.get('gross_margin', 0) / 100,
                                    'expense_ratio': metrics.get('expense_ratio', 0) / 100,
                                },
                                'confidence': 0.95,
                                'period_info': metadata.get('period', {}),
                                'statement_type': metadata.get('statement_type'),
                                'currency': metadata.get('currency', 'KES')
                            }
                        },
                        'metadata': metadata,
                        'projections': structured_data.get('projections', {})
                    }
                    
                    self.pipeline_status['extraction'] = 'completed'
                    logger.info(f"Universal parser extraction completed successfully")
                    return extraction_result
                    
            except Exception as parser_error:
                logger.warning(f"Universal parser failed: {str(parser_error)}, falling back to legacy extractor")
            
            # Fallback to legacy extractor if universal parser fails
            extraction_result = self.intelligent_extractor.extract_financial_data(
                file_path, 
                file_type='auto'
            )
            
            if extraction_result['success']:
                self.pipeline_status['extraction'] = 'completed'
                logger.info(f"Legacy extraction completed with {extraction_result.get('confidence', 0):.2%} confidence")
            else:
                self.pipeline_status['extraction'] = 'failed'
                logger.error(f"Intelligent extraction failed: {extraction_result.get('error')}")
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Error in intelligent extraction: {str(e)}")
            self.pipeline_status['extraction'] = 'failed'
            return {
                'success': False,
                'error': str(e)
            }
    
    def _perform_data_validation(self, upload_record: FinancialDataUpload, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Step 2: Perform data validation and storage"""
        try:
            logger.info(f"Step 2: Performing data validation for {upload_record.file_name}")
            self.pipeline_status['validation'] = 'processing'
            
            # Store extracted data using enhanced service
            storage_result = self.enhanced_data_service._store_intelligent_extraction(
                upload_record, 
                extraction_result
            )
            
            if storage_result['success']:
                self.pipeline_status['validation'] = 'completed'
                logger.info(f"Data validation and storage completed: {storage_result['rows_processed']} records")
            else:
                self.pipeline_status['validation'] = 'failed'
                logger.error(f"Data validation failed: {storage_result['error']}")
            
            return storage_result
            
        except Exception as e:
            logger.error(f"Error in data validation: {str(e)}")
            self.pipeline_status['validation'] = 'failed'
            return {
                'success': False,
                'error': str(e)
            }
    
    def _perform_financial_analysis(self, upload_record: FinancialDataUpload, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Step 3: Perform financial analysis"""
        try:
            logger.info(f"Step 3: Performing financial analysis for {upload_record.file_name}")
            self.pipeline_status['analysis'] = 'processing'
            
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
                self.pipeline_status['analysis'] = 'completed'
                logger.info(f"Financial analysis completed successfully")
            else:
                self.pipeline_status['analysis'] = 'failed'
                logger.error(f"Financial analysis failed: {analysis_result.get('error')}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in financial analysis: {str(e)}")
            self.pipeline_status['analysis'] = 'failed'
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_and_store_results(self, upload_record: FinancialDataUpload, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Step 4: Generate and store analysis results"""
        try:
            logger.info(f"Step 4: Generating and storing results for {upload_record.file_name}")
            self.pipeline_status['results'] = 'processing'
            
            # Get the existing analysis request or create a new one if fallback was used
            analysis_request = None
            if analysis_result.get('analysis_id'):
                try:
                    analysis_request = TazamaAnalysisRequest.objects.get(id=analysis_result['analysis_id'])
                except TazamaAnalysisRequest.DoesNotExist:
                    analysis_request = None
            
            if not analysis_request:
                # Create analysis request record for fallback analysis
                analysis_request = TazamaAnalysisRequest.objects.create(
                    corporate=upload_record.corporate,
                    requested_by=upload_record.uploaded_by,
                    request_type='single_prediction',
                    input_data=analysis_result.get('input_data', {}),
                    predictions=analysis_result.get('predictions', {}),
                    recommendations=analysis_result.get('recommendations', {}),
                    risk_assessment=analysis_result.get('risk_assessment', {}),
                    confidence_scores=analysis_result.get('confidence_scores', {}),
                    processing_time_seconds=analysis_result.get('processing_time', 0),
                    status='completed'
                )
            
            # Generate comprehensive report
            report_result = self._generate_comprehensive_report(upload_record, analysis_request, analysis_result)
            
            if report_result['success']:
                self.pipeline_status['results'] = 'completed'
                logger.info(f"Results generation completed successfully")
            else:
                self.pipeline_status['results'] = 'failed'
                logger.error(f"Results generation failed: {report_result['error']}")
            
            return {
                'success': True,
                'analysis_id': analysis_request.id,
                'analysis_request': analysis_request,
                'report_result': report_result,
                'message': 'Complete analysis pipeline finished successfully'
            }
            
        except Exception as e:
            logger.error(f"Error in results generation: {str(e)}")
            self.pipeline_status['results'] = 'failed'
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_comprehensive_report(self, upload_record: FinancialDataUpload, analysis_request: TazamaAnalysisRequest, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive analysis report"""
        try:
            # Create financial report
            # Map to FinancialReport fields (no 'content' field)
            formatted_text = self._format_report_content(analysis_result)
            report = FinancialReport.objects.create(
                corporate=upload_record.corporate,
                analysis_request=analysis_request,
                report_type='ai_analysis',
                title=f"Financial Analysis Report - {upload_record.file_name}",
                executive_summary=formatted_text,
                detailed_analysis=analysis_result.get('predictions', {}),
                recommendations=analysis_result.get('recommendations', {}),
                charts_data={
                    'risk_assessment': analysis_result.get('risk_assessment', {}),
                    'confidence_scores': analysis_result.get('confidence_scores', {})
                },
                report_format='json'
            )
            
            return {
                'success': True,
                'report_id': report.id,
                'report': report
            }
            
        except Exception as e:
            logger.error(f"Error generating comprehensive report: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_report_content(self, analysis_result: Dict[str, Any]) -> str:
        """Format analysis results into readable report content"""
        try:
            content = f"""
# Financial Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Analysis Summary
- **Status**: {'✅ Completed Successfully' if analysis_result.get('success') else '❌ Failed'}
- **Confidence**: {analysis_result.get('confidence', 0):.2%}
- **Processing Time**: {analysis_result.get('processing_time', 0):.2f} seconds

## Key Metrics
"""
            
            # Add predictions
            predictions = analysis_result.get('predictions', {})
            if predictions:
                content += "\n### Financial Predictions\n"
                for metric, value in predictions.items():
                    content += f"- **{metric.replace('_', ' ').title()}**: {value:.4f}\n"
            
            # Add recommendations
            recommendations = analysis_result.get('recommendations', {})
            if recommendations:
                content += "\n### Recommendations\n"
                for category, items in recommendations.items():
                    if isinstance(items, list) and items:
                        content += f"\n#### {category.replace('_', ' ').title()}\n"
                        for item in items[:3]:  # Show first 3 items
                            if isinstance(item, dict):
                                content += f"- **{item.get('action', 'Action')}**: {item.get('description', 'No description')}\n"
                            else:
                                content += f"- {item}\n"
            
            # Add risk assessment
            risk_assessment = analysis_result.get('risk_assessment', {})
            if risk_assessment:
                content += "\n### Risk Assessment\n"
                content += f"- **Overall Risk**: {risk_assessment.get('overall_risk', 'Unknown')}\n"
                content += f"- **Profitability Risk**: {risk_assessment.get('profitability_risk', 'Unknown')}\n"
                content += f"- **Operational Risk**: {risk_assessment.get('operational_risk', 'Unknown')}\n"
            
            return content
            
        except Exception as e:
            logger.error(f"Error formatting report content: {str(e)}")
            return f"Error generating report content: {str(e)}"
    
    def _create_success_result(self, upload_record: FinancialDataUpload, results: Dict[str, Any]) -> Dict[str, Any]:
        """Create success result for complete workflow"""
        return {
            'success': True,
            'message': f'Complete analysis pipeline finished successfully for {upload_record.file_name}',
            'pipeline_status': self.pipeline_status,
            'results': {
                'extraction_confidence': results['extraction'].get('confidence', 0),
                'validation_records': results['validation'].get('rows_processed', 0),
                'analysis_success': results['analysis'].get('success', False),
                'results_generated': results['results'].get('success', False)
            },
            'analysis_id': results['results'].get('analysis_id'),
            'report_id': results['results'].get('report_result', {}).get('report_id'),
            'timestamp': timezone.now().isoformat()
        }
    
    def _create_error_result(self, failed_step: str, error_message: str) -> Dict[str, Any]:
        """Create error result for failed workflow"""
        return {
            'success': False,
            'error': f'Pipeline failed at {failed_step} step: {error_message}',
            'pipeline_status': self.pipeline_status,
            'failed_step': failed_step,
            'timestamp': timezone.now().isoformat()
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
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status"""
        return {
            'pipeline_status': self.pipeline_status,
            'overall_status': 'completed' if all(status == 'completed' for status in self.pipeline_status.values()) else 'in_progress',
            'timestamp': timezone.now().isoformat()
        }
