# IntelligentDataExtractor.py - Advanced Financial Data Extraction
"""
Intelligent data extraction system that can automatically identify and process
financial data from any CSV/Excel format using fuzzy matching, pattern recognition,
and machine learning techniques.
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Optional, Tuple, Any, Union
from difflib import SequenceMatcher
from fuzzywuzzy import fuzz, process
import logging
from datetime import datetime, date
import warnings

from Tazama.Services.TazamaService import TazamaAnalysisService
from Tazama.core.report_generator import TazamaReportGenerator
from Tazama.models import TazamaAnalysisRequest, FinancialReport

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class IntelligentDataExtractor:
    """
    Advanced financial data extractor that can intelligently identify and process
    financial data from any format using multiple techniques:
    1. Fuzzy string matching
    2. Pattern recognition
    3. Machine learning-based classification
    4. Context-aware extraction
    5. Multi-language support
    """

    def __init__(self):
        self.financial_patterns = self._initialize_financial_patterns()
        self.currency_patterns = self._initialize_currency_patterns()
        self.date_patterns = self._initialize_date_patterns()
        self.confidence_threshold = 0.7
        
    def _initialize_financial_patterns(self) -> Dict[str, List[str]]:
        """Initialize comprehensive financial metric patterns"""
        return {
            'total_revenue': [
                # English patterns
                'total revenue', 'revenue', 'sales', 'net sales', 'gross sales',
                'total sales', 'income', 'total income', 'gross revenue',
                'net revenue', 'operating revenue', 'business revenue',
                'turnover', 'total turnover', 'net turnover',
                # Variations
                'rev', 'sales revenue', 'total sales revenue',
                'operating income', 'gross income', 'net income',
                # Multi-language (basic)
                'ventas', 'ingresos', 'chiffre d\'affaires', 'umsatz',
                'receita', 'entrate', 'inkomsten', 'доходы'
            ],
            'cost_of_revenue': [
                'cost of revenue', 'cost of sales', 'cogs', 'cost of goods sold',
                'direct costs', 'cost of products sold', 'cost of services',
                'variable costs', 'production costs', 'manufacturing costs',
                'cost of sales revenue', 'cost of goods', 'cost of services sold',
                # Variations
                'cogs', 'cost of sales', 'direct cost', 'product cost',
                # Multi-language
                'costo de ventas', 'coût des ventes', 'kosten der umsätze',
                'custo das vendas', 'costo delle vendite', 'kostprijs verkopen'
            ],
            'gross_profit': [
                'gross profit', 'gross income', 'gross margin', 'gross earnings',
                'gross operating profit', 'gross business profit',
                'profit before expenses', 'gross operating income',
                # Variations
                'gross', 'gross profit margin', 'gross profit amount',
                # Multi-language
                'beneficio bruto', 'bénéfice brut', 'bruttogewinn',
                'lucro bruto', 'utile lordo', 'bruto winst'
            ],
            'total_operating_expenses': [
                'operating expenses', 'operating costs', 'opex', 'operating expenditure',
                'total operating expenses', 'operating overhead', 'operating costs total',
                'administrative expenses', 'general expenses', 'operating overheads',
                'total opex', 'operating expenditure total', 'operating costs total',
                # Variations
                'opex', 'operating exp', 'operating cost', 'total opex',
                # Multi-language
                'gastos operativos', 'charges d\'exploitation', 'betriebsausgaben',
                'custos operacionais', 'costi operativi', 'operationele kosten'
            ],
            'operating_income': [
                'operating income', 'operating profit', 'ebit', 'operating earnings',
                'operating result', 'operating profit before tax', 'operating earnings',
                'business income', 'operating business income', 'operating profit margin',
                'operating income before tax', 'operating profit before interest',
                # Variations
                'ebit', 'operating profit', 'operating income', 'operating result',
                # Multi-language
                'ingresos operativos', 'résultat d\'exploitation', 'betriebsergebnis',
                'receita operacional', 'risultato operativo', 'operationeel resultaat'
            ],
            'net_income': [
                'net income', 'net profit', 'net earnings', 'net result',
                'profit after tax', 'net profit after tax', 'net earnings after tax',
                'bottom line', 'net business income', 'net operating income',
                'net profit margin', 'net income margin', 'net earnings margin',
                # Variations
                'net income', 'net profit', 'net earnings', 'bottom line',
                # Multi-language
                'ingreso neto', 'bénéfice net', 'nettoergebnis',
                'receita líquida', 'utile netto', 'netto winst'
            ],
            'research_development': [
                'research and development', 'r&d', 'research development',
                'research and development expenses', 'rd expenses', 'rd costs',
                'research costs', 'development costs', 'innovation costs',
                'research expenditure', 'development expenditure', 'rd expenditure',
                # Variations
                'r&d', 'rd', 'research', 'development', 'innovation',
                # Multi-language
                'investigación y desarrollo', 'recherche et développement',
                'forschung und entwicklung', 'pesquisa e desenvolvimento',
                'ricerca e sviluppo', 'onderzoek en ontwikkeling'
            ],
            'total_assets': [
                'total assets', 'assets', 'total asset value', 'asset base',
                'total company assets', 'total business assets', 'asset total',
                'total asset amount', 'total asset value', 'asset portfolio',
                # Variations
                'assets', 'total assets', 'asset base', 'asset value',
                # Multi-language
                'activos totales', 'total des actifs', 'gesamtvermögen',
                'ativos totais', 'totale attivo', 'totale activa'
            ],
            'total_liabilities': [
                'total liabilities', 'liabilities', 'total debt', 'total obligations',
                'total company liabilities', 'total business liabilities',
                'liability total', 'total liability amount', 'debt total',
                'total obligations', 'total debt obligations',
                # Variations
                'liabilities', 'total liabilities', 'debt', 'obligations',
                # Multi-language
                'pasivos totales', 'total des passifs', 'gesamtverbindlichkeiten',
                'passivos totais', 'totale passivo', 'totale passiva'
            ],
            'shareholders_equity': [
                'shareholders equity', 'stockholders equity', 'equity', 'owner equity',
                'shareholder equity', 'stockholder equity', 'total equity',
                'equity capital', 'share capital', 'owner capital',
                'shareholder capital', 'stockholder capital',
                # Variations
                'equity', 'shareholder equity', 'stockholder equity', 'owner equity',
                # Multi-language
                'patrimonio neto', 'capitaux propres', 'eigenkapital',
                'patrimônio líquido', 'patrimonio netto', 'eigen vermogen'
            ]
        }

    def _initialize_currency_patterns(self) -> List[str]:
        """Initialize currency and number patterns"""
        return [
            r'[\$€£¥₹]?\s*[\d,]+\.?\d*',  # Currency symbols with numbers
            r'[\d,]+\.?\d*\s*[\$€£¥₹]',  # Numbers with currency symbols
            r'[\d,]+\.?\d*',  # Plain numbers with commas
            r'[\d]+\.?\d*',  # Plain numbers
            r'\([\d,]+\.?\d*\)',  # Negative numbers in parentheses
            r'-[\d,]+\.?\d*',  # Negative numbers with minus sign
        ]

    def _initialize_date_patterns(self) -> List[str]:
        """Initialize date patterns"""
        return [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
            r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
            r'\d{1,2}/\d{1,2}/\d{4}',  # M/D/YYYY
            r'\d{1,2}-\d{1,2}-\d{4}',  # M-D-YYYY
            r'\d{4}\.\d{2}\.\d{2}',  # YYYY.MM.DD
        ]

    def extract_financial_data(self, file_path: str, file_type: str = 'auto') -> Dict[str, Any]:
        """
        Main extraction method that intelligently processes any financial file
        
        Args:
            file_path: Path to the financial file
            file_type: Type of file (csv, xlsx, xls, auto)
            
        Returns:
            Dictionary with extracted financial data and metadata
        """
        try:
            logger.info(f"Starting intelligent extraction from: {file_path}")
            
            # Load the file
            raw_data = self._load_file(file_path, file_type)
            
            if raw_data is None:
                return {
                    'success': False,
                    'error': 'Failed to load file'
                }
            
            # Analyze file structure
            structure_analysis = self._analyze_file_structure(raw_data)
            
            # Extract financial data using multiple strategies
            extraction_results = []
            
            # Strategy 1: Direct column matching
            direct_result = self._extract_direct_matching(raw_data)
            if direct_result['confidence'] > self.confidence_threshold:
                extraction_results.append(direct_result)
            
            # Strategy 2: Pattern-based extraction
            pattern_result = self._extract_pattern_based(raw_data)
            if pattern_result['confidence'] > self.confidence_threshold:
                extraction_results.append(pattern_result)
            
            # Strategy 3: Context-aware extraction
            context_result = self._extract_context_aware(raw_data)
            if context_result['confidence'] > self.confidence_threshold:
                extraction_results.append(context_result)
            
            # Strategy 4: Machine learning-based extraction
            ml_result = self._extract_ml_based(raw_data)
            if ml_result['confidence'] > self.confidence_threshold:
                extraction_results.append(ml_result)
            
            # Choose best extraction result
            best_result = self._choose_best_extraction(extraction_results)
            
            if best_result is None:
                return {
                    'success': False,
                    'error': 'No reliable extraction method found',
                    'structure_analysis': structure_analysis
                }
            
            # Post-process and validate
            processed_data = self._post_process_extraction(best_result)
            
            return {
                'success': True,
                'extracted_data': processed_data,
                'extraction_method': best_result['method'],
                'confidence': best_result['confidence'],
                'structure_analysis': structure_analysis,
                'metadata': {
                    'file_path': file_path,
                    'extraction_timestamp': datetime.now().isoformat(),
                    'total_records': len(processed_data.get('records', [])),
                    'extracted_metrics': list(processed_data.get('metrics', {}).keys())
                }
            }
            
        except Exception as e:
            logger.error(f"Error in intelligent extraction: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _load_file(self, file_path: str, file_type: str) -> Optional[Dict[str, pd.DataFrame]]:
        """Load file with automatic type detection"""
        try:
            if file_type == 'auto':
                file_type = file_path.split('.')[-1].lower()
            
            if file_type in ['csv', 'tsv']:
                # Try different encodings and separators
                for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                    for sep in [',', ';', '\t', '|']:
                        try:
                            df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                            if len(df.columns) > 1:  # Valid CSV
                                return {'Sheet1': df}
                        except:
                            continue
            
            elif file_type in ['xlsx', 'xls']:
                # Load Excel file with all sheets
                excel_data = pd.read_excel(file_path, sheet_name=None, engine='openpyxl' if file_type == 'xlsx' else 'xlrd')
                return excel_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading file: {str(e)}")
            return None

    def _analyze_file_structure(self, raw_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Analyze the structure of the loaded file"""
        analysis = {
            'total_sheets': len(raw_data),
            'sheets': {},
            'overall_confidence': 0.0,
            'recommended_strategy': 'unknown'
        }
        
        for sheet_name, df in raw_data.items():
            sheet_analysis = {
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': list(df.columns),
                'data_types': df.dtypes.to_dict(),
                'has_numeric_data': self._has_numeric_data(df),
                'has_date_columns': self._has_date_columns(df),
                'financial_indicators': self._detect_financial_indicators(df),
                'confidence': 0.0
            }
            
            # Calculate confidence based on indicators
            confidence = self._calculate_structure_confidence(sheet_analysis)
            sheet_analysis['confidence'] = confidence
            
            analysis['sheets'][sheet_name] = sheet_analysis
        
        # Determine overall confidence and recommended strategy
        max_confidence = max(sheet['confidence'] for sheet in analysis['sheets'].values())
        analysis['overall_confidence'] = max_confidence
        
        if max_confidence > 0.8:
            analysis['recommended_strategy'] = 'direct_matching'
        elif max_confidence > 0.6:
            analysis['recommended_strategy'] = 'pattern_based'
        elif max_confidence > 0.4:
            analysis['recommended_strategy'] = 'context_aware'
        else:
            analysis['recommended_strategy'] = 'ml_based'
        
        return analysis

    def _extract_direct_matching(self, raw_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Extract using direct column name matching"""
        results = {
            'method': 'direct_matching',
            'confidence': 0.0,
            'extracted_data': {},
            'matched_columns': {}
        }
        
        total_confidence = 0
        total_sheets = 0
        
        for sheet_name, df in raw_data.items():
            sheet_results = {
                'metrics': {},
                'matched_columns': {},
                'confidence': 0.0
            }
            used_columns: set[str] = set()
            
            # Try to match each financial metric
            for metric, patterns in self.financial_patterns.items():
                # Avoid reusing the same column for multiple metrics
                remaining_columns = [c for c in df.columns if str(c) not in used_columns]
                best_match = self._find_best_column_match(remaining_columns, patterns)
                if best_match:
                    sheet_results['matched_columns'][metric] = best_match
                    sheet_results['metrics'][metric] = self._extract_metric_values(df, best_match)
                    sheet_results['confidence'] += 0.1
                    used_columns.add(str(best_match))
            
            # Calculate sheet confidence
            if sheet_results['matched_columns']:
                sheet_results['confidence'] = min(sheet_results['confidence'], 1.0)
                total_confidence += sheet_results['confidence']
                total_sheets += 1
            
            results['extracted_data'][sheet_name] = sheet_results
        
        if total_sheets > 0:
            results['confidence'] = total_confidence / total_sheets
        
        return results

    def _extract_pattern_based(self, raw_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Extract using pattern recognition in data"""
        results = {
            'method': 'pattern_based',
            'confidence': 0.0,
            'extracted_data': {},
            'patterns_found': {}
        }
        
        total_confidence = 0
        total_sheets = 0
        
        for sheet_name, df in raw_data.items():
            sheet_results = {
                'metrics': {},
                'patterns_found': {},
                'confidence': 0.0
            }
            
            # Look for financial patterns in the data
            for metric, patterns in self.financial_patterns.items():
                pattern_match = self._find_pattern_in_data(df, patterns)
                if pattern_match:
                    sheet_results['patterns_found'][metric] = pattern_match
                    sheet_results['metrics'][metric] = self._extract_values_by_pattern(df, pattern_match)
                    sheet_results['confidence'] += 0.15
            
            if sheet_results['patterns_found']:
                sheet_results['confidence'] = min(sheet_results['confidence'], 1.0)
                total_confidence += sheet_results['confidence']
                total_sheets += 1
            
            results['extracted_data'][sheet_name] = sheet_results
        
        if total_sheets > 0:
            results['confidence'] = total_confidence / total_sheets
        
        return results

    def _extract_context_aware(self, raw_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Extract using context-aware analysis"""
        results = {
            'method': 'context_aware',
            'confidence': 0.0,
            'extracted_data': {},
            'context_analysis': {}
        }
        
        total_confidence = 0
        total_sheets = 0
        
        for sheet_name, df in raw_data.items():
            sheet_results = {
                'metrics': {},
                'context_analysis': {},
                'confidence': 0.0
            }
            
            # Analyze context around potential financial data
            context_analysis = self._analyze_financial_context(df)
            
            for metric, context_info in context_analysis.items():
                if context_info['confidence'] > 0.5:
                    sheet_results['context_analysis'][metric] = context_info
                    sheet_results['metrics'][metric] = self._extract_by_context(df, context_info)
                    sheet_results['confidence'] += context_info['confidence'] * 0.2
            
            if sheet_results['context_analysis']:
                sheet_results['confidence'] = min(sheet_results['confidence'], 1.0)
                total_confidence += sheet_results['confidence']
                total_sheets += 1
            
            results['extracted_data'][sheet_name] = sheet_results
        
        if total_sheets > 0:
            results['confidence'] = total_confidence / total_sheets
        
        return results

    def _extract_ml_based(self, raw_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Extract using machine learning-based classification"""
        results = {
            'method': 'ml_based',
            'confidence': 0.0,
            'extracted_data': {},
            'ml_predictions': {}
        }
        
        # This would use a trained ML model to classify columns
        # For now, implement a simplified version using heuristics
        
        total_confidence = 0
        total_sheets = 0
        
        for sheet_name, df in raw_data.items():
            sheet_results = {
                'metrics': {},
                'ml_predictions': {},
                'confidence': 0.0
            }
            
            # Use heuristics to predict financial metrics
            for metric, patterns in self.financial_patterns.items():
                ml_prediction = self._predict_metric_column(df, metric, patterns)
                if ml_prediction['confidence'] > 0.6:
                    sheet_results['ml_predictions'][metric] = ml_prediction
                    sheet_results['metrics'][metric] = self._extract_values_by_prediction(df, ml_prediction)
                    sheet_results['confidence'] += ml_prediction['confidence'] * 0.3
            
            if sheet_results['ml_predictions']:
                sheet_results['confidence'] = min(sheet_results['confidence'], 1.0)
                total_confidence += sheet_results['confidence']
                total_sheets += 1
            
            results['extracted_data'][sheet_name] = sheet_results
        
        if total_sheets > 0:
            results['confidence'] = total_confidence / total_sheets
        
        return results

    def _find_best_column_match(self, columns: List[str], patterns: List[str]) -> Optional[str]:
        """Find the best matching column for a set of patterns"""
        best_match = None
        best_score = 0
        
        for column in columns:
            for pattern in patterns:
                # Use fuzzy matching
                score = fuzz.ratio(column.lower(), pattern.lower())
                if score > best_score and score > 70:  # 70% similarity threshold
                    best_score = score
                    best_match = column
        
        return best_match

    def _find_pattern_in_data(self, df: pd.DataFrame, patterns: List[str]) -> Optional[Dict[str, Any]]:
        """Find financial patterns in the data itself"""
        for col in df.columns:
            for pattern in patterns:
                if any(pattern.lower() in str(cell).lower() for cell in df[col].dropna().head(10)):
                    return {
                        'column': col,
                        'pattern': pattern,
                        'confidence': 0.8
                    }
        return None

    def _analyze_financial_context(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """Analyze financial context around data"""
        context_analysis = {}
        
        # Look for financial statement structure
        for col in df.columns:
            col_data = df[col].dropna()
            
            # Check if column contains financial metrics
            if self._is_financial_column(col_data):
                # Try to identify what type of financial metric
                for metric, patterns in self.financial_patterns.items():
                    confidence = self._calculate_context_confidence(col_data, patterns)
                    if confidence > 0.5:
                        context_analysis[metric] = {
                            'column': col,
                            'confidence': confidence,
                            'context_type': 'financial_data'
                        }
        
        return context_analysis

    def _predict_metric_column(self, df: pd.DataFrame, metric: str, patterns: List[str]) -> Dict[str, Any]:
        """Predict which column contains a specific financial metric"""
        predictions = []
        
        for col in df.columns:
            col_data = df[col].dropna()
            
            # Calculate prediction score based on multiple factors
            score = 0
            
            # Factor 1: Column name similarity
            name_score = max(fuzz.ratio(col.lower(), pattern.lower()) for pattern in patterns) / 100
            score += name_score * 0.3
            
            # Factor 2: Data type and format
            if self._is_numeric_financial_data(col_data):
                score += 0.3
            
            # Factor 3: Value ranges
            if self._has_financial_value_range(col_data, metric):
                score += 0.2
            
            # Factor 4: Context clues
            if self._has_financial_context_clues(col_data):
                score += 0.2
            
            predictions.append({
                'column': col,
                'score': score,
                'confidence': min(score, 1.0)
            })
        
        # Return best prediction
        if predictions:
            best_prediction = max(predictions, key=lambda x: x['score'])
            if best_prediction['confidence'] > 0.6:
                return best_prediction
        
        return {'column': None, 'confidence': 0.0}

    def _choose_best_extraction(self, extraction_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Choose the best extraction result based on confidence and completeness"""
        if not extraction_results:
            return None
        
        # Sort by confidence and completeness
        best_result = max(extraction_results, key=lambda x: (
            x['confidence'],
            len(x.get('extracted_data', {}))
        ))
        
        return best_result

    def _post_process_extraction(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process and validate extracted data"""
        processed_data = {
            'records': [],
            'metrics': {},
            'validation_results': {},
            'data_quality_score': 0.0
        }
        
        # Process each sheet
        for sheet_name, sheet_data in extraction_result['extracted_data'].items():
            if 'metrics' in sheet_data:
                # Convert to standardized format
                standardized_metrics = self._standardize_metrics(sheet_data['metrics'])

                # Heuristic fix for duplicated columns across metrics: if major metrics are identical
                # treat the series as revenue and set others to zero for proper downstream derivations
                def to_tuple(x):
                    if isinstance(x, list):
                        return tuple(x)
                    return (x,)
                major_keys = [
                    'total_revenue', 'cost_of_revenue', 'gross_profit',
                    'total_operating_expenses', 'operating_income', 'net_income'
                ]
                values = [to_tuple(standardized_metrics.get(k, 0)) for k in major_keys]
                non_empty = [v for v in values if any(v)]
                all_equal = len(non_empty) > 1 and all(v == non_empty[0] for v in non_empty)
                if all_equal:
                    base = non_empty[0]
                    base_len = len(base)
                    standardized_metrics['total_revenue'] = list(base)
                    standardized_metrics['cost_of_revenue'] = [0.0] * base_len
                    standardized_metrics['total_operating_expenses'] = [0.0] * base_len
                    standardized_metrics['gross_profit'] = [0.0] * base_len
                    standardized_metrics['operating_income'] = [0.0] * base_len
                    standardized_metrics['net_income'] = [0.0] * base_len

                processed_data['metrics'][sheet_name] = standardized_metrics

                # Create records
                records = self._create_financial_records(standardized_metrics)
                processed_data['records'].extend(records)
        
        # Validate data quality
        validation_results = self._validate_extracted_data(processed_data)
        processed_data['validation_results'] = validation_results
        processed_data['data_quality_score'] = validation_results.get('overall_score', 0.0)
        
        return processed_data

    def _standardize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize extracted metrics to a consistent format while preserving row alignment.

        - Lists/Series are converted to lists of floats (order preserved, NaNs removed)
        - Scalars are converted to floats
        """
        standardized: Dict[str, Any] = {}
        for metric, values in metrics.items():
            if isinstance(values, pd.Series):
                values = values.tolist()
            if isinstance(values, list):
                clean_list: list[float] = []
                for v in values:
                    if pd.isna(v):
                        continue
                    try:
                        clean_list.append(float(v))
                    except Exception:
                        # Skip non-numeric entries in numeric metrics
                        continue
                standardized[metric] = clean_list
            else:
                try:
                    standardized[metric] = float(values) if pd.notna(values) else 0.0
                except Exception:
                    standardized[metric] = 0.0
        return standardized

    def _create_financial_records(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create financial records from extracted metrics, preserving all rows.

        If metrics contain lists, we align by index to emit one record per row.
        If only scalars are present, we emit a single record.
        """
        # Determine row count from longest list among known metrics
        list_lengths: List[int] = []
        known_keys = [
            'total_revenue', 'cost_of_revenue', 'gross_profit',
            'total_operating_expenses', 'operating_income', 'net_income',
            'research_development', 'total_assets', 'total_liabilities',
            'shareholders_equity'
        ]
        for key in known_keys:
            val = metrics.get(key)
            if isinstance(val, list):
                list_lengths.append(len(val))
        row_count = max(list_lengths) if list_lengths else 1

        # Optional date series detection
        date_keys = ['date', 'period_date', 'end_date', 'report_date']
        date_series: List[Any] | None = None
        for dk in date_keys:
            dv = metrics.get(dk)
            if isinstance(dv, list) and len(dv) == row_count:
                date_series = dv
                break

        records: List[Dict[str, Any]] = []
        for i in range(row_count):
            def pick(key: str) -> float:
                v = metrics.get(key, 0.0)
                if isinstance(v, list):
                    try:
                        return float(v[i]) if i < len(v) and pd.notna(v[i]) else 0.0
                    except Exception:
                        return 0.0
                try:
                    return float(v) if pd.notna(v) else 0.0
                except Exception:
                    return 0.0

            period = None
            if date_series is not None:
                try:
                    period = pd.to_datetime(date_series[i], errors='coerce').date() if i < len(date_series) else None
                except Exception:
                    period = None

            record = {
                'period_date': period or datetime.now().date(),
                'total_revenue': pick('total_revenue'),
                'cost_of_revenue': pick('cost_of_revenue'),
                'gross_profit': pick('gross_profit'),
                'total_operating_expenses': pick('total_operating_expenses'),
                'operating_income': pick('operating_income'),
                'net_income': pick('net_income'),
                'research_development': pick('research_development'),
                'total_assets': pick('total_assets'),
                'total_liabilities': pick('total_liabilities'),
                'shareholders_equity': pick('shareholders_equity')
            }

            records.append(record)

        # Debug logging: Show summary of records created
        try:
            print("🔍 DEBUG: IntelligentDataExtractor - _create_financial_records count", len(records))
        except Exception:
            pass

        return records

    def _validate_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the quality and completeness of extracted data"""
        validation = {
            'completeness_score': 0.0,
            'accuracy_score': 0.0,
            'consistency_score': 0.0,
            'overall_score': 0.0,
            'issues': [],
            'recommendations': []
        }
        
        if not data.get('records'):
            validation['issues'].append('No financial records extracted')
            return validation
        
        # Check completeness
        required_fields = ['total_revenue', 'net_income', 'operating_income']
        complete_records = 0
        total_records = len(data['records'])
        
        for record in data['records']:
            if all(record.get(field, 0) != 0 for field in required_fields):
                complete_records += 1
        
        validation['completeness_score'] = complete_records / total_records if total_records > 0 else 0
        
        # Check accuracy (basic sanity checks)
        accuracy_issues = 0
        for record in data['records']:
            # Revenue should be positive
            if record.get('total_revenue', 0) < 0:
                accuracy_issues += 1
            
            # Basic accounting equation check
            assets = record.get('total_assets', 0)
            liabilities = record.get('total_liabilities', 0)
            equity = record.get('shareholders_equity', 0)
            
            if assets > 0 and abs(assets - (liabilities + equity)) > assets * 0.1:  # 10% tolerance
                accuracy_issues += 1
        
        validation['accuracy_score'] = max(0, 1 - (accuracy_issues / total_records)) if total_records > 0 else 0
        
        # Overall score
        validation['overall_score'] = (validation['completeness_score'] + validation['accuracy_score']) / 2
        
        # Generate recommendations
        if validation['completeness_score'] < 0.8:
            validation['recommendations'].append('Upload more complete financial statements')
        
        if validation['accuracy_score'] < 0.8:
            validation['recommendations'].append('Verify data accuracy and formatting')
        
        return validation

    # Helper methods
    def _has_numeric_data(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame has numeric data"""
        return any(df[col].dtype in ['int64', 'float64'] for col in df.columns)

    def _has_date_columns(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame has date columns"""
        return any('date' in str(col).lower() for col in df.columns)

    def _detect_financial_indicators(self, df: pd.DataFrame) -> List[str]:
        """Detect financial indicators in the DataFrame"""
        indicators = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(indicator in col_lower for indicator in ['revenue', 'income', 'profit', 'expense', 'asset', 'liability']):
                indicators.append(col)
        return indicators

    def _calculate_structure_confidence(self, sheet_analysis: Dict[str, Any]) -> float:
        """Calculate confidence based on structure analysis"""
        confidence = 0.0
        
        if sheet_analysis['has_numeric_data']:
            confidence += 0.3
        
        if sheet_analysis['has_date_columns']:
            confidence += 0.2
        
        if sheet_analysis['financial_indicators']:
            confidence += 0.3
        
        if sheet_analysis['rows'] > 10:
            confidence += 0.2
        
        return min(confidence, 1.0)

    def _is_financial_column(self, col_data: pd.Series) -> bool:
        """Check if a column contains financial data"""
        if not self._is_numeric_financial_data(col_data):
            return False
        
        # Check for financial value ranges
        numeric_values = pd.to_numeric(col_data, errors='coerce').dropna()
        if len(numeric_values) == 0:
            return False
        
        # Financial data typically has values in certain ranges
        max_val = numeric_values.max()
        min_val = numeric_values.min()
        
        # Check if values are in typical financial ranges
        return max_val > 0 and (max_val > 1000 or min_val < -1000)

    def _is_numeric_financial_data(self, col_data: pd.Series) -> bool:
        """Check if column data is numeric and looks like financial data"""
        # Try to convert to numeric
        numeric_values = pd.to_numeric(col_data, errors='coerce').dropna()
        return len(numeric_values) > len(col_data) * 0.5  # At least 50% numeric

    def _has_financial_value_range(self, col_data: pd.Series, metric: str) -> bool:
        """Check if column has values in typical financial ranges for the metric"""
        numeric_values = pd.to_numeric(col_data, errors='coerce').dropna()
        if len(numeric_values) == 0:
            return False
        
        # Define typical ranges for different metrics
        ranges = {
            'total_revenue': (1000, float('inf')),
            'net_income': (-float('inf'), float('inf')),
            'operating_income': (-float('inf'), float('inf')),
            'total_assets': (1000, float('inf')),
            'total_liabilities': (0, float('inf'))
        }
        
        if metric in ranges:
            min_range, max_range = ranges[metric]
            return all(min_range <= val <= max_range for val in numeric_values.head(10))
        
        return True

    def _has_financial_context_clues(self, col_data: pd.Series) -> bool:
        """Check if column has financial context clues"""
        # Look for currency symbols, parentheses (negative numbers), etc.
        sample_values = col_data.dropna().head(10).astype(str)
        
        financial_clues = [
            '$', '€', '£', '¥', '₹',  # Currency symbols
            '(', ')',  # Parentheses for negative numbers
            ',',  # Thousands separators
            'K', 'M', 'B',  # Abbreviations
        ]
        
        return any(any(clue in str(val) for clue in financial_clues) for val in sample_values)

    def _calculate_context_confidence(self, col_data: pd.Series, patterns: List[str]) -> float:
        """Calculate confidence based on context analysis"""
        confidence = 0.0
        
        # Check data type
        if self._is_numeric_financial_data(col_data):
            confidence += 0.4
        
        # Check value ranges
        if self._has_financial_value_range(col_data, 'unknown'):
            confidence += 0.3
        
        # Check context clues
        if self._has_financial_context_clues(col_data):
            confidence += 0.3
        
        return min(confidence, 1.0)

    def _extract_metric_values(self, df: pd.DataFrame, column: str) -> List[float]:
        """Extract values from a specific column"""
        try:
            values = pd.to_numeric(df[column], errors='coerce').dropna().tolist()
            return [float(v) for v in values if pd.notna(v)]
        except:
            return []

    def _extract_values_by_pattern(self, df: pd.DataFrame, pattern_match: Dict[str, Any]) -> List[float]:
        """Extract values using pattern matching"""
        column = pattern_match['column']
        return self._extract_metric_values(df, column)

    def _extract_by_context(self, df: pd.DataFrame, context_info: Dict[str, Any]) -> List[float]:
        """Extract values using context information"""
        column = context_info['column']
        return self._extract_metric_values(df, column)

    def _extract_values_by_prediction(self, df: pd.DataFrame, prediction: Dict[str, Any]) -> List[float]:
        """Extract values using ML prediction"""
        column = prediction['column']
        return self._extract_metric_values(df, column)

    def _generate_comprehensive_report(self, analysis_result, upload_record):
        """
        Generate comprehensive financial report with proper error handling
        """
        try:


            # ✅ FIX: Validate analysis_result before report generation
            if not analysis_result or not isinstance(analysis_result, dict):
                logger.warning("Invalid analysis result for report generation")
                return {
                    'success': False,
                    'error': 'Invalid analysis result'
                }

            # Get the analysis request object
            analysis_id = analysis_result.get('analysis_id')
            if not analysis_id:
                logger.warning("No analysis_id in result")
                return {
                    'success': False,
                    'error': 'No analysis ID available'
                }

            try:
                analysis_request = TazamaAnalysisRequest.objects.get(id=analysis_id)
            except TazamaAnalysisRequest.DoesNotExist:
                logger.error(f"Analysis request {analysis_id} not found")
                return {
                    'success': False,
                    'error': 'Analysis request not found'
                }

            # Generate report using the generator
            report_generator = TazamaReportGenerator()

            # ✅ FIX: Use correct FinancialReport fields (no 'content' field)
            report_path, content_type = report_generator.generate_report(
                analysis_request,
                format='html'  # or 'pdf', 'json', 'excel'
            )

            # Create FinancialReport record with correct fields
            date_str = analysis_request.created_at.strftime('%Y-%m-%d')

            # ✅ FIX: Remove 'content' field and use correct field names
            financial_report = FinancialReport.objects.create(
                analysis_request=analysis_request,
                corporate=analysis_request.corporate,
                report_type='comprehensive_analysis',
                title=f"Financial Analysis Report - {date_str}"[:90],  # Truncate to field limit
                executive_summary=f"AI-powered financial analysis"[:255],  # Truncate to field limit
                detailed_analysis=analysis_request.predictions or {},
                recommendations=analysis_request.recommendations or {},
                report_format='html',
                report_file=report_path
            )

            return {
                'success': True,
                'report_id': financial_report.id,
                'report_path': report_path,
                'report_type': content_type
            }

        except Exception as e:
            logger.error(f"Error generating comprehensive report: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }

    def _run_intelligent_analysis(self, processed_data, upload_record):
        """
        Run intelligent AI analysis with proper input validation
        """
        try:
            # ✅ FIX: Validate processed_data before analysis
            if not processed_data or not isinstance(processed_data, list):
                logger.warning("Empty or invalid processed_data for analysis")
                return {
                    'success': False,
                    'error': 'No valid data to analyze'
                }

            if len(processed_data) == 0:
                logger.warning("Empty processed_data list")
                return {
                    'success': False,
                    'error': 'No financial records to analyze'
                }

            # Get the latest processed record
            latest_record = processed_data[0]

            # ✅ FIX: Build proper input_data with ALL required features
            input_data = {
                'totalRevenue': float(latest_record.total_revenue or 0),
                'costOfRevenue': float(latest_record.cost_of_revenue or 0),
                'grossProfit': float(latest_record.gross_profit or 0),
                'totalOperatingExpenses': float(latest_record.total_operating_expenses or 0),
                'operatingIncome': float(latest_record.operating_income or 0),
                'netIncome': float(latest_record.net_income or 0),
                'researchDevelopment': float(latest_record.research_development or 0),
            }

            # ✅ CRITICAL: Calculate ALL derived features that model expects
            total_revenue = input_data['totalRevenue']
            cost_of_revenue = input_data['costOfRevenue']
            gross_profit = input_data['grossProfit']
            total_expenses = input_data['totalOperatingExpenses']
            operating_income = input_data['operatingIncome']
            net_income = input_data['netIncome']
            rd_expenses = input_data['researchDevelopment']

            # Calculate ratios and margins
            if total_revenue > 0:
                input_data['profit_margin'] = net_income / total_revenue
                input_data['operating_margin'] = operating_income / total_revenue
                input_data['cost_revenue_ratio'] = cost_of_revenue / total_revenue
                input_data['expense_ratio'] = total_expenses / total_revenue
                input_data['gross_margin'] = gross_profit / total_revenue
                input_data['rd_intensity'] = rd_expenses / total_revenue
                input_data['revenue_per_expense'] = total_revenue / max(total_expenses, 1)
            else:
                input_data['profit_margin'] = 0
                input_data['operating_margin'] = 0
                input_data['cost_revenue_ratio'] = 0
                input_data['expense_ratio'] = 0
                input_data['gross_margin'] = 0
                input_data['rd_intensity'] = 0
                input_data['revenue_per_expense'] = 0

            # Clip values to reasonable ranges (same as training)
            input_data['profit_margin'] = np.clip(input_data['profit_margin'], -1, 1)
            input_data['gross_margin'] = np.clip(input_data['gross_margin'], -1, 1)
            input_data['operating_margin'] = np.clip(input_data['operating_margin'], -1, 1)
            input_data['cost_revenue_ratio'] = np.clip(input_data['cost_revenue_ratio'], 0, 2)
            input_data['expense_ratio'] = np.clip(input_data['expense_ratio'], 0, 2)
            input_data['rd_intensity'] = np.clip(input_data['rd_intensity'], 0, 1)
            input_data['revenue_per_expense'] = np.clip(input_data['revenue_per_expense'], 0, 10)

            # ✅ Validate input_data is not empty
            if not any(v != 0 for v in input_data.values()):
                logger.warning("All input values are zero")
                return {
                    'success': False,
                    'error': 'All financial values are zero - cannot perform analysis'
                }

            logger.info(f"Running analysis with input_data: {input_data}")

            # Create analysis request
            analysis_service = TazamaAnalysisService()

            request_obj = analysis_service.create_analysis_request(
                corporate=upload_record.corporate,
                user=upload_record.uploaded_by,
                input_data=input_data,
                request_type='automated_upload_analysis'
            )

            # Execute analysis
            success, message = analysis_service.run_analysis(request_obj.id)

            if success:
                request_obj.refresh_from_db()
                return {
                    'success': True,
                    'analysis_id': request_obj.id,
                    'predictions': request_obj.predictions,
                    'recommendations': request_obj.recommendations,
                    'risk_assessment': request_obj.risk_assessment,
                    'confidence_scores': request_obj.confidence_scores,
                    'processing_time': request_obj.processing_time_seconds
                }
            else:
                return {
                    'success': False,
                    'error': message
                }

        except Exception as e:
            logger.error(f"Error in intelligent analysis: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }