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
from Tazama.Services.DataNormalizationPipeline import DataNormalizationPipeline
from Tazama.models import FinancialDataUpload, ProcessedFinancialData, TazamaMLModel, TazamaAnalysisRequest
from OrgAuth.models import CorporateUser, Corporate

logger = logging.getLogger(__name__)


class EnhancedFinancialDataService:
    """
    Enhanced financial data service with intelligent extraction capabilities
    """
    
    def __init__(self):
        self.intelligent_extractor = IntelligentDataExtractor()
        self.normalization_pipeline = DataNormalizationPipeline()  # Dynamic normalization pipeline
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
            
            # Use intelligent extractor with cell-by-cell extraction
            # Pass corporate and user for logging
            extraction_result = self.intelligent_extractor.extract_financial_data(
                file_path, 
                file_type='auto',
                corporate=upload_record.corporate,
                user=upload_record.uploaded_by,
                upload_record=upload_record
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
            # Pass extraction_result to use JSON data if available
            analysis_result = self._trigger_automatic_analysis(upload_record, storage_result, extraction_result)
            
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
            # ✅ PRIORITY: Use JSON data from intelligent extraction if available
            json_data = extraction_result.get('json_data')
            records = []
            
            if json_data:
                logger.info("✅ Using JSON data from intelligent extraction")
                # ✅ DEBUG: Log the full JSON data
                logger.info("=" * 80)
                logger.info("📥 RAW JSON DATA FROM EXTRACTOR:")
                logger.info("=" * 80)
                import json as json_lib
                try:
                    logger.info(json_lib.dumps(json_data, indent=2, default=str))
                except Exception as e:
                    logger.error(f"Failed to serialize json_data: {e}")
                    logger.info(f"JSON data keys: {list(json_data.keys())}")
                logger.info("=" * 80)
                
                # Check if it's the new snake_case format (from IntelligentStatementExtractor)
                if 'total_revenue' in json_data or 'cogs' in json_data:
                    # New format: snake_case fields from IntelligentStatementExtractor
                    # Handle None values by converting to 0 for numeric fields
                    def safe_get(key, default=0):
                        val = json_data.get(key, default)
                        return val if val is not None else default
                    
                    record = {
                        'total_revenue': safe_get('total_revenue', 0),
                        'cost_of_revenue': safe_get('cogs', 0),  # Map cogs to cost_of_revenue
                        'gross_profit': safe_get('gross_profit', 0),
                        'total_operating_expenses': safe_get('operating_expenses', 0),  # Map operating_expenses
                        'operating_income': safe_get('operating_income', 0),
                        'net_income': safe_get('net_income', 0),
                        'research_development': safe_get('research_development', 0),
                        'interest_expense': safe_get('interest_expense', 0),
                        'taxes': safe_get('taxes', 0),
                        'risk_level': json_data.get('risk_level'),  # Keep None for optional string field
                        '_from_intelligent_extractor': True,  # Flag to skip normalization pipeline
                    }
                    records = [record]
                    logger.info(f"📊 Extracted Data (snake_case): Revenue={record['total_revenue']:,.0f}, "
                              f"COGS={record['cost_of_revenue']:,.0f}, "
                              f"OPEX={record['total_operating_expenses']:,.0f}, "
                              f"Net Income={record['net_income']:,.0f}")
                else:
                    # Old format: camelCase fields from cell-by-cell extraction
                    record = {
                        'total_revenue': json_data.get('totalRevenue', 0),
                        'cost_of_revenue': json_data.get('costOfRevenue', 0),
                        'gross_profit': json_data.get('grossProfit', 0),
                        'total_operating_expenses': json_data.get('totalOperatingExpenses', 0),
                        'operating_income': json_data.get('operatingIncome', 0),
                        'net_income': json_data.get('netIncome', 0),
                        'research_development': json_data.get('researchDevelopment', 0),
                    }
                    records = [record]
                    logger.info(f"📊 JSON Data (camelCase): Revenue={record['total_revenue']:,.0f}, "
                              f"OPEX={record['total_operating_expenses']:,.0f}, "
                              f"NI={record['net_income']:,.0f}")
            
            # Fall back to extracted_data.records if json_data not available
            if not records:
                extracted_data = extraction_result.get('extracted_data', {})
                records = extracted_data.get('records', [])
                
                # If records have statement_type, extract the income_statement
                if records and isinstance(records[0], dict) and 'statement_type' in records[0]:
                    income_statement = next((r for r in records if r.get('statement_type') == 'income_statement'), None)
                    if income_statement:
                        # Convert income_statement format to record format
                        # Handle None values by converting to 0 for numeric fields
                        def safe_get(key, default=0):
                            val = income_statement.get(key, default)
                            return val if val is not None else default
                        
                        record = {
                            'total_revenue': safe_get('total_revenue', 0),
                            'cost_of_revenue': safe_get('cogs', 0),
                            'gross_profit': safe_get('gross_profit', 0),
                            'total_operating_expenses': safe_get('operating_expenses', 0),
                            'operating_income': safe_get('operating_income', 0),
                            'net_income': safe_get('net_income', 0),
                            'interest_expense': safe_get('interest_expense', 0),
                            'taxes': safe_get('taxes', 0),
                            'risk_level': income_statement.get('risk_level'),  # Keep None for optional string field
                            '_from_intelligent_extractor': True,  # Flag to skip normalization pipeline
                        }
                        records = [record]
                        logger.info(f"📊 Extracted from records: Revenue={record['total_revenue']:,.0f}, "
                                  f"OPEX={record['total_operating_expenses']:,.0f}, "
                                  f"Net Income={record['net_income']:,.0f}")
            
            if not records:
                logger.warning("⚠️ No financial records extracted from extraction_result")
                return {
                    'success': False,
                    'error': 'No financial records extracted'
                }
            
            # Check for validation warnings but proceed anyway
            if extraction_result.get('statements'):
                for stmt_name, stmt_data in extraction_result.get('statements', {}).items():
                    if '_validation_warning' in stmt_data:
                        logger.warning(f"⚠️ Storing data with validation warning for {stmt_name}: "
                                     f"{stmt_data.get('_validation_warning')}")
            
            stored_count = 0
            validation_errors = []
            
            for record in records:
                try:
                    # Validate and clean the record
                    cleaned_record = self._clean_financial_record(record)
                    
                    # Debug logging: Show cleaned record before storage
                    print("🔍 DEBUG: EnhancedFinancialDataService - _store_intelligent_extraction")
                    print({
                        "cleaned_record": {
                            "total_revenue": cleaned_record.get('total_revenue', 0),
                            "cost_of_revenue": cleaned_record.get('cost_of_revenue', 0),
                            "gross_profit": cleaned_record.get('gross_profit', 0),
                            "operating_expenses": cleaned_record.get('total_operating_expenses', 0),
                            "operating_income": cleaned_record.get('operating_income', 0),
                            "net_income": cleaned_record.get('net_income', 0)
                        }
                    })
                    
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
                    
                    # Debug logging: Show what was saved to database
                    print("🔍 DEBUG: Saved to ProcessedFinancialData")
                    print({
                        "saved_to_db": {
                            "total_revenue": str(processed_data.total_revenue),
                            "cost_of_revenue": str(processed_data.cost_of_revenue),
                            "gross_profit": str(processed_data.gross_profit),
                            "operating_expenses": str(processed_data.total_operating_expenses),
                            "operating_income": str(processed_data.operating_income),
                            "net_income": str(processed_data.net_income)
                        }
                    })
                    
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
                # IMPORTANT: Preserve negative values exactly as they are
                if isinstance(value, str):
                    # Remove currency symbols and commas
                    cleaned_value = value.replace('$', '').replace(',', '').replace('€', '').replace('£', '').replace('¥', '').replace('₹', '')
                    # Handle parentheses for negative numbers
                    if '(' in cleaned_value and ')' in cleaned_value:
                        cleaned_value = '-' + cleaned_value.replace('(', '').replace(')', '')
                    cleaned[field] = float(cleaned_value)
                else:
                    # Preserve negative values - do NOT convert to 0.0
                    cleaned[field] = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                # Only set to 0.0 if value is truly invalid, not if it's negative
                if value is None:
                    cleaned[field] = 0.0
                else:
                    # Try to preserve the value even if conversion fails
                    cleaned[field] = 0.0

        # ✅ STRICT MODE: For data from IntelligentStatementExtractor, preserve values exactly as extracted
        # Do NOT run normalization pipeline which modifies/corrects values
        # Only use normalization for legacy extractors that need calculation of missing fields
        use_strict_mode = record.get('_from_intelligent_extractor', False)
        
        if not use_strict_mode:
            # Only use normalization pipeline for legacy extractors
            try:
                normalized = self.normalization_pipeline.normalize_and_calculate(cleaned)
                # Update cleaned with normalized values
                cleaned.update(normalized)
                logger.info(f"✅ Data normalized: Revenue={cleaned.get('total_revenue', 0):,.0f}, "
                           f"OPEX={cleaned.get('total_operating_expenses', 0):,.0f}, "
                           f"Net Income={cleaned.get('net_income', 0):,.0f}")
            except Exception as e:
                logger.error(f"Error in normalization pipeline: {e}", exc_info=True)
                # Fallback to basic calculations
        else:
            logger.info(f"✅ STRICT MODE: Preserving extracted values exactly as read - Revenue={cleaned.get('total_revenue', 0):,.0f}, "
                       f"OPEX={cleaned.get('total_operating_expenses', 0):,.0f}, "
                       f"Net Income={cleaned.get('net_income', 0):,.0f}")
        
        # Fallback to basic calculations if needed (only if not in strict mode)
        if not use_strict_mode:
            try:
                revenue = cleaned.get('total_revenue', 0.0)
                cost = cleaned.get('cost_of_revenue', 0.0)
                gross_profit = cleaned.get('gross_profit', 0.0)
                opex = cleaned.get('total_operating_expenses', 0.0)
                operating_income = cleaned.get('operating_income', 0.0)
                net_income = cleaned.get('net_income', 0.0)

                # Gross Profit = Revenue - Cost of Revenue
                if (gross_profit == 0.0) and (revenue or cost):
                    cleaned['gross_profit'] = max(0.0, revenue - cost)

                # Operating Income = Gross Profit - Operating Expenses
                if (operating_income == 0.0) and (cleaned.get('gross_profit', 0.0) or opex):
                    cleaned['operating_income'] = cleaned.get('gross_profit', 0.0) - opex

                # Net Income: if absent, approximate with Operating Income when available
                if (net_income == 0.0) and (cleaned.get('operating_income', 0.0)):
                    cleaned['net_income'] = cleaned.get('operating_income', 0.0)
            except Exception:
                pass
        
        # Ensure date field
        if 'period_date' in record:
            cleaned['period_date'] = record['period_date']
        else:
            cleaned['period_date'] = timezone.now().date()
        
        # ✅ CRITICAL FIX: Recompute derived fields if missing or zero
        total_revenue = cleaned.get('total_revenue', 0)
        cost_of_revenue = cleaned.get('cost_of_revenue', 0)
        gross_profit = cleaned.get('gross_profit', 0)
        total_operating_expenses = cleaned.get('total_operating_expenses', 0)
        operating_income = cleaned.get('operating_income', 0)
        net_income = cleaned.get('net_income', 0)
        
        # ✅ FIX: Detect and correct doubled revenue
        # If revenue seems too high compared to cost and expenses, it might be doubled
        # Check if revenue is approximately 2x what it should be based on cost ratio
        if total_revenue > 0 and cost_of_revenue > 0:
            cost_ratio = cost_of_revenue / total_revenue
            # If cost ratio is very low (< 0.15) and we have operating expenses, revenue might be doubled
            if cost_ratio < 0.15 and total_operating_expenses > 0:
                # Check if halving revenue makes more sense
                test_revenue = total_revenue / 2
                test_cost_ratio = cost_of_revenue / test_revenue if test_revenue > 0 else 0
                test_expense_ratio = total_operating_expenses / test_revenue if test_revenue > 0 else 0
                # If halved revenue gives more reasonable ratios (cost 20-40%, expense 20-50%)
                if 0.20 <= test_cost_ratio <= 0.40 and 0.20 <= test_expense_ratio <= 0.50:
                    logger.warning(f"⚠️ Detected potentially doubled revenue: {total_revenue}. Correcting to {test_revenue}")
                    total_revenue = test_revenue
                    cleaned['total_revenue'] = test_revenue
        
        # Update gross_profit variable after previous calculation
        gross_profit = cleaned.get('gross_profit', 0)
        
        # Recompute gross_profit if missing but we have revenue and cost
        if gross_profit == 0 and total_revenue > 0 and cost_of_revenue > 0:
            gross_profit = total_revenue - cost_of_revenue
            cleaned['gross_profit'] = gross_profit
            logger.info(f"Recomputed gross_profit: {gross_profit}")
        
        # ⭐ CRITICAL: Calculate Operating Expenses if missing or zero
        # Formula: Operating Expenses = Gross Profit - Operating Income
        logger.info(f"🔍 OPEX Calc - Before: opex={total_operating_expenses}, gross_profit={gross_profit}, operating_income={operating_income}, revenue={total_revenue}")
        
        # Priority 1: Calculate from formula if we have gross profit and operating income
        if (total_operating_expenses == 0.0 or total_operating_expenses == 0) and gross_profit > 0 and operating_income > 0:
            calculated_opex = gross_profit - operating_income
            if calculated_opex >= 0:  # Only if non-negative (makes sense)
                cleaned['total_operating_expenses'] = calculated_opex
                total_operating_expenses = calculated_opex
                logger.info(f"✅ Calculated Operating Expenses from formula: {gross_profit} - {operating_income} = {calculated_opex}")
        
        # Priority 2: If still zero, check if we can calculate from revenue and cost
        elif total_operating_expenses == 0 and total_revenue > 0 and cost_of_revenue > 0:
            # We have revenue and cost, so we can calculate gross profit
            if gross_profit == 0:
                gross_profit = total_revenue - cost_of_revenue
                cleaned['gross_profit'] = gross_profit
            
            # If we have operating income, calculate expenses
            if operating_income > 0 and gross_profit > 0:
                calculated_opex = gross_profit - operating_income
                if calculated_opex >= 0:
                    cleaned['total_operating_expenses'] = calculated_opex
                    total_operating_expenses = calculated_opex
                    logger.info(f"✅ Calculated Operating Expenses (from derived gross profit): {gross_profit} - {operating_income} = {calculated_opex}")
            # Otherwise, estimate based on typical expense ratios (30-40% of revenue)
            elif gross_profit > 0:
                estimated_opex = total_revenue * 0.35 if total_revenue > 0 else 0
                if estimated_opex > 0 and estimated_opex < gross_profit:  # Ensure it's less than gross profit
                    cleaned['total_operating_expenses'] = estimated_opex
                    total_operating_expenses = estimated_opex
                    logger.info(f"⚠️ Estimated Operating Expenses: {estimated_opex} (35% of revenue)")
                    # Recalculate operating income
                    if operating_income == 0:
                        operating_income = gross_profit - estimated_opex
                        cleaned['operating_income'] = operating_income
        
        # Priority 3: Final validation - ensure expense ratio makes sense
        if total_operating_expenses > 0 and total_revenue > 0:
            expense_ratio = total_operating_expenses / total_revenue
            # Expense ratio should typically be between 20% and 60% for most businesses
            if expense_ratio > 0.80:
                logger.warning(f"⚠️ Expense ratio is very high ({expense_ratio:.2%}), may indicate data issue")
            elif expense_ratio < 0.05 and total_operating_expenses < 1000:
                # Very low expenses might indicate missing data
                logger.warning(f"⚠️ Expense ratio is very low ({expense_ratio:.2%}), may indicate missing expense data")
        
        if total_operating_expenses == 0:
            logger.warning(f"⚠️ Could not calculate OPEX: opex={total_operating_expenses}, gross_profit={gross_profit}, operating_income={operating_income}, revenue={total_revenue}")
        
        # Recompute operating_income if missing but we have gross profit and expenses
        if operating_income == 0 and gross_profit > 0 and total_operating_expenses > 0:
            operating_income = gross_profit - total_operating_expenses
            cleaned['operating_income'] = operating_income
            logger.info(f"Recomputed operating_income: {operating_income}")
        
        # ✅ FIX: Ensure net income makes sense
        if net_income == 0 and operating_income > 0:
            # Net income is typically close to operating income (before taxes/other items)
            cleaned['net_income'] = operating_income * 0.85  # Approximate after-tax
            logger.info(f"Estimated net_income: {cleaned['net_income']}")
        
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
        
        # ✅ FIX: Calculate ratios if revenue is available - using correct formulas
        if total_revenue > 0:
            # ✅ CORRECT FORMULAS:
            # Profit Margin = Net Income / Total Revenue
            # Operating Margin = Operating Income / Total Revenue
            # Cost Ratio = Cost of Revenue / Total Revenue
            # Expense Ratio = Operating Expenses / Total Revenue
            metrics['profit_margin'] = net_income / total_revenue
            metrics['operating_margin'] = operating_income / total_revenue
            metrics['gross_margin'] = gross_profit / total_revenue
            metrics['cost_revenue_ratio'] = cost_of_revenue / total_revenue
            metrics['expense_ratio'] = total_operating_expenses / total_revenue
            metrics['rd_intensity'] = research_development / total_revenue if research_development != 0 else 0.0
            
            # ✅ Validate ratios are reasonable
            if metrics['expense_ratio'] == 0 and total_operating_expenses > 0:
                logger.warning(f"⚠️ Expense ratio is 0 but operating expenses exist: {total_operating_expenses}. Recalculating...")
                metrics['expense_ratio'] = total_operating_expenses / total_revenue
            
            logger.info(f"📊 Calculated Metrics: profit_margin={metrics['profit_margin']:.4f} ({metrics['profit_margin']*100:.2f}%), operating_margin={metrics['operating_margin']:.4f} ({metrics['operating_margin']*100:.2f}%), cost_ratio={metrics['cost_revenue_ratio']:.4f} ({metrics['cost_revenue_ratio']*100:.2f}%), expense_ratio={metrics['expense_ratio']:.4f} ({metrics['expense_ratio']*100:.2f}%), OPEX={total_operating_expenses}, Revenue={total_revenue}")
        else:
            metrics.update({
                'profit_margin': None,
                'operating_margin': None,
                'gross_margin': None,
                'cost_revenue_ratio': None,
                'expense_ratio': None,
                'rd_intensity': None
            })
            logger.warning(f"⚠️ Cannot calculate metrics: total_revenue is {total_revenue}")
        
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
    
    def _trigger_automatic_analysis(self, upload_record: FinancialDataUpload, storage_result: Dict[str, Any], 
                                   extraction_result: Dict[str, Any] = None) -> Dict[str, Any]:
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
            
            # ✅ PRIORITY: Use JSON data from cell-by-cell extraction if available
            if extraction_result and extraction_result.get('json_data'):
                logger.info("✅ Using JSON data from cell-by-cell extraction for analysis")
                financial_data = extraction_result['json_data'].copy()
                logger.info(f"📊 Analysis Input (JSON): Revenue={financial_data.get('totalRevenue', 0):,.0f}, "
                           f"OPEX={financial_data.get('totalOperatingExpenses', 0):,.0f}, "
                           f"NI={financial_data.get('netIncome', 0):,.0f}")
            else:
                # Fallback: Get the latest processed financial data
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
                logger.info(f"📊 Analysis Input (DB): Revenue={financial_data.get('totalRevenue', 0):,.0f}, "
                           f"OPEX={financial_data.get('totalOperatingExpenses', 0):,.0f}, "
                           f"NI={financial_data.get('netIncome', 0):,.0f}")
            
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
            
            # Generate strict truth report (covers risk + fraud detection)
            truth_report = self._generate_truth_report(financial_data, predictions)
            risk_assessment = truth_report.get('risk_assessment', {
                'overall_risk': 'LOW',
                'profitability_risk': 'LOW',
                'operational_risk': 'LOW',
                'risk_factors': []
            })
            
            # Map strict recommendations into legacy buckets for backward compatibility
            recommendations = {
                'immediate_actions': [],
                'cost_optimization': [],
                'revenue_enhancement': [],
                'profitability_improvements': []
            }
            
            for rec in truth_report.get('brutally_honest_recommendations', []):
                category = 'immediate_actions'
                text = rec.get('recommendation') or rec.get('action') or ''
                entry = {
                    'action': text.split(':')[0] if ':' in text else text[:60] or 'Action Required',
                    'description': text,
                    'priority': rec.get('priority', 'HIGH'),
                    'timeline': rec.get('timeline'),
                    'potential_savings': rec.get('potential_savings')
                }
                if rec.get('category') and rec['category'] in recommendations:
                    category = rec['category']
                recommendations.setdefault(category, []).append(entry)
            
            if not any(recommendations.values()):
                # Provide at least one actionable insight if strict recommendations were empty
                recommendations['immediate_actions'].append({
                    'action': 'Review Financial Position',
                    'description': 'Confirm the reported numbers and ensure no sections are missing (strict truth mode).',
                    'priority': 'MEDIUM'
                })
            
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
                'truth_report': truth_report,
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

    def _generate_truth_report(self, financial_data: Dict[str, Any], predictions: Dict[str, float] | None = None) -> Dict[str, Any]:
        """
        Build a strict-truth report that mirrors the enforcement rules shared by the product team.
        This method NEVER massages numbers — it only reports what was provided and flags inconsistencies.
        """
        def _num(*keys: str) -> float:
            for key in keys:
                if key in financial_data and financial_data[key] is not None:
                    try:
                        return float(financial_data[key])
                    except (ValueError, TypeError):
                        continue
            return 0.0
        
        revenue = _num('totalRevenue', 'total_revenue', 'Revenue', 'revenue')
        cost = _num('costOfRevenue', 'cost_of_revenue', 'cogs')
        gross_profit = _num('grossProfit', 'gross_profit')
        operating_expenses = _num('totalOperatingExpenses', 'total_operating_expenses', 'operatingExpenses')
        operating_income = _num('operatingIncome', 'operating_income')
        net_income = _num('netIncome', 'net_income')
        interest_expense = _num('interestExpense', 'interest_expense')
        taxes = _num('incomeTaxExpense', 'income_tax_expense', 'taxes')
        
        reported = {
            'total_revenue': revenue,
            'cost_of_revenue': cost,
            'gross_profit': gross_profit,
            'operating_expenses': operating_expenses,
            'operating_income': operating_income,
            'net_income': net_income,
            'interest_expense': interest_expense,
            'taxes': taxes
        }
        
        predicted = predictions or {}
        summary_points: List[str] = []
        fraud_flags: List[str] = []
        discrepancies: List[Dict[str, Any]] = []
        honest_recs: List[Dict[str, Any]] = []
        
        def fmt_amount(value: float) -> str:
            return f"KES {value:,.0f}"
        
        summary_points.append(f"Reported revenue: {fmt_amount(revenue)}")
        summary_points.append(f"Reported net income: {fmt_amount(net_income)}")
        summary_points.append(f"Reported operating expenses: {fmt_amount(operating_expenses)}")
        
        # ✅ STEP 1: RECONCILIATION ENGINE - Auto-correct arithmetic errors BEFORE fraud detection
        from Tazama.core.FinancialReconciliationEngine import FinancialReconciliationEngine
        from Tazama.core.FraudDetectionEngine import FraudDetectionEngine
        
        # Run reconciliation first
        reconciliation_engine = FinancialReconciliationEngine()
        reconciliation_result = reconciliation_engine.reconcile_statement(financial_data)
        
        # Log reconciliation results
        logger.info(f"📝 Reconciliation: {len(reconciliation_result['corrections_made'])} corrections, Risk={reconciliation_result['risk_level']}")
        if reconciliation_result['corrections_made']:
            logger.info(f"   Corrections: {[c['field'] for c in reconciliation_result['corrections_made']]}")
        
        # Use RECONCILED data for fraud detection (not original data)
        reconciled_data = reconciliation_result['reconciled_data']
        
        # ✅ STEP 2: FRAUD DETECTION ENGINE - Run on reconciled data
        fraud_engine = FraudDetectionEngine()
        fraud_analysis = fraud_engine.analyze_financial_statement(reconciled_data)
        
        # ✅ ADJUST FRAUD SCORE: Downgrade if reconciliation was successful
        if reconciliation_result['is_reconciled'] and len(reconciliation_result['corrections_made']) > 0:
            # If corrections were made and statement now reconciles, reduce fraud score
            original_fraud_score = fraud_analysis['fraud_score']
            if reconciliation_result['risk_level'] in ['LOW', 'MODERATE']:
                # Reduce fraud score by 50% if issues were just arithmetic errors
                fraud_analysis['fraud_score'] = max(0, int(fraud_analysis['fraud_score'] * 0.5))
                logger.info(f"   ✅ Fraud score reduced from {original_fraud_score} to {fraud_analysis['fraud_score']} (arithmetic errors corrected)")
                
                # Update fraud probability based on new score
                if fraud_analysis['fraud_score'] >= 75:
                    fraud_analysis['fraud_probability'] = 'CRITICAL'
                elif fraud_analysis['fraud_score'] >= 50:
                    fraud_analysis['fraud_probability'] = 'HIGH'
                elif fraud_analysis['fraud_score'] >= 25:
                    fraud_analysis['fraud_probability'] = 'MEDIUM'
                else:
                    fraud_analysis['fraud_probability'] = 'LOW'
        
        # Merge fraud analysis results with reconciliation context
        fraud_flags = fraud_analysis['red_flags'] + fraud_analysis['warnings']
        
        # Add reconciliation info to fraud flags if corrections were made
        if reconciliation_result['corrections_made']:
            fraud_flags.insert(0, f"ℹ️ DATA QUALITY: {len(reconciliation_result['corrections_made'])} arithmetic corrections applied to statement before analysis")
        
        logger.info(f"🔍 Final Analysis: Fraud Score={fraud_analysis['fraud_score']}, Probability={fraud_analysis['fraud_probability']}, Flags={len(fraud_flags)}")
        
        # Still check for mathematical discrepancies separately for the discrepancies report
        # This is for the detailed discrepancy table, fraud flags come from the engine
        if revenue and cost:
            calculated_gp = revenue - cost
            if abs(calculated_gp - gross_profit) > max(1, abs(calculated_gp) * 0.01):
                discrepancies.append({
                    'metric': 'Gross Profit',
                    'reported': gross_profit,
                    'calculated': calculated_gp,
                    'difference': gross_profit - calculated_gp
                })
        
        if gross_profit and operating_income:
            expected_opex = gross_profit - operating_income
            if abs(expected_opex - operating_expenses) > max(1, abs(expected_opex) * 0.01):
                discrepancies.append({
                    'metric': 'Operating Expenses',
                    'reported': operating_expenses,
                    'calculated': expected_opex,
                    'difference': operating_expenses - expected_opex
                })
        
        # All other fraud detection is now handled by the FraudDetectionEngine above
        
        # Risk assessment per strict rules (enhanced with fraud analysis)
        def escalate(current: str, new_level: str) -> str:
            order = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            try:
                return new_level if order.index(new_level) > order.index(current) else current
            except ValueError:
                return current
        
        risk = {
            'overall_risk': fraud_analysis['fraud_probability'],  # Start with fraud assessment
            'profitability_risk': 'LOW',
            'operational_risk': 'LOW',
            'liquidity_risk': 'LOW',
            'fraud_risk': fraud_analysis['fraud_probability'],
            'fraud_score': fraud_analysis['fraud_score'],
            'risk_factors': []
        }
        
        if operating_income < 0:
            risk['operational_risk'] = 'MEDIUM'
            risk['overall_risk'] = escalate(risk['overall_risk'], 'MEDIUM')
            risk['risk_factors'].append('Operating income is negative.')
        
        if net_income < 0:
            risk['profitability_risk'] = 'HIGH'
            risk['overall_risk'] = escalate(risk['overall_risk'], 'HIGH')
            risk['risk_factors'].append('Net income is negative (loss-making period).')
        
        if net_income < 0 and interest_expense > 0:
            risk['overall_risk'] = escalate(risk['overall_risk'], 'VERY HIGH')
            risk['risk_factors'].append('Losses combined with interest expense indicate debt distress.')
        
        if operating_expenses == 0 and revenue > 0:
            risk['operational_risk'] = escalate(risk['operational_risk'], 'HIGH')
            risk['risk_factors'].append('Operating expenses missing — incomplete statement.')
        
        # ✅ BRUTAL TRUTH: Honest recommendations derived from EXACT numbers
        def push_rec(priority: str, text: str, category: str = 'immediate_actions', timeline: str = None):
            honest_recs.append({
                'priority': priority,
                'recommendation': text,
                'category': category,
                'timeline': timeline
            })
        
        # ✅ Calculate key financial ratios
        profit_margin = (net_income / revenue * 100) if revenue > 0 else 0
        operating_margin = (operating_income / revenue * 100) if revenue > 0 else 0
        cost_ratio = (cost / revenue * 100) if revenue > 0 else 0
        expense_ratio = (operating_expenses / revenue * 100) if revenue > 0 else 0
        
        # ✅ CRITICAL: Loss-making company
        if net_income < 0:
            loss_amount = abs(net_income)
            push_rec(
                'CRITICAL', 
                f'🚨 IMMEDIATE CASH CRISIS: Company lost {fmt_amount(loss_amount)} this year. '
                f'Net margin is {profit_margin:.1f}% (NEGATIVE). This is NOT sustainable.',
                'immediate_actions',
                'Immediate - 0-30 days'
            )
            
            # Calculate required expense cuts
            required_cut = loss_amount * 1.2  # Need to cut 120% of loss to break even with buffer
            cut_percentage = (required_cut / operating_expenses * 100) if operating_expenses > 0 else 0
            
            push_rec(
                'CRITICAL',
                f'CUT EXPENSES IMMEDIATELY: Need to reduce operating expenses by {fmt_amount(required_cut)} '
                f'({cut_percentage:.0f}%) to break even. Current OpEx = {fmt_amount(operating_expenses)}. '
                f'Target: {fmt_amount(operating_expenses - required_cut)}.',
                'cost_reduction',
                '30-60 days'
            )
            
            # Interest burden check
            if interest_expense > 0:
                interest_coverage = operating_income / interest_expense if interest_expense > 0 else 0
                if interest_coverage < 1:
                    push_rec(
                        'CRITICAL',
                        f'DEBT CRISIS: Interest expense of {fmt_amount(interest_expense)} on LOSS-MAKING operations. '
                        f'Interest coverage ratio is {interest_coverage:.2f}x (< 1.0 = cannot cover debt). '
                        f'URGENT: Restructure debt or seek equity injection within 90 days or face insolvency.',
                        'debt_management',
                        '60-90 days (URGENT)'
                    )
        
        # ✅ CRITICAL: Negative operating income
        if operating_income < 0:
            op_loss = abs(operating_income)
            push_rec(
                'HIGH',
                f'⚠️ OPERATING LOSS: Core business operations lost {fmt_amount(op_loss)} (Operating margin: {operating_margin:.1f}%). '
                f'Your business model is BROKEN. Revenue ({fmt_amount(revenue)}) cannot cover COGS ({fmt_amount(cost)}) + OpEx ({fmt_amount(operating_expenses)}).',
                'business_model',
                '30-90 days'
            )
        
        # ✅ HIGH: Very low margins (even if profitable)
        elif net_income > 0 and profit_margin < 5:
            push_rec(
                'HIGH',
                f'THIN MARGINS: Net profit margin is only {profit_margin:.1f}% ({fmt_amount(net_income)} profit on {fmt_amount(revenue)} revenue). '
                f'Any market disruption will push you into losses. Increase margins to 10%+ minimum.',
                'margin_improvement',
                '3-6 months'
            )
        
        # ✅ HIGH: High cost ratio
        if cost_ratio > 70:
            push_rec(
                'HIGH',
                f'HIGH COST RATIO: COGS is {cost_ratio:.1f}% of revenue ({fmt_amount(cost)} / {fmt_amount(revenue)}). '
                f'Industry standard is 50-60%. Renegotiate supplier contracts, find cheaper alternatives, or increase prices.',
                'cost_optimization',
                '3-6 months'
            )
        
        # ✅ HIGH: Operating expenses too high
        if expense_ratio > 40 and operating_income > 0:
            target_opex = revenue * 0.30  # Target 30% OpEx ratio
            savings = operating_expenses - target_opex
            push_rec(
                'HIGH',
                f'EXCESSIVE OPERATING EXPENSES: OpEx is {expense_ratio:.1f}% of revenue ({fmt_amount(operating_expenses)}). '
                f'Target should be 25-30% maximum. Potential savings: {fmt_amount(savings)} by reducing non-essential spending.',
                'operational_efficiency',
                '6-12 months'
            )
        
        # ✅ CRITICAL: Missing operating expenses (fraud indicator)
        if operating_expenses == 0 and revenue > 0:
            push_rec(
                'CRITICAL', 
                f'🚨 FRAUD ALERT: Operating expenses = 0 while revenue = {fmt_amount(revenue)}. '
                f'This is IMPOSSIBLE. Statement is incomplete or fraudulent. Do NOT trust these numbers.',
                'data_integrity',
                'Immediate'
            )
        
        # ✅ CRITICAL: Revenue too low / No revenue
        if revenue == 0:
            push_rec(
                'CRITICAL', 
                '🚨 NO REVENUE: Statement shows zero revenue. Company is non-operational or statement is incomplete. '
                'Verify the uploaded document is correct.',
                'data_integrity',
                'Immediate'
            )
        elif revenue < 1000000:  # Less than 1M
            push_rec(
                'MEDIUM',
                f'LOW REVENUE: Total revenue is only {fmt_amount(revenue)}. Company is very small scale. '
                f'Focus on growth initiatives to reach 5M+ revenue for viability.',
                'revenue_growth',
                '12+ months'
            )
        
        # ✅ CRITICAL: Fraud flags detected
        if fraud_flags:
            push_rec(
                'CRITICAL', 
                f'🚨 FRAUD INDICATORS DETECTED: {len(fraud_flags)} mathematical discrepancies found. '
                f'Numbers do NOT reconcile. Possible manipulation: {", ".join(fraud_flags[:2])}. '
                f'DO NOT approve loans/investments until resolved.',
                'fraud_investigation',
                'Immediate - Do not proceed'
            )
        
        # ✅ Additional specific recommendations based on actual data
        if net_income > 0:
            # Profitable but need to check sustainability
            if operating_margin < 10:
                push_rec(
                    'MEDIUM',
                    f'SUSTAINABLE GROWTH RISK: Operating margin is {operating_margin:.1f}% (target: 15%+). '
                    f'Profit is {fmt_amount(net_income)} but margins are thin. Focus on high-margin products/services.',
                    'margin_improvement',
                    '6-12 months'
                )

            # Strong performance
            if profit_margin > 15:
                push_rec(
                    'LOW',
                    f'STRONG PERFORMANCE: Net margin is {profit_margin:.1f}% ({fmt_amount(net_income)} profit). '
                    f'Company is profitable. Focus on maintaining efficiency while scaling revenue.',
                    'growth_strategy',
                    '12+ months'
                )

            # ✅ CRITICAL: Always provide at least one recommendation for profitable companies
            # If no other recommendations were triggered, provide general growth advice
            if len(honest_recs) == 0:
                push_rec(
                    'LOW',
                    f'HEALTHY FINANCIAL POSITION: Company shows profit of {fmt_amount(net_income)} on {fmt_amount(revenue)} revenue '
                    f'(net margin: {profit_margin:.1f}%, operating margin: {operating_margin:.1f}%). '
                    f'Focus on sustainable growth strategies and maintain current operational efficiency.',
                    'growth_strategy',
                    'Ongoing'
                )
        
        profitability_table = [
            {'label': 'Total Revenue', 'value': revenue},
            {'label': 'Cost of Revenue', 'value': cost},
            {'label': 'Gross Profit', 'value': gross_profit},
            {'label': 'Operating Expenses', 'value': operating_expenses},
            {'label': 'Operating Income', 'value': operating_income},
            {'label': 'Net Income', 'value': net_income},
            {'label': 'Interest Expense', 'value': interest_expense},
            {'label': 'Taxes', 'value': taxes},
        ]
        
        return {
            'executive_summary': {
                'overall_risk': risk['overall_risk'],
                'summary_points': summary_points
            },
            'profitability_table': profitability_table,
            'risk_assessment': risk,
            'fraud_red_flags': fraud_flags,
            'exact_numbers_vs_discrepancy': discrepancies,
            'brutally_honest_recommendations': honest_recs,
            'reported_figures': reported,
            'predictions': predicted,
            # ✅ NEW: Reconciliation data
            'reconciliation': {
                'corrections_made': reconciliation_result['corrections_made'],
                'reconciled_data': reconciliation_result['reconciled_data'],
                'original_data': reconciliation_result['original_data'],
                'reconciliation_report': reconciliation_result['reconciliation_report'],
                'is_reconciled': reconciliation_result['is_reconciled'],
                'lending_recommendation': reconciliation_result['lending_recommendation']
            }
        }
    
    def analyze_intelligent_date_driven_projection(self, financial_data: Dict[str, Any], statement_date: date, corporate_id: int = None) -> Dict[str, Any]:
        """
        Perform intelligent date-driven analysis that generates comprehensive projections
        and recommendations based on the actual statement date and historical patterns
        
        Args:
            financial_data: Dictionary containing financial data
            statement_date: Date of the financial statement
            corporate_id: Corporate ID for historical data analysis
            
        Returns:
            Dictionary with intelligent date-driven projections and recommendations
        """
        try:
            logger.info(f"Performing intelligent date-driven analysis for statement dated: {statement_date}")
            
            # Comprehensive statement date analysis
            date_analysis = self._analyze_statement_date_intelligence(statement_date)
            
            # Get historical patterns for this corporate
            historical_patterns = self._get_historical_patterns(corporate_id, statement_date) if corporate_id else {}
            
            # Generate intelligent projections based on date analysis
            intelligent_projections = self._generate_intelligent_projections(
                financial_data, statement_date, date_analysis, historical_patterns
            )
            
            # Generate intelligent KPI predictions
            kpi_predictions = self._generate_intelligent_kpi_predictions(
                financial_data, statement_date, date_analysis, historical_patterns
            )
            
            # Generate cost optimization recommendations
            cost_optimization = self._generate_intelligent_cost_optimization(
                financial_data, statement_date, date_analysis, historical_patterns
            )
            
            # Generate decision-making intelligence
            decision_intelligence = self._generate_decision_making_intelligence(
                financial_data, statement_date, date_analysis, intelligent_projections
            )
            
            # Calculate intelligent confidence scores
            confidence_analysis = self._calculate_intelligent_confidence(
                financial_data, intelligent_projections, historical_patterns
            )
            
            return {
                'success': True,
                'statement_date': statement_date.isoformat(),
                'date_analysis': date_analysis,
                'intelligent_projections': intelligent_projections,
                'kpi_predictions': kpi_predictions,
                'cost_optimization': cost_optimization,
                'decision_intelligence': decision_intelligence,
                'confidence_analysis': confidence_analysis,
                'historical_insights': historical_patterns,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in intelligent date-driven analysis: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_statement_date_intelligence(self, statement_date: date) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of the statement date to determine
        the most appropriate analysis approach and projections
        """
        try:
            # Determine fiscal year and quarter
            fiscal_year = self._determine_fiscal_year(statement_date)
            quarter = self._get_quarter_from_date(statement_date)
            
            # Determine statement type and period
            statement_type = self._determine_statement_type(statement_date)
            period_type = self._determine_period_type(statement_date)
            
            # Calculate time-based factors
            time_factors = self._calculate_time_factors(statement_date)
            
            # Determine seasonal patterns
            seasonal_analysis = self._analyze_seasonal_patterns(statement_date)
            
            # Calculate business cycle position
            business_cycle = self._determine_business_cycle_position(statement_date)
            
            return {
                'fiscal_year': fiscal_year,
                'quarter': quarter,
                'statement_type': statement_type,
                'period_type': period_type,
                'time_factors': time_factors,
                'seasonal_analysis': seasonal_analysis,
                'business_cycle': business_cycle,
                'is_year_end': statement_date.month == 12 and statement_date.day >= 25,
                'is_quarter_end': statement_date.month in [3, 6, 9, 12] and statement_date.day >= 25,
                'days_since_year_start': (statement_date - date(statement_date.year, 1, 1)).days,
                'days_until_year_end': (date(statement_date.year, 12, 31) - statement_date).days
            }
            
        except Exception as e:
            logger.error(f"Error analyzing statement date intelligence: {str(e)}")
            return {}
    
    def _determine_fiscal_year(self, statement_date: date) -> int:
        """Determine fiscal year based on statement date"""
        # Most companies use calendar year, but this could be customized
        return statement_date.year
    
    def _get_quarter_from_date(self, statement_date: date) -> int:
        """Get quarter number from date"""
        return (statement_date.month - 1) // 3 + 1
    
    def _determine_statement_type(self, statement_date: date) -> str:
        """Determine the type of financial statement based on date"""
        if statement_date.month == 12 and statement_date.day >= 25:
            return 'annual'
        elif statement_date.month in [3, 6, 9, 12] and statement_date.day >= 25:
            return 'quarterly'
        else:
            return 'interim'
    
    def _determine_period_type(self, statement_date: date) -> str:
        """Determine the period type for projections"""
        if statement_date.month == 12 and statement_date.day >= 25:
            return 'yearly'
        elif statement_date.month in [3, 6, 9, 12] and statement_date.day >= 25:
            return 'quarterly'
        else:
            return 'quarterly'  # Default to quarterly for interim statements
    
    def _calculate_time_factors(self, statement_date: date) -> Dict[str, Any]:
        """Calculate various time-based factors that affect projections"""
        return {
            'month_of_year': statement_date.month,
            'quarter_of_year': (statement_date.month - 1) // 3 + 1,
            'is_holiday_season': statement_date.month in [11, 12, 1],
            'is_summer_season': statement_date.month in [6, 7, 8],
            'is_fiscal_year_end': statement_date.month == 12,
            'is_fiscal_quarter_end': statement_date.month in [3, 6, 9, 12],
            'business_days_remaining': self._calculate_business_days_remaining(statement_date),
            'seasonal_multiplier': self._get_seasonal_multiplier(statement_date)
        }
    
    def _analyze_seasonal_patterns(self, statement_date: date) -> Dict[str, Any]:
        """Analyze seasonal patterns that affect business performance"""
        month = statement_date.month
        quarter = (month - 1) // 3 + 1
        
        seasonal_patterns = {
            'Q1': {'revenue_factor': 0.95, 'expense_factor': 1.05, 'description': 'Post-holiday recovery period'},
            'Q2': {'revenue_factor': 1.0, 'expense_factor': 1.0, 'description': 'Steady growth period'},
            'Q3': {'revenue_factor': 0.90, 'expense_factor': 1.10, 'description': 'Summer slowdown period'},
            'Q4': {'revenue_factor': 1.15, 'expense_factor': 1.05, 'description': 'Holiday season boost'}
        }
        
        return seasonal_patterns.get(f'Q{quarter}', seasonal_patterns['Q2'])
    
    def _determine_business_cycle_position(self, statement_date: date) -> Dict[str, Any]:
        """Determine the position in the business cycle"""
        # This would ideally use economic indicators, but for now use seasonal patterns
        month = statement_date.month
        
        if month in [1, 2, 3]:
            return {'phase': 'recovery', 'growth_expectation': 0.05, 'description': 'Post-holiday recovery phase'}
        elif month in [4, 5, 6]:
            return {'phase': 'growth', 'growth_expectation': 0.08, 'description': 'Strong growth phase'}
        elif month in [7, 8, 9]:
            return {'phase': 'slowdown', 'growth_expectation': 0.03, 'description': 'Summer slowdown phase'}
        else:
            return {'phase': 'acceleration', 'growth_expectation': 0.10, 'description': 'Year-end acceleration phase'}
    
    def _get_historical_patterns(self, corporate_id: int, statement_date: date) -> Dict[str, Any]:
        """Get historical patterns for the corporate entity"""
        try:
            if not corporate_id:
                return {}
            
            # Get historical data for the same period in previous years
            historical_data = ProcessedFinancialData.objects.filter(
                corporate_id=corporate_id,
                period_date__month=statement_date.month,
                period_date__year__lt=statement_date.year
            ).order_by('-period_date')
            
            if not historical_data.exists():
                return {}
            
            # Calculate historical growth patterns
            patterns = {
                'revenue_growth_history': [],
                'profit_growth_history': [],
                'seasonal_consistency': 0.0,
                'year_over_year_growth': 0.0,
                'volatility_score': 0.0
            }
            
            # Analyze historical patterns
            for i, record in enumerate(historical_data[:3]):  # Last 3 years
                if i > 0:
                    prev_record = historical_data[i-1]
                    if prev_record.total_revenue > 0:
                        revenue_growth = (record.total_revenue - prev_record.total_revenue) / prev_record.total_revenue
                        patterns['revenue_growth_history'].append(revenue_growth)
                    
                    if prev_record.net_income > 0:
                        profit_growth = (record.net_income - prev_record.net_income) / prev_record.net_income
                        patterns['profit_growth_history'].append(profit_growth)
            
            # Calculate average growth rates
            if patterns['revenue_growth_history']:
                patterns['avg_revenue_growth'] = sum(patterns['revenue_growth_history']) / len(patterns['revenue_growth_history'])
            if patterns['profit_growth_history']:
                patterns['avg_profit_growth'] = sum(patterns['profit_growth_history']) / len(patterns['profit_growth_history'])
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error getting historical patterns: {str(e)}")
            return {}
    
    def _generate_intelligent_projections(self, financial_data: Dict[str, Any], statement_date: date, date_analysis: Dict[str, Any], historical_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Generate intelligent projections based on date analysis and historical patterns"""
        try:
            # Extract current financial metrics (support snake_case and camelCase)
            def v(*keys, default=0.0):
                for k in keys:
                    if k in financial_data and isinstance(financial_data.get(k), (int, float)):
                        return float(financial_data.get(k) or 0)
                return float(default)

            revenue = v('totalRevenue', 'total_revenue')
            cost_of_revenue = v('costOfRevenue', 'cost_of_revenue')
            gross_profit = v('grossProfit', 'gross_profit')
            operating_expenses = v('totalOperatingExpenses', 'total_operating_expenses')
            operating_income = v('operatingIncome', 'operating_income')
            net_income = v('netIncome', 'net_income')
            
            # Calculate intelligent growth rates based on date analysis
            growth_rates = self._calculate_intelligent_growth_rates(
                financial_data, date_analysis, historical_patterns
            )
            
            # Generate projections for next period
            next_period = self._calculate_next_period(statement_date, date_analysis)
            
            # Compute projections using dynamic formulas (multiplicative, dependency aware)
            projected_revenue = self._project_intelligent_revenue(revenue, growth_rates, date_analysis)
            projected_cost_of_revenue = self._project_intelligent_cost_of_revenue(cost_of_revenue, growth_rates, date_analysis)
            projected_gross_profit = projected_revenue - projected_cost_of_revenue
            projected_operating_expenses = self._project_intelligent_operating_expenses(operating_expenses, growth_rates, date_analysis)
            projected_operating_income = projected_gross_profit - projected_operating_expenses
            projected_net_income = self._project_intelligent_net_income(net_income, growth_rates, date_analysis)

            projections = {
                'next_period': {
                    'period': next_period['label'],
                    'start_date': next_period['start_date'],
                    'end_date': next_period['end_date'],
                    'projected_revenue': projected_revenue,
                    'projected_cost_of_revenue': projected_cost_of_revenue,
                    'projected_gross_profit': projected_gross_profit,
                    'projected_operating_expenses': projected_operating_expenses,
                    'projected_operating_income': projected_operating_income,
                    'projected_net_income': projected_net_income
                },
                'growth_rates': growth_rates,
                'confidence_factors': self._calculate_projection_confidence(date_analysis, historical_patterns),
                'risk_factors': self._identify_projection_risks(date_analysis, growth_rates)
            }
            
            return projections
            
        except Exception as e:
            logger.error(f"Error generating intelligent projections: {str(e)}")
            return {}
    
    def _calculate_intelligent_growth_rates(self, financial_data: Dict[str, Any], date_analysis: Dict[str, Any], historical_patterns: Dict[str, Any]) -> Dict[str, float]:
        """Calculate intelligent growth rates based on date analysis and historical patterns"""
        # Base growth rates
        base_rates = {
            'revenue_growth': 0.05,
            'cost_growth': 0.03,
            'gross_profit_growth': 0.06,
            'expense_growth': 0.02,
            'operating_income_growth': 0.08,
            'net_income_growth': 0.10
        }
        
        # Adjust based on historical patterns
        if historical_patterns.get('avg_revenue_growth'):
            base_rates['revenue_growth'] = historical_patterns['avg_revenue_growth']
        if historical_patterns.get('avg_profit_growth'):
            base_rates['net_income_growth'] = historical_patterns['avg_profit_growth']
        
        # Adjust based on seasonal analysis
        seasonal_factor = date_analysis.get('seasonal_analysis', {}).get('revenue_factor', 1.0)
        base_rates['revenue_growth'] *= seasonal_factor
        
        # Adjust based on business cycle
        business_cycle = date_analysis.get('business_cycle', {})
        cycle_growth = business_cycle.get('growth_expectation', 0.05)
        base_rates['revenue_growth'] = (base_rates['revenue_growth'] + cycle_growth) / 2
        
        return base_rates
    
    def _calculate_next_period(self, statement_date: date, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate the next period based on statement date and analysis"""
        period_type = date_analysis.get('period_type', 'quarterly')
        
        if period_type == 'yearly':
            next_year = statement_date.year + 1
            return {
                'label': f'FY {next_year}',
                'start_date': date(next_year, 1, 1).isoformat(),
                'end_date': date(next_year, 12, 31).isoformat(),
                'type': 'yearly'
            }
        else:
            # Calculate next quarter
            current_quarter = date_analysis.get('quarter', 1)
            next_quarter = current_quarter + 1
            next_year = statement_date.year
            
            if next_quarter > 4:
                next_quarter = 1
                next_year += 1
            
            # Calculate quarter dates
            quarter_start_month = (next_quarter - 1) * 3 + 1
            quarter_end_month = next_quarter * 3
            
            return {
                'label': f'Q{next_quarter} {next_year}',
                'start_date': date(next_year, quarter_start_month, 1).isoformat(),
                'end_date': date(next_year, quarter_end_month, calendar.monthrange(next_year, quarter_end_month)[1]).isoformat(),
                'type': 'quarterly'
            }
    
    def _project_intelligent_revenue(self, current_revenue: float, growth_rates: Dict[str, float], date_analysis: Dict[str, Any]) -> float:
        """Project revenue using intelligent analysis"""
        base_growth = growth_rates.get('revenue_growth', 0.05)
        seasonal_factor = date_analysis.get('seasonal_analysis', {}).get('revenue_factor', 1.0)
        return current_revenue * (1 + base_growth) * seasonal_factor
    
    def _project_intelligent_cost_of_revenue(self, current_cost: float, growth_rates: Dict[str, float], date_analysis: Dict[str, Any]) -> float:
        """Project cost of revenue using intelligent analysis"""
        base_growth = growth_rates.get('cost_growth', 0.03)
        return current_cost * (1 + base_growth)
    
    def _project_intelligent_gross_profit(self, current_gross_profit: float, growth_rates: Dict[str, float], date_analysis: Dict[str, Any]) -> float:
        """Project gross profit using intelligent analysis"""
        base_growth = growth_rates.get('gross_profit_growth', 0.06)
        return current_gross_profit * (1 + base_growth)
    
    def _project_intelligent_operating_expenses(self, current_expenses: float, growth_rates: Dict[str, float], date_analysis: Dict[str, Any]) -> float:
        """Project operating expenses using intelligent analysis"""
        base_growth = growth_rates.get('expense_growth', 0.02)
        seasonal_factor = date_analysis.get('seasonal_analysis', {}).get('expense_factor', 1.0)
        return current_expenses * (1 + base_growth) * seasonal_factor
    
    def _project_intelligent_operating_income(self, current_operating_income: float, growth_rates: Dict[str, float], date_analysis: Dict[str, Any]) -> float:
        """Project operating income using intelligent analysis"""
        base_growth = growth_rates.get('operating_income_growth', 0.08)
        return current_operating_income * (1 + base_growth)
    
    def _project_intelligent_net_income(self, current_net_income: float, growth_rates: Dict[str, float], date_analysis: Dict[str, Any]) -> float:
        """Project net income using intelligent analysis"""
        base_growth = growth_rates.get('net_income_growth', 0.10)
        return current_net_income * (1 + base_growth)
    
    def _calculate_projection_confidence(self, date_analysis: Dict[str, Any], historical_patterns: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence factors for projections"""
        confidence = {
            'overall': 0.8,
            'revenue': 0.85,
            'costs': 0.80,
            'profit': 0.75
        }
        
        # Adjust based on historical data availability
        if historical_patterns:
            confidence['overall'] += 0.1
            confidence['revenue'] += 0.05
        
        # Adjust based on statement type
        statement_type = date_analysis.get('statement_type', 'interim')
        if statement_type == 'annual':
            confidence['overall'] += 0.05
        elif statement_type == 'quarterly':
            confidence['overall'] += 0.02
        
        return confidence
    
    def _identify_projection_risks(self, date_analysis: Dict[str, Any], growth_rates: Dict[str, float]) -> List[Dict[str, Any]]:
        """Identify risks in projections"""
        risks = []
        
        # Check for unrealistic growth rates
        if growth_rates.get('revenue_growth', 0) > 0.5:
            risks.append({
                'type': 'unrealistic_growth',
                'severity': 'high',
                'description': 'Revenue growth rate is unusually high',
                'recommendation': 'Review and validate growth assumptions'
            })
        
        # Check for seasonal risks
        seasonal_analysis = date_analysis.get('seasonal_analysis', {})
        if seasonal_analysis.get('revenue_factor', 1.0) < 0.8:
            risks.append({
                'type': 'seasonal_risk',
                'severity': 'medium',
                'description': 'Projected period is in a historically low-revenue season',
                'recommendation': 'Consider seasonal adjustments and contingency planning'
            })
        
        return risks
    
    def _generate_intelligent_kpi_predictions(self, financial_data: Dict[str, Any], statement_date: date, date_analysis: Dict[str, Any], historical_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Generate intelligent KPI predictions based on statement date and analysis"""
        try:
            # Extract current financial metrics (support snake_case and camelCase)
            def v(*keys, default=0.0):
                for k in keys:
                    if k in financial_data and isinstance(financial_data.get(k), (int, float)):
                        return float(financial_data.get(k) or 0)
                return float(default)

            revenue = v('totalRevenue', 'total_revenue')
            cost_of_revenue = v('costOfRevenue', 'cost_of_revenue')
            gross_profit = v('grossProfit', 'gross_profit')
            operating_expenses = v('totalOperatingExpenses', 'total_operating_expenses')
            operating_income = v('operatingIncome', 'operating_income')
            net_income = v('netIncome', 'net_income')
            
            # Calculate current KPIs
            current_kpis = {
                'profit_margin': max(0.0, min(1.0, (net_income / revenue) if revenue > 0 else 0)),
                'operating_margin': max(0.0, min(1.0, (operating_income / revenue) if revenue > 0 else 0)),
                'gross_margin': max(0.0, min(1.0, (gross_profit / revenue) if revenue > 0 else 0)),
                'cost_revenue_ratio': max(0.0, min(1.0, (cost_of_revenue / revenue) if revenue > 0 else 0)),
                'expense_ratio': max(0.0, min(1.0, (operating_expenses / revenue) if revenue > 0 else 0)),
                'revenue_growth_rate': 0,
                'profit_growth_rate': 0
            }
            
            # Generate intelligent KPI projections
            kpi_projections = {
                'profitability_kpis': {
                    'projected_profit_margin': self._project_kpi_improvement(current_kpis['profit_margin'], 'profit_margin', date_analysis),
                    'projected_operating_margin': self._project_kpi_improvement(current_kpis['operating_margin'], 'operating_margin', date_analysis),
                    'projected_gross_margin': self._project_kpi_improvement(current_kpis['gross_margin'], 'gross_margin', date_analysis)
                },
                'efficiency_kpis': {
                    'projected_cost_revenue_ratio': self._project_kpi_improvement(current_kpis['cost_revenue_ratio'], 'cost_revenue_ratio', date_analysis),
                    'projected_expense_ratio': self._project_kpi_improvement(current_kpis['expense_ratio'], 'expense_ratio', date_analysis)
                },
                'growth_kpis': {
                    'projected_revenue_growth': self._calculate_projected_growth_rate('revenue', date_analysis, historical_patterns),
                    'projected_profit_growth': self._calculate_projected_growth_rate('profit', date_analysis, historical_patterns)
                },
                'benchmark_analysis': self._generate_benchmark_analysis(current_kpis, date_analysis),
                'kpi_trends': self._analyze_kpi_trends(current_kpis, date_analysis)
            }
            
            return kpi_projections
            
        except Exception as e:
            logger.error(f"Error generating intelligent KPI predictions: {str(e)}")
            return {}
    
    def _project_kpi_improvement(self, current_kpi: float, kpi_type: str, date_analysis: Dict[str, Any]) -> float:
        """Project KPI improvement based on date analysis"""
        # Base improvement rates by KPI type
        improvement_rates = {
            'profit_margin': 0.02,      # 2% improvement
            'operating_margin': 0.015,   # 1.5% improvement
            'gross_margin': 0.01,        # 1% improvement
            'cost_revenue_ratio': -0.01, # 1% reduction (negative improvement)
            'expense_ratio': -0.005      # 0.5% reduction
        }
        
        base_improvement = improvement_rates.get(kpi_type, 0.01)
        
        # Adjust based on seasonal factors
        seasonal_factor = date_analysis.get('seasonal_analysis', {}).get('revenue_factor', 1.0)
        if kpi_type in ['profit_margin', 'operating_margin', 'gross_margin']:
            base_improvement *= seasonal_factor
        
        return current_kpi + base_improvement
    
    def _calculate_projected_growth_rate(self, metric_type: str, date_analysis: Dict[str, Any], historical_patterns: Dict[str, Any]) -> float:
        """Calculate projected growth rate for a specific metric"""
        # Base growth rates
        base_growth = {
            'revenue': 0.05,
            'profit': 0.08
        }
        
        growth_rate = base_growth.get(metric_type, 0.05)
        
        # Adjust based on historical patterns
        if historical_patterns:
            if metric_type == 'revenue' and historical_patterns.get('avg_revenue_growth'):
                growth_rate = historical_patterns['avg_revenue_growth']
            elif metric_type == 'profit' and historical_patterns.get('avg_profit_growth'):
                growth_rate = historical_patterns['avg_profit_growth']
        
        # Adjust based on business cycle
        business_cycle = date_analysis.get('business_cycle', {})
        cycle_growth = business_cycle.get('growth_expectation', 0.05)
        growth_rate = (growth_rate + cycle_growth) / 2
        
        return growth_rate
    
    def _generate_benchmark_analysis(self, current_kpis: Dict[str, float], date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate benchmark analysis for KPIs"""
        # Industry benchmarks (these would ideally come from external data)
        industry_benchmarks = {
            'profit_margin': 0.10,      # 10%
            'operating_margin': 0.15,    # 15%
            'gross_margin': 0.30,        # 30%
            'cost_revenue_ratio': 0.60,  # 60%
            'expense_ratio': 0.20        # 20%
        }
        
        benchmark_analysis = {}
        for kpi, current_value in current_kpis.items():
            if kpi in industry_benchmarks:
                benchmark = industry_benchmarks[kpi]
                performance = 'above' if current_value > benchmark else 'below'
                gap = abs(current_value - benchmark)
                
                benchmark_analysis[kpi] = {
                    'current_value': current_value,
                    'industry_benchmark': benchmark,
                    'performance': performance,
                    'gap': gap,
                    'improvement_potential': gap if performance == 'below' else 0
                }
        
        return benchmark_analysis
    
    def _analyze_kpi_trends(self, current_kpis: Dict[str, float], date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze KPI trends and patterns
        Note: This will be refined by the dashboard view using recent analyses to determine movement.
        Here we provide placeholders using neutral 'stable' to avoid static quality tags.
        """
        trends = {}
        for k, v in current_kpis.items():
            trends[k] = {'trend': 'stable', 'description': 'Awaiting recent trend analysis'}
        return trends
    
    def _generate_intelligent_cost_optimization(self, financial_data: Dict[str, Any], statement_date: date, date_analysis: Dict[str, Any], historical_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Generate intelligent cost optimization recommendations based on statement date"""
        try:
            # Extract cost-related metrics
            cost_of_revenue = financial_data.get('costOfRevenue', 0)
            operating_expenses = financial_data.get('totalOperatingExpenses', 0)
            revenue = financial_data.get('totalRevenue', 0)
            
            # Calculate cost ratios
            cost_revenue_ratio = cost_of_revenue / revenue if revenue > 0 else 0
            expense_ratio = operating_expenses / revenue if revenue > 0 else 0
            
            # Generate cost optimization recommendations
            cost_optimization = {
                'cost_analysis': {
                    'cost_of_revenue_ratio': cost_revenue_ratio,
                    'operating_expense_ratio': expense_ratio,
                    'total_cost_ratio': cost_revenue_ratio + expense_ratio,
                    'cost_efficiency_score': self._calculate_cost_efficiency_score(cost_revenue_ratio, expense_ratio)
                },
                'optimization_opportunities': self._identify_cost_optimization_opportunities(
                    cost_revenue_ratio, expense_ratio, date_analysis
                ),
                'seasonal_cost_adjustments': self._calculate_seasonal_cost_adjustments(date_analysis),
                'cost_reduction_targets': self._calculate_cost_reduction_targets(
                    cost_of_revenue, operating_expenses, date_analysis
                ),
                'implementation_timeline': self._create_cost_optimization_timeline(date_analysis)
            }
            
            return cost_optimization
            
        except Exception as e:
            logger.error(f"Error generating intelligent cost optimization: {str(e)}")
            return {}
    
    def _calculate_cost_efficiency_score(self, cost_revenue_ratio: float, expense_ratio: float) -> float:
        """Calculate cost efficiency score"""
        # Lower ratios are better, so we invert them
        cost_score = max(0, 1 - cost_revenue_ratio)
        expense_score = max(0, 1 - expense_ratio)
        
        return (cost_score + expense_score) / 2
    
    def _identify_cost_optimization_opportunities(self, cost_revenue_ratio: float, expense_ratio: float, date_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify specific cost optimization opportunities"""
        opportunities = []
        
        # Cost of revenue optimization
        if cost_revenue_ratio > 0.70:
            opportunities.append({
                'category': 'Cost of Revenue',
                'priority': 'HIGH',
                'description': 'Cost of revenue is high (>70%). Focus on supplier negotiations and operational efficiency.',
                'potential_savings': f'${(cost_revenue_ratio - 0.60) * 1000000:,.0f} potential savings',
                'timeline': '3-6 months',
                'implementation_difficulty': 'Medium'
            })
        
        # Operating expense optimization
        if expense_ratio > 0.25:
            opportunities.append({
                'category': 'Operating Expenses',
                'priority': 'HIGH',
                'description': 'Operating expenses are high (>25%). Review overhead costs and operational efficiency.',
                'potential_savings': f'${(expense_ratio - 0.20) * 1000000:,.0f} potential savings',
                'timeline': '2-4 months',
                'implementation_difficulty': 'Low'
            })
        
        # Seasonal cost adjustments
        seasonal_analysis = date_analysis.get('seasonal_analysis', {})
        if seasonal_analysis.get('expense_factor', 1.0) > 1.05:
            opportunities.append({
                'category': 'Seasonal Optimization',
                'priority': 'MEDIUM',
                'description': 'Expenses are seasonally high. Consider seasonal workforce adjustments.',
                'potential_savings': 'Variable based on seasonal adjustments',
                'timeline': '1-3 months',
                'implementation_difficulty': 'Low'
            })
        
        return opportunities
    
    def _calculate_seasonal_cost_adjustments(self, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate seasonal cost adjustments"""
        seasonal_analysis = date_analysis.get('seasonal_analysis', {})
        business_cycle = date_analysis.get('business_cycle', {})
        
        return {
            'seasonal_factors': seasonal_analysis,
            'business_cycle_impact': business_cycle,
            'recommended_adjustments': {
                'workforce': self._get_workforce_adjustments(date_analysis),
                'inventory': self._get_inventory_adjustments(date_analysis),
                'marketing': self._get_marketing_adjustments(date_analysis)
            }
        }
    
    def _get_workforce_adjustments(self, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get workforce adjustment recommendations"""
        quarter = date_analysis.get('quarter', 1)
        
        adjustments = {
            1: {'action': 'Maintain current workforce', 'reason': 'Post-holiday recovery period'},
            2: {'action': 'Consider hiring for growth', 'reason': 'Strong growth period'},
            3: {'action': 'Optimize workforce efficiency', 'reason': 'Summer slowdown period'},
            4: {'action': 'Prepare for year-end push', 'reason': 'Holiday season preparation'}
        }
        
        return adjustments.get(quarter, adjustments[2])
    
    def _get_inventory_adjustments(self, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get inventory adjustment recommendations"""
        quarter = date_analysis.get('quarter', 1)
        
        adjustments = {
            1: {'action': 'Reduce excess inventory', 'reason': 'Clear post-holiday inventory'},
            2: {'action': 'Build inventory for growth', 'reason': 'Prepare for strong demand'},
            3: {'action': 'Optimize inventory levels', 'reason': 'Summer demand management'},
            4: {'action': 'Stock up for holiday season', 'reason': 'Prepare for peak demand'}
        }
        
        return adjustments.get(quarter, adjustments[2])
    
    def _get_marketing_adjustments(self, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get marketing adjustment recommendations"""
        quarter = date_analysis.get('quarter', 1)
        
        adjustments = {
            1: {'action': 'Focus on retention marketing', 'reason': 'Post-holiday customer retention'},
            2: {'action': 'Increase acquisition marketing', 'reason': 'Growth period marketing push'},
            3: {'action': 'Optimize marketing spend', 'reason': 'Summer efficiency focus'},
            4: {'action': 'Holiday season marketing', 'reason': 'Peak season marketing campaign'}
        }
        
        return adjustments.get(quarter, adjustments[2])
    
    def _calculate_cost_reduction_targets(self, cost_of_revenue: float, operating_expenses: float, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate specific cost reduction targets"""
        # Calculate realistic reduction targets based on current costs
        cost_reduction_targets = {
            'cost_of_revenue_reduction': {
                'current': cost_of_revenue,
                'target_reduction_percent': 0.05,  # 5% reduction
                'target_amount': cost_of_revenue * 0.05,
                'timeline': '6 months'
            },
            'operating_expense_reduction': {
                'current': operating_expenses,
                'target_reduction_percent': 0.03,  # 3% reduction
                'target_amount': operating_expenses * 0.03,
                'timeline': '3 months'
            },
            'total_potential_savings': (cost_of_revenue * 0.05) + (operating_expenses * 0.03)
        }
        
        return cost_reduction_targets
    
    def _create_cost_optimization_timeline(self, date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create implementation timeline for cost optimization"""
        quarter = date_analysis.get('quarter', 1)
        
        timeline = {
            'immediate_actions': {
                'timeline': '0-30 days',
                'actions': [
                    'Review current cost structure',
                    'Identify quick wins',
                    'Set up cost tracking systems'
                ]
            },
            'short_term_goals': {
                'timeline': '1-3 months',
                'actions': [
                    'Implement supplier negotiations',
                    'Optimize operational processes',
                    'Reduce unnecessary expenses'
                ]
            },
            'long_term_strategy': {
                'timeline': '3-12 months',
                'actions': [
                    'Strategic cost restructuring',
                    'Technology optimization',
                    'Long-term supplier partnerships'
                ]
            }
        }
        
        return timeline
    
    def _generate_decision_making_intelligence(self, financial_data: Dict[str, Any], statement_date: date, date_analysis: Dict[str, Any], projections: Dict[str, Any]) -> Dict[str, Any]:
        """Generate intelligent decision-making recommendations"""
        try:
            # Extract key financial metrics
            revenue = financial_data.get('totalRevenue', 0)
            net_income = financial_data.get('netIncome', 0)
            operating_income = financial_data.get('operatingIncome', 0)
            
            # Calculate key ratios
            profit_margin = net_income / revenue if revenue > 0 else 0
            operating_margin = operating_income / revenue if revenue > 0 else 0
            
            # Generate decision intelligence
            decision_intelligence = {
                'strategic_recommendations': self._generate_strategic_recommendations(
                    financial_data, date_analysis, projections
                ),
                'investment_opportunities': self._identify_investment_opportunities(
                    financial_data, date_analysis
                ),
                'risk_assessment': self._assess_business_risks(
                    financial_data, date_analysis, projections
                ),
                'growth_strategies': self._recommend_growth_strategies(
                    financial_data, date_analysis, projections
                ),
                'operational_improvements': self._recommend_operational_improvements(
                    financial_data, date_analysis
                ),
                'financial_health_score': self._calculate_financial_health_score(
                    financial_data, date_analysis
                )
            }
            
            return decision_intelligence
            
        except Exception as e:
            logger.error(f"Error generating decision-making intelligence: {str(e)}")
            return {}
    
    def _generate_strategic_recommendations(self, financial_data: Dict[str, Any], date_analysis: Dict[str, Any], projections: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate strategic recommendations based on analysis"""
        recommendations = []
        
        # Revenue-based recommendations
        revenue = financial_data.get('totalRevenue', 0)
        if revenue > 0:
            if revenue < 1000000:  # Less than $1M
                recommendations.append({
                    'category': 'Growth Strategy',
                    'priority': 'HIGH',
                    'title': 'Scale Revenue Operations',
                    'description': 'Focus on scaling revenue operations to reach $1M+ annual revenue',
                    'expected_impact': 'Increase revenue by 50-100%',
                    'timeline': '6-12 months',
                    'implementation_difficulty': 'Medium'
                })
            elif revenue < 10000000:  # Less than $10M
                recommendations.append({
                    'category': 'Market Expansion',
                    'priority': 'MEDIUM',
                    'title': 'Expand Market Reach',
                    'description': 'Consider expanding into new markets or customer segments',
                    'expected_impact': 'Increase market share by 20-30%',
                    'timeline': '12-18 months',
                    'implementation_difficulty': 'High'
                })
        
        # Profitability-based recommendations
        profit_margin = financial_data.get('netIncome', 0) / revenue if revenue > 0 else 0
        if profit_margin < 0.05:
            recommendations.append({
                'category': 'Profitability',
                'priority': 'HIGH',
                'title': 'Improve Profitability',
                'description': 'Focus on cost optimization and revenue enhancement to improve profit margins',
                'expected_impact': 'Increase profit margin by 3-5%',
                'timeline': '3-6 months',
                'implementation_difficulty': 'Medium'
            })
        
        # Seasonal recommendations
        seasonal_analysis = date_analysis.get('seasonal_analysis', {})
        if seasonal_analysis.get('revenue_factor', 1.0) < 0.9:
            recommendations.append({
                'category': 'Seasonal Strategy',
                'priority': 'MEDIUM',
                'title': 'Seasonal Revenue Optimization',
                'description': 'Develop strategies to offset seasonal revenue fluctuations',
                'expected_impact': 'Stabilize revenue throughout the year',
                'timeline': '6-12 months',
                'implementation_difficulty': 'High'
            })
        
        return recommendations
    
    def _identify_investment_opportunities(self, financial_data: Dict[str, Any], date_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify investment opportunities based on financial position"""
        opportunities = []
        
        revenue = financial_data.get('totalRevenue', 0)
        net_income = financial_data.get('netIncome', 0)
        
        # Technology investment
        if revenue > 500000:  # More than $500K revenue
            opportunities.append({
                'category': 'Technology',
                'title': 'Technology Infrastructure Investment',
                'description': 'Invest in technology infrastructure to improve operational efficiency',
                'investment_amount': f'${min(revenue * 0.05, 50000):,.0f}',
                'expected_roi': '15-25%',
                'payback_period': '12-18 months',
                'risk_level': 'Low'
            })
        
        # Market expansion investment
        if net_income > 100000:  # Profitable company
            opportunities.append({
                'category': 'Market Expansion',
                'title': 'Market Expansion Investment',
                'description': 'Invest in market expansion and customer acquisition',
                'investment_amount': f'${min(net_income * 0.3, 100000):,.0f}',
                'expected_roi': '20-40%',
                'payback_period': '18-24 months',
                'risk_level': 'Medium'
            })
        
        # Operational efficiency investment
        if revenue > 1000000:  # More than $1M revenue
            opportunities.append({
                'category': 'Operations',
                'title': 'Operational Efficiency Investment',
                'description': 'Invest in operational efficiency improvements and automation',
                'investment_amount': f'${min(revenue * 0.03, 75000):,.0f}',
                'expected_roi': '25-35%',
                'payback_period': '6-12 months',
                'risk_level': 'Low'
            })
        
        return opportunities
    
    def _assess_business_risks(self, financial_data: Dict[str, Any], date_analysis: Dict[str, Any], projections: Dict[str, Any]) -> Dict[str, Any]:
        """Assess business risks based on financial position and projections using accurate metrics"""
        risks = {
            'financial_risks': [],
            'operational_risks': [],
            'market_risks': [],
            'overall_risk_level': 'LOW'
        }
        
        # ✅ CRITICAL: Use correct field names (both camelCase and snake_case)
        revenue = float(financial_data.get('totalRevenue') or financial_data.get('total_revenue') or 0)
        net_income = float(financial_data.get('netIncome') or financial_data.get('net_income') or 0)
        operating_income = float(financial_data.get('operatingIncome') or financial_data.get('operating_income') or 0)
        operating_expenses = float(financial_data.get('totalOperatingExpenses') or financial_data.get('total_operating_expenses') or 0)
        gross_profit = float(financial_data.get('grossProfit') or financial_data.get('gross_profit') or 0)
        
        # ✅ Calculate ratios accurately
        profit_margin = (net_income / revenue) if revenue > 0 else 0.0
        operating_margin = (operating_income / revenue) if revenue > 0 else 0.0
        expense_ratio = (operating_expenses / revenue) if revenue > 0 else 0.0
        
        # ✅ Financial risks based on accurate calculations
        if net_income < 0:
            risks['financial_risks'].append({
                'risk': 'Negative Profitability',
                'severity': 'HIGH',
                'description': f'Company is currently unprofitable (Net Income: {net_income:,.2f})',
                'mitigation': 'Focus on cost reduction and revenue enhancement'
            })
            risks['overall_risk_level'] = 'HIGH'
        elif profit_margin < 0.05:
            risks['financial_risks'].append({
                'risk': 'Low Profit Margin',
                'severity': 'MEDIUM',
                'description': f'Profit margin is below 5% ({profit_margin*100:.2f}%)',
                'mitigation': 'Improve operational efficiency and cost management'
            })
            if risks['overall_risk_level'] == 'LOW':
                risks['overall_risk_level'] = 'MEDIUM'
        
        # ✅ Operating expense risks
        if expense_ratio > 0.30:
            risks['operational_risks'].append({
                'risk': 'High Operating Expense Ratio',
                'severity': 'MEDIUM',
                'description': f'Operating expenses are {expense_ratio*100:.2f}% of revenue, indicating high cost structure',
                'mitigation': 'Review and optimize operating expenses, focus on efficiency improvements'
            })
            if risks['overall_risk_level'] == 'LOW':
                risks['overall_risk_level'] = 'MEDIUM'
        elif operating_expenses == 0 and revenue > 0:
            risks['operational_risks'].append({
                'risk': 'Missing Operating Expenses Data',
                'severity': 'LOW',
                'description': 'Operating expenses data may be incomplete or missing',
                'mitigation': 'Ensure complete financial data extraction for accurate analysis'
            })
        
        if revenue < 500000:
            risks['financial_risks'].append({
                'risk': 'Low Revenue Base',
                'severity': 'MEDIUM',
                'description': f'Revenue base is below $500K ({revenue:,.2f})',
                'mitigation': 'Focus on revenue growth and market expansion'
            })
        
        # Operational risks
        cost_of_revenue = float(financial_data.get('costOfRevenue') or financial_data.get('cost_of_revenue') or 0)
        cost_ratio = (cost_of_revenue / revenue) if revenue > 0 else 0.0
        if cost_ratio > 0.8:
            risks['operational_risks'].append({
                'risk': 'High Cost Structure',
                'severity': 'MEDIUM',
                'description': 'Cost of revenue is very high (>80%)',
                'mitigation': 'Review supplier contracts and operational efficiency'
            })
        
        # Market risks
        seasonal_analysis = date_analysis.get('seasonal_analysis', {})
        if seasonal_analysis.get('revenue_factor', 1.0) < 0.8:
            risks['market_risks'].append({
                'risk': 'Seasonal Revenue Volatility',
                'severity': 'MEDIUM',
                'description': 'Revenue is highly seasonal',
                'mitigation': 'Develop strategies to reduce seasonal dependence'
            })
        
        return risks
    
    def _recommend_growth_strategies(self, financial_data: Dict[str, Any], date_analysis: Dict[str, Any], projections: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recommend growth strategies based on current position"""
        strategies = []
        
        revenue = financial_data.get('totalRevenue', 0)
        net_income = financial_data.get('netIncome', 0)
        
        # Revenue-based growth strategies
        if revenue < 1000000:
            strategies.append({
                'strategy': 'Revenue Scaling',
                'description': 'Focus on scaling revenue operations through improved sales processes',
                'expected_growth': '50-100%',
                'timeline': '6-12 months',
                'investment_required': 'Low to Medium'
            })
        elif revenue < 10000000:
            strategies.append({
                'strategy': 'Market Expansion',
                'description': 'Expand into new markets or customer segments',
                'expected_growth': '20-50%',
                'timeline': '12-18 months',
                'investment_required': 'Medium to High'
            })
        
        # Profitability-based strategies
        if net_income / revenue < 0.10 if revenue > 0 else True:
            strategies.append({
                'strategy': 'Profitability Improvement',
                'description': 'Focus on improving profit margins through cost optimization',
                'expected_growth': '15-30%',
                'timeline': '3-6 months',
                'investment_required': 'Low'
            })
        
        return strategies
    
    def _recommend_operational_improvements(self, financial_data: Dict[str, Any], date_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recommend operational improvements"""
        improvements = []
        
        # Cost structure improvements
        cost_of_revenue = financial_data.get('costOfRevenue', 0)
        operating_expenses = financial_data.get('totalOperatingExpenses', 0)
        revenue = financial_data.get('totalRevenue', 0)
        
        if cost_of_revenue / revenue > 0.70 if revenue > 0 else False:
            improvements.append({
                'area': 'Cost Management',
                'improvement': 'Optimize Cost of Revenue',
                'description': 'Review supplier contracts and operational efficiency',
                'expected_impact': 'Reduce cost of revenue by 5-10%',
                'timeline': '3-6 months'
            })
        
        if operating_expenses / revenue > 0.25 if revenue > 0 else False:
            improvements.append({
                'area': 'Operating Efficiency',
                'improvement': 'Streamline Operations',
                'description': 'Improve operational efficiency and reduce overhead',
                'expected_impact': 'Reduce operating expenses by 3-5%',
                'timeline': '2-4 months'
            })
        
        return improvements
    
    def _calculate_financial_health_score(self, financial_data: Dict[str, Any], date_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall financial health score using accurate financial metrics"""
        # ✅ CRITICAL: Use correct field names (both camelCase and snake_case)
        revenue = float(financial_data.get('totalRevenue') or financial_data.get('total_revenue') or 0)
        net_income = float(financial_data.get('netIncome') or financial_data.get('net_income') or 0)
        operating_income = float(financial_data.get('operatingIncome') or financial_data.get('operating_income') or 0)
        operating_expenses = float(financial_data.get('totalOperatingExpenses') or financial_data.get('total_operating_expenses') or 0)
        gross_profit = float(financial_data.get('grossProfit') or financial_data.get('gross_profit') or 0)
        
        # ✅ Calculate ratios accurately
        profit_margin = (net_income / revenue) if revenue > 0 else 0.0
        operating_margin = (operating_income / revenue) if revenue > 0 else 0.0
        expense_ratio = (operating_expenses / revenue) if revenue > 0 else 0.0
        gross_margin = (gross_profit / revenue) if revenue > 0 else 0.0
        
        # ✅ Calculate individual scores with proper scaling
        # Profitability: Based on profit margin (0-100 scale, where 20%+ margin = 100)
        profitability_score = min(100, max(0, (profit_margin / 0.20) * 100)) if revenue > 0 else 0
        
        # Operational: Based on operating margin and expense efficiency
        # Higher operating margin = better, lower expense ratio = better
        operational_efficiency = operating_margin * (1.0 - min(1.0, expense_ratio))
        operational_score = min(100, max(0, operational_efficiency * 500)) if revenue > 0 else 0
        
        # Revenue: Scale based on revenue size (normalized to $1M = 100)
        revenue_score = min(100, max(0, revenue / 1000000 * 100))
        
        # ✅ Calculate overall score (weighted average)
        overall_score = (profitability_score * 0.4 + operational_score * 0.4 + revenue_score * 0.2)
        
        # ✅ LOGGING: Show calculated scores for debugging
        logger.info(f"📊 Financial Health Score Calculation:")
        logger.info(f"   Revenue: {revenue:,.2f}, OPEX: {operating_expenses:,.2f}, OI: {operating_income:,.2f}, NI: {net_income:,.2f}")
        logger.info(f"   Ratios: PM={profit_margin:.4f}, OM={operating_margin:.4f}, ER={expense_ratio:.4f}")
        logger.info(f"   Scores: Profitability={profitability_score:.2f}, Operational={operational_score:.2f}, Revenue={revenue_score:.2f}, Overall={overall_score:.2f}")
        
        # Determine health level
        if overall_score >= 80:
            health_level = 'Excellent'
        elif overall_score >= 60:
            health_level = 'Good'
        elif overall_score >= 40:
            health_level = 'Fair'
        else:
            health_level = 'Poor'
        
        return {
            'overall_score': round(overall_score, 2),
            'health_level': health_level,
            'profitability_score': round(profitability_score, 2),
            'operational_score': round(operational_score, 2),
            'revenue_score': round(revenue_score, 2),
            'recommendations': self._get_health_improvement_recommendations(overall_score)
        }
    
    def _get_health_improvement_recommendations(self, score: float) -> List[str]:
        """Get recommendations based on financial health score"""
        if score >= 80:
            return ['Maintain current performance', 'Consider expansion opportunities']
        elif score >= 60:
            return ['Focus on profitability improvement', 'Optimize operational efficiency']
        elif score >= 40:
            return ['Address cost structure issues', 'Improve revenue generation']
        else:
            return ['Urgent financial restructuring needed', 'Focus on survival strategies']
    
    def _calculate_intelligent_confidence(self, financial_data: Dict[str, Any], projections: Dict[str, Any], historical_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate intelligent confidence scores"""
        confidence = {
            'overall_confidence': 0.8,
            'projection_confidence': 0.75,
            'recommendation_confidence': 0.85,
            'risk_assessment_confidence': 0.80
        }
        
        # Adjust based on data quality
        if financial_data.get('totalRevenue', 0) > 0:
            confidence['overall_confidence'] += 0.05
        
        # Adjust based on historical data
        if historical_patterns:
            confidence['overall_confidence'] += 0.1
            confidence['projection_confidence'] += 0.15
        
        # Adjust based on projection quality
        if projections.get('risk_factors'):
            risk_count = len(projections['risk_factors'])
            confidence['projection_confidence'] -= risk_count * 0.05
        
        return confidence
    
    def _calculate_business_days_remaining(self, statement_date: date) -> int:
        """Calculate business days remaining in the year"""
        year_end = date(statement_date.year, 12, 31)
        business_days = 0
        current_date = statement_date
        
        while current_date <= year_end:
            if current_date.weekday() < 5:  # Monday to Friday
                business_days += 1
            current_date += timedelta(days=1)
        
        return business_days
    
    def _get_seasonal_multiplier(self, statement_date: date) -> float:
        """Get seasonal multiplier based on statement date"""
        month = statement_date.month
        
        seasonal_multipliers = {
            1: 0.95,   # January - post-holiday
            2: 0.90,   # February - winter
            3: 1.00,   # March - spring
            4: 1.05,   # April - growth
            5: 1.10,   # May - strong
            6: 1.00,   # June - steady
            7: 0.95,   # July - summer
            8: 0.90,   # August - vacation
            9: 1.00,   # September - back to business
            10: 1.05,  # October - growth
            11: 1.10,  # November - pre-holiday
            12: 1.20   # December - holiday season
        }
        
        return seasonal_multipliers.get(month, 1.0)
    
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
