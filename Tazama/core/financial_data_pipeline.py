# financial_data_pipeline.py - Comprehensive Financial Document Processing Pipeline
"""
Advanced financial document processing pipeline for Tazama
Handles CSV, XLS, XLSX, ODS, TSV files with intelligent table detection
and time series preparation for AI model training
"""

import pandas as pd
import numpy as np
import logging
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union, Any
from pathlib import Path
import warnings
from dateutil import parser as date_parser
from fuzzywuzzy import fuzz, process
import chardet
import io

# Excel and other format support
try:
    import openpyxl
    from openpyxl.utils import get_column_letter
except ImportError:
    openpyxl = None

try:
    import xlrd
except ImportError:
    xlrd = None

try:
    import odfpy
except ImportError:
    odfpy = None

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class FinancialDocumentProcessor:
    """Comprehensive financial document processing pipeline"""
    
    def __init__(self):
        self.supported_formats = ['.csv', '.xls', '.xlsx', '.ods', '.tsv']
        self.financial_keywords = {
            'income_statement': [
                'revenue', 'sales', 'income', 'profit', 'loss', 'earnings',
                'total revenue', 'net income', 'gross profit', 'operating income',
                'ebitda', 'ebit', 'net sales', 'service revenue'
            ],
            'balance_sheet': [
                'assets', 'liabilities', 'equity', 'cash', 'inventory',
                'total assets', 'current assets', 'fixed assets', 'total liabilities',
                'shareholders equity', 'retained earnings', 'working capital'
            ],
            'cash_flow': [
                'cash flow', 'operating cash', 'investing cash', 'financing cash',
                'net cash', 'cash from operations', 'free cash flow',
                'cash and cash equivalents', 'cash at beginning', 'cash at end'
            ],
            'profit_loss': [
                'profit', 'loss', 'p&l', 'profit and loss', 'income statement',
                'revenue', 'expenses', 'cost of goods', 'operating expenses'
            ]
        }
        
        self.date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
            r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
            r'\d{1,2}/\d{1,2}/\d{4}',  # M/D/YYYY
            r'\d{4}\.\d{2}\.\d{2}',  # YYYY.MM.DD
        ]
    
    def process_financial_document(self, file_path: str, file_content: bytes = None) -> Dict[str, Any]:
        """
        Main entry point for processing financial documents
        
        Args:
            file_path: Path to the financial document
            file_content: Optional file content as bytes (for web uploads)
            
        Returns:
            Dictionary containing processed data and metadata
        """
        try:
            logger.info(f"Processing financial document: {file_path}")
            
            # Step 1: Detect file type and load content
            file_info = self._detect_file_type(file_path, file_content)
            
            # Step 2: Load and parse the document
            raw_data = self._load_document(file_path, file_content, file_info)
            
            # Step 3: Detect and extract financial tables
            financial_tables = self._detect_financial_tables(raw_data)
            
            # Step 4: Clean and normalize data
            cleaned_tables = self._clean_financial_data(financial_tables)
            
            # Step 5: Prepare time series data
            time_series_data = self._prepare_time_series_data(cleaned_tables)
            
            # Step 6: Generate metadata and statistics
            metadata = self._generate_metadata(time_series_data, file_info)
            
            return {
                'success': True,
                'file_info': file_info,
                'financial_tables': financial_tables,
                'cleaned_tables': cleaned_tables,
                'time_series_data': time_series_data,
                'metadata': metadata,
                'processing_log': self._get_processing_log()
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'file_info': getattr(self, '_file_info', {}),
                'processing_log': self._get_processing_log()
            }
    
    def _detect_file_type(self, file_path: str, file_content: bytes = None) -> Dict[str, Any]:
        """Detect file type and encoding"""
        file_info = {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'file_extension': Path(file_path).suffix.lower(),
            'file_size': 0,
            'encoding': 'utf-8',
            'is_valid': False
        }
        
        try:
            # Check if file exists or content is provided
            if file_content:
                file_info['file_size'] = len(file_content)
                content = file_content
            else:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"File not found: {file_path}")
                
                file_info['file_size'] = os.path.getsize(file_path)
                with open(file_path, 'rb') as f:
                    content = f.read()
            
            # Detect encoding for text files
            if file_info['file_extension'] in ['.csv', '.tsv']:
                detected = chardet.detect(content)
                file_info['encoding'] = detected.get('encoding', 'utf-8')
            
            # Validate file format
            if file_info['file_extension'] not in self.supported_formats:
                raise ValueError(f"Unsupported file format: {file_info['file_extension']}")
            
            file_info['is_valid'] = True
            self._file_info = file_info
            
        except Exception as e:
            logger.error(f"File detection error: {str(e)}")
            file_info['error'] = str(e)
        
        return file_info
    
    def _load_document(self, file_path: str, file_content: bytes, file_info: Dict) -> Dict[str, pd.DataFrame]:
        """Load document content into DataFrames"""
        raw_data = {}
        
        try:
            file_extension = file_info['file_extension']
            
            if file_extension == '.csv':
                raw_data = self._load_csv(file_path, file_content, file_info)
            elif file_extension == '.tsv':
                raw_data = self._load_tsv(file_path, file_content, file_info)
            elif file_extension == '.xlsx':
                raw_data = self._load_excel(file_path, file_content, file_info)
            elif file_extension == '.xls':
                raw_data = self._load_excel_legacy(file_path, file_content, file_info)
            elif file_extension == '.ods':
                raw_data = self._load_ods(file_path, file_content, file_info)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            logger.info(f"Successfully loaded {len(raw_data)} sheets/tables")
            
        except Exception as e:
            logger.error(f"Document loading error: {str(e)}")
            raise
        
        return raw_data
    
    def _load_csv(self, file_path: str, file_content: bytes, file_info: Dict) -> Dict[str, pd.DataFrame]:
        """Load CSV file"""
        try:
            if file_content:
                df = pd.read_csv(io.BytesIO(file_content), encoding=file_info['encoding'])
            else:
                df = pd.read_csv(file_path, encoding=file_info['encoding'])
            
            return {'main': df}
        except Exception as e:
            logger.error(f"CSV loading error: {str(e)}")
            raise
    
    def _load_tsv(self, file_path: str, file_content: bytes, file_info: Dict) -> Dict[str, pd.DataFrame]:
        """Load TSV file"""
        try:
            if file_content:
                df = pd.read_csv(io.BytesIO(file_content), sep='\t', encoding=file_info['encoding'])
            else:
                df = pd.read_csv(file_path, sep='\t', encoding=file_info['encoding'])
            
            return {'main': df}
        except Exception as e:
            logger.error(f"TSV loading error: {str(e)}")
            raise
    
    def _load_excel(self, file_path: str, file_content: bytes, file_info: Dict) -> Dict[str, pd.DataFrame]:
        """Load Excel file (XLSX)"""
        try:
            if file_content:
                excel_file = io.BytesIO(file_content)
            else:
                excel_file = file_path
            
            # Read all sheets
            excel_data = pd.read_excel(excel_file, sheet_name=None, engine='openpyxl')
            
            # Convert to our format
            sheets = {}
            for sheet_name, df in excel_data.items():
                if not df.empty:
                    sheets[sheet_name] = df
            
            return sheets if sheets else {'main': pd.DataFrame()}
            
        except Exception as e:
            logger.error(f"Excel loading error: {str(e)}")
            raise
    
    def _load_excel_legacy(self, file_path: str, file_content: bytes, file_info: Dict) -> Dict[str, pd.DataFrame]:
        """Load legacy Excel file (XLS)"""
        try:
            if file_content:
                excel_file = io.BytesIO(file_content)
            else:
                excel_file = file_path
            
            # Read all sheets
            excel_data = pd.read_excel(excel_file, sheet_name=None, engine='xlrd')
            
            # Convert to our format
            sheets = {}
            for sheet_name, df in excel_data.items():
                if not df.empty:
                    sheets[sheet_name] = df
            
            return sheets if sheets else {'main': pd.DataFrame()}
            
        except Exception as e:
            logger.error(f"Legacy Excel loading error: {str(e)}")
            raise
    
    def _load_ods(self, file_path: str, file_content: bytes, file_info: Dict) -> Dict[str, pd.DataFrame]:
        """Load ODS file"""
        try:
            if file_content:
                ods_file = io.BytesIO(file_content)
            else:
                ods_file = file_path
            
            # Read all sheets
            ods_data = pd.read_excel(ods_file, sheet_name=None, engine='odf')
            
            # Convert to our format
            sheets = {}
            for sheet_name, df in ods_data.items():
                if not df.empty:
                    sheets[sheet_name] = df
            
            return sheets if sheets else {'main': pd.DataFrame()}
            
        except Exception as e:
            logger.error(f"ODS loading error: {str(e)}")
            raise
    
    def _detect_financial_tables(self, raw_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, Any]]:
        """Detect and classify financial tables"""
        financial_tables = {}
        
        for sheet_name, df in raw_data.items():
            if df.empty:
                continue
            
            # Analyze the sheet for financial content
            analysis = self._analyze_sheet_content(df, sheet_name)
            
            if analysis['is_financial']:
                financial_tables[sheet_name] = {
                    'data': df,
                    'type': analysis['financial_type'],
                    'confidence': analysis['confidence'],
                    'date_columns': analysis['date_columns'],
                    'numeric_columns': analysis['numeric_columns'],
                    'key_metrics': analysis['key_metrics']
                }
        
        return financial_tables
    
    def _analyze_sheet_content(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """Analyze sheet content to determine if it's financial data"""
        analysis = {
            'is_financial': False,
            'financial_type': 'unknown',
            'confidence': 0.0,
            'date_columns': [],
            'numeric_columns': [],
            'key_metrics': []
        }
        
        try:
            # Get all column names as strings
            columns = [str(col).lower().strip() for col in df.columns]
            
            # Check for financial keywords in column names
            financial_scores = {}
            for financial_type, keywords in self.financial_keywords.items():
                score = 0
                for keyword in keywords:
                    for col in columns:
                        if fuzz.partial_ratio(keyword.lower(), col) > 70:
                            score += 1
                
                financial_scores[financial_type] = score
            
            # Determine the best match
            if financial_scores:
                best_type = max(financial_scores, key=financial_scores.get)
                best_score = financial_scores[best_type]
                
                if best_score > 0:
                    analysis['is_financial'] = True
                    analysis['financial_type'] = best_type
                    analysis['confidence'] = min(best_score / 10.0, 1.0)
            
            # Detect date columns
            analysis['date_columns'] = self._detect_date_columns(df)
            
            # Detect numeric columns
            analysis['numeric_columns'] = self._detect_numeric_columns(df)
            
            # Extract key metrics
            analysis['key_metrics'] = self._extract_key_metrics(df, columns)
            
        except Exception as e:
            logger.error(f"Sheet analysis error: {str(e)}")
        
        return analysis
    
    def _detect_date_columns(self, df: pd.DataFrame) -> List[str]:
        """Detect columns that contain dates"""
        date_columns = []
        
        for col in df.columns:
            try:
                # Check if column name suggests it's a date
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['date', 'time', 'period', 'year', 'month', 'quarter']):
                    date_columns.append(col)
                    continue
                
                # Check if column values look like dates
                sample_values = df[col].dropna().head(10)
                if len(sample_values) > 0:
                    date_count = 0
                    for value in sample_values:
                        if self._is_date_like(value):
                            date_count += 1
                    
                    if date_count / len(sample_values) > 0.5:
                        date_columns.append(col)
            
            except Exception:
                continue
        
        return date_columns
    
    def _is_date_like(self, value: Any) -> bool:
        """Check if a value looks like a date"""
        try:
            if pd.isna(value):
                return False
            
            value_str = str(value)
            
            # Check for date patterns
            for pattern in self.date_patterns:
                if re.search(pattern, value_str):
                    return True
            
            # Try to parse as date
            date_parser.parse(value_str, fuzzy=True)
            return True
            
        except:
            return False
    
    def _detect_numeric_columns(self, df: pd.DataFrame) -> List[str]:
        """Detect columns that contain numeric data"""
        numeric_columns = []
        
        for col in df.columns:
            try:
                # Check if column is already numeric
                if pd.api.types.is_numeric_dtype(df[col]):
                    numeric_columns.append(col)
                    continue
                
                # Check if column contains numeric-like data
                sample_values = df[col].dropna().head(20)
                if len(sample_values) > 0:
                    numeric_count = 0
                    for value in sample_values:
                        if self._is_numeric_like(value):
                            numeric_count += 1
                    
                    if numeric_count / len(sample_values) > 0.7:
                        numeric_columns.append(col)
            
            except Exception:
                continue
        
        return numeric_columns
    
    def _is_numeric_like(self, value: Any) -> bool:
        """Check if a value looks like a number"""
        try:
            if pd.isna(value):
                return False
            
            value_str = str(value).strip()
            
            # Remove common currency symbols and formatting
            value_str = re.sub(r'[$,\s]', '', value_str)
            value_str = re.sub(r'[()]', '-', value_str)  # Handle negative numbers in parentheses
            value_str = re.sub(r'%', '', value_str)
            
            # Try to convert to float
            float(value_str)
            return True
            
        except:
            return False
    
    def _extract_key_metrics(self, df: pd.DataFrame, columns: List[str]) -> List[str]:
        """Extract key financial metrics from the data"""
        key_metrics = []
        
        # Look for common financial metrics
        metric_keywords = [
            'revenue', 'sales', 'income', 'profit', 'loss', 'assets', 'liabilities',
            'equity', 'cash', 'ebitda', 'ebit', 'gross', 'operating', 'net'
        ]
        
        for col in columns:
            for keyword in metric_keywords:
                if keyword in col:
                    key_metrics.append(col)
                    break
        
        return key_metrics
    
    def _clean_financial_data(self, financial_tables: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Clean and normalize financial data"""
        cleaned_tables = {}
        
        for sheet_name, table_info in financial_tables.items():
            try:
                df = table_info['data'].copy()
                
                # Clean column names
                df.columns = self._clean_column_names(df.columns)
                
                # Clean numeric data
                df = self._clean_numeric_data(df, table_info['numeric_columns'])
                
                # Clean date data
                df = self._clean_date_data(df, table_info['date_columns'])
                
                # Remove completely empty rows and columns
                df = df.dropna(how='all').dropna(axis=1, how='all')
                
                # Update table info
                cleaned_info = table_info.copy()
                cleaned_info['data'] = df
                cleaned_info['cleaned_columns'] = list(df.columns)
                cleaned_info['shape'] = df.shape
                
                cleaned_tables[sheet_name] = cleaned_info
                
            except Exception as e:
                logger.error(f"Error cleaning table {sheet_name}: {str(e)}")
                continue
        
        return cleaned_tables
    
    def _clean_column_names(self, columns: List[str]) -> List[str]:
        """Clean and normalize column names"""
        cleaned_columns = []
        
        for col in columns:
            # Convert to string and clean
            col_str = str(col).strip()
            
            # Remove extra whitespace
            col_str = re.sub(r'\s+', ' ', col_str)
            
            # Convert to snake_case
            col_str = re.sub(r'[^a-zA-Z0-9\s]', '', col_str)
            col_str = re.sub(r'\s+', '_', col_str)
            col_str = col_str.lower()
            
            # Handle empty or duplicate names
            if not col_str or col_str in cleaned_columns:
                col_str = f"column_{len(cleaned_columns)}"
            
            cleaned_columns.append(col_str)
        
        return cleaned_columns
    
    def _clean_numeric_data(self, df: pd.DataFrame, numeric_columns: List[str]) -> pd.DataFrame:
        """Clean numeric data in specified columns"""
        for col in numeric_columns:
            if col in df.columns:
                try:
                    # Convert to string first
                    df[col] = df[col].astype(str)
                    
                    # Remove currency symbols, commas, and other formatting
                    df[col] = df[col].str.replace(r'[$,\s]', '', regex=True)
                    df[col] = df[col].str.replace(r'[()]', '-', regex=True)  # Handle negative numbers
                    df[col] = df[col].str.replace(r'%', '', regex=True)
                    
                    # Convert to numeric, errors will become NaN
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                except Exception as e:
                    logger.warning(f"Error cleaning numeric column {col}: {str(e)}")
        
        return df
    
    def _clean_date_data(self, df: pd.DataFrame, date_columns: List[str]) -> pd.DataFrame:
        """Clean date data in specified columns"""
        for col in date_columns:
            if col in df.columns:
                try:
                    # Convert to datetime
                    df[col] = pd.to_datetime(df[col], errors='coerce', infer_datetime_format=True)
                    
                except Exception as e:
                    logger.warning(f"Error cleaning date column {col}: {str(e)}")
        
        return df
    
    def _prepare_time_series_data(self, cleaned_tables: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Prepare data for time series analysis"""
        time_series_data = {}
        
        for sheet_name, table_info in cleaned_tables.items():
            try:
                df = table_info['data'].copy()
                
                # Find the best date column
                date_column = self._find_best_date_column(df, table_info['date_columns'])
                
                if date_column:
                    # Set date as index
                    df = df.set_index(date_column)
                    df = df.sort_index()
                    
                    # Create time series features
                    df = self._create_time_series_features(df)
                    
                    # Interpolate missing values
                    df = self._interpolate_missing_values(df)
                    
                    # Create lag features
                    df = self._create_lag_features(df)
                    
                    # Create rolling averages
                    df = self._create_rolling_features(df)
                
                # Update table info
                ts_info = table_info.copy()
                ts_info['data'] = df
                ts_info['date_column'] = date_column
                ts_info['time_series_ready'] = date_column is not None
                
                time_series_data[sheet_name] = ts_info
                
            except Exception as e:
                logger.error(f"Error preparing time series for {sheet_name}: {str(e)}")
                continue
        
        return time_series_data
    
    def _find_best_date_column(self, df: pd.DataFrame, date_columns: List[str]) -> Optional[str]:
        """Find the best date column for time series analysis"""
        if not date_columns:
            return None
        
        best_column = None
        best_score = 0
        
        for col in date_columns:
            if col in df.columns:
                try:
                    # Check if column has valid dates
                    valid_dates = df[col].dropna()
                    if len(valid_dates) > 0:
                        # Score based on number of valid dates and uniqueness
                        unique_dates = valid_dates.nunique()
                        score = len(valid_dates) * unique_dates / len(df)
                        
                        if score > best_score:
                            best_score = score
                            best_column = col
                
                except Exception:
                    continue
        
        return best_column
    
    def _create_time_series_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create time series features"""
        try:
            # Add time-based features
            if isinstance(df.index, pd.DatetimeIndex):
                df['year'] = df.index.year
                df['month'] = df.index.month
                df['quarter'] = df.index.quarter
                df['day_of_year'] = df.index.dayofyear
                df['week_of_year'] = df.index.isocalendar().week
                
                # Add seasonal features
                df['is_quarter_end'] = df.index.is_quarter_end
                df['is_year_end'] = df.index.is_year_end
            
        except Exception as e:
            logger.warning(f"Error creating time series features: {str(e)}")
        
        return df
    
    def _interpolate_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Interpolate missing values in time series"""
        try:
            # For numeric columns, use linear interpolation
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                if df[col].isna().any():
                    df[col] = df[col].interpolate(method='linear')
            
        except Exception as e:
            logger.warning(f"Error interpolating missing values: {str(e)}")
        
        return df
    
    def _create_lag_features(self, df: pd.DataFrame, lags: List[int] = [1, 2, 3, 6, 12]) -> pd.DataFrame:
        """Create lag features for time series forecasting"""
        try:
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            
            for col in numeric_columns:
                for lag in lags:
                    lag_col = f"{col}_lag_{lag}"
                    df[lag_col] = df[col].shift(lag)
            
        except Exception as e:
            logger.warning(f"Error creating lag features: {str(e)}")
        
        return df
    
    def _create_rolling_features(self, df: pd.DataFrame, windows: List[int] = [3, 6, 12]) -> pd.DataFrame:
        """Create rolling average features"""
        try:
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            
            for col in numeric_columns:
                for window in windows:
                    rolling_col = f"{col}_rolling_{window}"
                    df[rolling_col] = df[col].rolling(window=window).mean()
            
        except Exception as e:
            logger.warning(f"Error creating rolling features: {str(e)}")
        
        return df
    
    def _generate_metadata(self, time_series_data: Dict[str, Dict[str, Any]], file_info: Dict) -> Dict[str, Any]:
        """Generate comprehensive metadata about the processed data"""
        metadata = {
            'file_info': file_info,
            'processing_timestamp': datetime.now().isoformat(),
            'total_sheets': len(time_series_data),
            'financial_tables': {},
            'summary_statistics': {},
            'data_quality': {},
            'recommendations': []
        }
        
        for sheet_name, table_info in time_series_data.items():
            df = table_info['data']
            
            # Basic info
            metadata['financial_tables'][sheet_name] = {
                'type': table_info['financial_type'],
                'confidence': table_info['confidence'],
                'shape': df.shape,
                'date_column': table_info.get('date_column'),
                'time_series_ready': table_info.get('time_series_ready', False),
                'columns': list(df.columns),
                'numeric_columns': list(df.select_dtypes(include=[np.number]).columns),
                'date_columns': list(df.select_dtypes(include=['datetime']).columns)
            }
            
            # Summary statistics
            if not df.empty:
                numeric_df = df.select_dtypes(include=[np.number])
                if not numeric_df.empty:
                    metadata['summary_statistics'][sheet_name] = {
                        'mean': numeric_df.mean().to_dict(),
                        'std': numeric_df.std().to_dict(),
                        'min': numeric_df.min().to_dict(),
                        'max': numeric_df.max().to_dict(),
                        'missing_values': df.isnull().sum().to_dict()
                    }
            
            # Data quality assessment
            metadata['data_quality'][sheet_name] = {
                'completeness': (1 - df.isnull().sum().sum() / (df.shape[0] * df.shape[1])),
                'duplicate_rows': df.duplicated().sum(),
                'empty_rows': df.isnull().all(axis=1).sum(),
                'empty_columns': df.isnull().all(axis=0).sum()
            }
        
        # Generate recommendations
        metadata['recommendations'] = self._generate_data_recommendations(metadata)
        
        return metadata
    
    def _generate_data_recommendations(self, metadata: Dict) -> List[str]:
        """Generate recommendations for data improvement"""
        recommendations = []
        
        for sheet_name, quality in metadata['data_quality'].items():
            if quality['completeness'] < 0.8:
                recommendations.append(f"Sheet '{sheet_name}' has low data completeness ({quality['completeness']:.1%}). Consider data cleaning.")
            
            if quality['duplicate_rows'] > 0:
                recommendations.append(f"Sheet '{sheet_name}' has {quality['duplicate_rows']} duplicate rows. Consider removing duplicates.")
            
            if quality['empty_rows'] > 0:
                recommendations.append(f"Sheet '{sheet_name}' has {quality['empty_rows']} empty rows. Consider removing them.")
        
        return recommendations
    
    def _get_processing_log(self) -> List[str]:
        """Get processing log"""
        return getattr(self, '_log', [])
    
    def _log(self, message: str):
        """Add message to processing log"""
        if not hasattr(self, '_log'):
            self._log = []
        self._log.append(f"{datetime.now().isoformat()}: {message}")


class FinancialDataPipeline:
    """Main pipeline class for financial data processing"""
    
    def __init__(self):
        self.processor = FinancialDocumentProcessor()
        self._log = []
    
    def process_file(self, file_path: str, file_content: bytes = None) -> Dict[str, Any]:
        """Process a financial file and return structured data"""
        try:
            self._log(f"Starting processing of file: {file_path}")
            
            # Process the document
            result = self.processor.process_financial_document(file_path, file_content)
            
            if result['success']:
                self._log("File processing completed successfully")
                
                # Prepare data for model training
                if result['time_series_data']:
                    result['model_ready_data'] = self._prepare_model_data(result['time_series_data'])
                
                return result
            else:
                self._log(f"File processing failed: {result.get('error', 'Unknown error')}")
                return result
                
        except Exception as e:
            self._log(f"Pipeline error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_log': self._log
            }
    
    def _prepare_model_data(self, time_series_data: Dict[str, Dict[str, Any]]) -> Dict[str, pd.DataFrame]:
        """Prepare data for model training"""
        model_data = {}
        
        for sheet_name, table_info in time_series_data.items():
            if table_info.get('time_series_ready', False):
                df = table_info['data'].copy()
                
                # Select only numeric columns for model training
                numeric_df = df.select_dtypes(include=[np.number])
                
                if not numeric_df.empty:
                    model_data[sheet_name] = numeric_df
        
        return model_data
    
    def train_model(self, dataframe: pd.DataFrame, model_type: str = 'lstm') -> Dict[str, Any]:
        """Placeholder function for model training"""
        try:
            self._log(f"Training {model_type} model with {dataframe.shape[0]} rows and {dataframe.shape[1]} features")
            
            # This is a placeholder - integrate with your actual model training
            # For now, return basic statistics
            return {
                'success': True,
                'model_type': model_type,
                'training_samples': len(dataframe),
                'features': len(dataframe.columns),
                'data_shape': dataframe.shape,
                'message': f"Model training placeholder - ready for {model_type} implementation"
            }
            
        except Exception as e:
            self._log(f"Model training error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def predict_future(self, dataframe: pd.DataFrame, periods: int = 12) -> Dict[str, Any]:
        """Placeholder function for future predictions"""
        try:
            self._log(f"Generating {periods} period predictions")
            
            # This is a placeholder - integrate with your actual prediction model
            # For now, return basic forecast structure
            forecast_data = {
                'periods': periods,
                'forecast_dates': pd.date_range(start=dataframe.index[-1], periods=periods+1, freq='M')[1:],
                'predictions': {},
                'confidence_intervals': {}
            }
            
            # Generate placeholder predictions for each numeric column
            for col in dataframe.select_dtypes(include=[np.number]).columns:
                last_value = dataframe[col].iloc[-1]
                forecast_data['predictions'][col] = [last_value * (1 + np.random.normal(0, 0.1)) for _ in range(periods)]
            
            return {
                'success': True,
                'forecast_data': forecast_data,
                'message': f"Prediction placeholder - ready for actual model implementation"
            }
            
        except Exception as e:
            self._log(f"Prediction error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_processing_log(self) -> List[str]:
        """Get the processing log"""
        return self._log


# Example usage and testing
if __name__ == "__main__":
    # Example usage
    pipeline = FinancialDataPipeline()
    
    # Process a file
    result = pipeline.process_file("example_financial_data.xlsx")
    
    if result['success']:
        print("✅ File processed successfully!")
        print(f"📊 Found {len(result['financial_tables'])} financial tables")
        
        for sheet_name, table_info in result['financial_tables'].items():
            print(f"  - {sheet_name}: {table_info['type']} (confidence: {table_info['confidence']:.2f})")
        
        # Train model if data is available
        if result.get('model_ready_data'):
            for sheet_name, df in result['model_ready_data'].items():
                print(f"\n🤖 Training model for {sheet_name}...")
                training_result = pipeline.train_model(df)
                print(f"Training result: {training_result}")
                
                # Generate predictions
                print(f"🔮 Generating predictions for {sheet_name}...")
                prediction_result = pipeline.predict_future(df, periods=12)
                print(f"Prediction result: {prediction_result}")
    else:
        print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
