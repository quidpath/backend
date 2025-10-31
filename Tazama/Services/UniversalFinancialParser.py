"""
Universal Financial Statement Parser and Predictor
==================================================
A comprehensive, production-ready parser that handles any financial statement format,
automatically detects periods, sections, and generates intelligent projections.

Author: Tazama AI Financial System
Version: 1.0.0
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import numpy as np
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UniversalFinancialParser:
    """
    Universal parser for financial statements that handles multiple formats,
    automatically detects sections, and generates intelligent projections.
    """
    
    # Section keywords for automatic classification
    SECTION_KEYWORDS = {
        'revenue': [
            'revenue', 'sales', 'income', 'turnover', 'receipts',
            'service revenue', 'sales revenue', 'product sales',
            'total revenue', 'gross revenue', 'operating revenue'
        ],
        'cost_of_revenue': [
            'cost of revenue', 'cogs', 'cost of goods sold', 'cost of sales',
            'direct costs', 'production costs', 'manufacturing costs'
        ],
        'expenses': [
            'expense', 'expenses', 'operating expense', 'opex',
            'salaries', 'wages', 'rent', 'utilities', 'marketing',
            'advertising', 'administrative', 'office', 'transport',
            'travel', 'supplies', 'depreciation', 'amortization',
            'interest expense', 'tax expense', 'legal', 'consulting',
            'subscription', 'insurance', 'maintenance', 'repairs'
        ],
        'gross_profit': [
            'gross profit', 'gross income', 'gross margin'
        ],
        'operating_income': [
            'operating income', 'ebit', 'operating profit',
            'earnings before interest and tax', 'operating earnings'
        ],
        'net_income': [
            'net income', 'net profit', 'net earnings', 'profit after tax',
            'profit before tax', 'bottom line', 'net profit after tax',
            'profit for the period', 'profit for the year'
        ],
        'assets': [
            'assets', 'total assets', 'current assets', 'fixed assets',
            'cash', 'accounts receivable', 'inventory', 'property',
            'equipment', 'intangible assets'
        ],
        'liabilities': [
            'liabilities', 'total liabilities', 'current liabilities',
            'long term liabilities', 'accounts payable', 'debt',
            'loans', 'bonds payable'
        ],
        'equity': [
            'equity', 'shareholders equity', 'stockholders equity',
            'retained earnings', 'capital', 'reserves'
        ],
        'cash_inflow': [
            'cash inflow', 'cash receipts', 'operating cash flow',
            'cash from operations', 'cash received'
        ],
        'cash_outflow': [
            'cash outflow', 'cash payments', 'cash paid',
            'cash used in operations'
        ]
    }
    
    # Date extraction patterns
    DATE_PATTERNS = [
        r'for\s+the\s+year\s+ended\s+(\d{1,2}\s+\w+\s+\d{4})',
        r'for\s+the\s+period\s+ended\s+(\d{1,2}\s+\w+\s+\d{4})',
        r'as\s+(?:at|of)\s+(\d{1,2}\s+\w+\s+\d{4})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\w+\s+\d{1,2},?\s+\d{4})',
        r'Q([1-4])\s+(\d{4})',
        r'(\d{4})-Q([1-4])',
        r'(\w+)\s+(\d{4})'
    ]
    
    # Growth assumptions (conservative defaults)
    DEFAULT_GROWTH_RATES = {
        'revenue': 0.08,  # 8%
        'net_income': 0.10,  # 10%
        'expenses': 0.05,  # 5%
        'assets': 0.07,  # 7%
    }
    
    def __init__(self):
        """Initialize the universal financial parser."""
        self.raw_data = None
        self.normalized_data = {}
        self.detected_period = None
        self.statement_type = None
        self.currency = 'KES'  # Default currency
        
    def parse_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Main entry point: Parse any financial statement file.
        
        Args:
            file_path: Path to the financial statement file
            
        Returns:
            Dict containing parsed data, metrics, and projections
        """
        logger.info(f"Starting parse of file: {file_path}")
        
        # Step 1: Load file
        self.raw_data = self._load_file(file_path)
        
        # Step 2: Extract metadata (date, currency)
        self._extract_metadata(file_path)
        
        # Step 3: Normalize and clean data
        self._normalize_data()
        
        # Step 4: Classify sections
        self._classify_sections()
        
        # Step 5: Calculate metrics
        metrics = self._calculate_metrics()
        
        # Step 6: Generate projections
        projections = self._generate_projections(metrics)
        
        # Step 7: Build final output
        output = self._build_output(metrics, projections)
        
        logger.info("Parsing completed successfully")
        return output
    
    def _load_file(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """
        Load file with automatic format detection.
        
        Supports: CSV, TSV, XLS, XLSX
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        try:
            if extension == '.csv':
                # Try different encodings and delimiters
                for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        if len(df.columns) == 1:
                            # Try different delimiter
                            df = pd.read_csv(file_path, encoding=encoding, delimiter=';')
                        if len(df.columns) > 1:
                            logger.info(f"Successfully loaded CSV with encoding: {encoding}")
                            return df
                    except Exception:
                        continue
                raise ValueError("Could not parse CSV with any standard encoding")
                
            elif extension == '.tsv':
                df = pd.read_csv(file_path, sep='\t', encoding='utf-8')
                return df
                
            elif extension in ['.xls', '.xlsx']:
                # Load first sheet by default
                df = pd.read_excel(file_path, sheet_name=0)
                logger.info(f"Successfully loaded Excel file")
                return df
                
            else:
                raise ValueError(f"Unsupported file format: {extension}")
                
        except Exception as e:
            logger.error(f"Error loading file: {str(e)}")
            raise
    
    def _extract_metadata(self, file_path: Union[str, Path]):
        """Extract date, period, and currency from file."""
        file_path = Path(file_path)
        
        # Try to extract date from filename
        date_from_filename = self._extract_date_from_text(file_path.stem)
        
        # Try to extract date from file content
        date_from_content = None
        if self.raw_data is not None:
            # Check first few rows for date information
            for col in self.raw_data.columns:
                for idx in range(min(10, len(self.raw_data))):
                    cell_value = str(self.raw_data.iloc[idx][col])
                    extracted_date = self._extract_date_from_text(cell_value)
                    if extracted_date:
                        date_from_content = extracted_date
                        break
                if date_from_content:
                    break
        
        # Use detected date or default to today
        self.detected_period = date_from_content or date_from_filename or {
            'end_date': datetime.now().date(),
            'period_type': 'unknown',
            'quarter': None,
            'year': datetime.now().year
        }
        
        # Extract currency
        self.currency = self._detect_currency()
        
        logger.info(f"Detected period: {self.detected_period}")
        logger.info(f"Detected currency: {self.currency}")
    
    def _extract_date_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract date information from text using multiple patterns."""
        if not text:
            return None
            
        text = text.lower().strip()
        
        # Try quarter pattern (Q1 2024, 2024-Q2, etc.)
        quarter_match = re.search(r'q([1-4])\s*(\d{4})|(\d{4})\s*-?\s*q([1-4])', text)
        if quarter_match:
            if quarter_match.group(1):
                quarter = int(quarter_match.group(1))
                year = int(quarter_match.group(2))
            else:
                quarter = int(quarter_match.group(4))
                year = int(quarter_match.group(3))
            
            # Calculate quarter end date
            month = quarter * 3
            if month == 12:
                end_date = datetime(year, 12, 31).date()
            else:
                end_date = datetime(year, month, 1).date() + relativedelta(months=1, days=-1)
            
            start_date = end_date - relativedelta(months=3, days=-1)
            
            return {
                'start_date': start_date,
                'end_date': end_date,
                'period_type': 'quarterly',
                'quarter': quarter,
                'year': year
            }
        
        # Try standard date patterns
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1) if '(' in pattern else match.group(0)
                    parsed_date = date_parser.parse(date_str, fuzzy=True)
                    
                    # Determine period type based on context
                    period_type = 'annual' if 'year' in text else 'unknown'
                    
                    return {
                        'start_date': (parsed_date - relativedelta(years=1)).date() if period_type == 'annual' else None,
                        'end_date': parsed_date.date(),
                        'period_type': period_type,
                        'quarter': None,
                        'year': parsed_date.year
                    }
                except Exception:
                    continue
        
        return None
    
    def _detect_currency(self) -> str:
        """Detect currency from file content."""
        if self.raw_data is None:
            return 'KES'
        
        currency_symbols = {
            'KES': ['kes', 'ksh', 'kenyan shilling'],
            'USD': ['usd', '$', 'dollar', 'us dollar'],
            'EUR': ['eur', '€', 'euro'],
            'GBP': ['gbp', '£', 'pound', 'sterling'],
        }
        
        # Check column names
        for col in self.raw_data.columns:
            col_lower = str(col).lower()
            for currency, patterns in currency_symbols.items():
                if any(pattern in col_lower for pattern in patterns):
                    return currency
        
        # Check first few rows
        for idx in range(min(5, len(self.raw_data))):
            for col in self.raw_data.columns:
                cell_value = str(self.raw_data.iloc[idx][col]).lower()
                for currency, patterns in currency_symbols.items():
                    if any(pattern in cell_value for pattern in patterns):
                        return currency
        
        return 'KES'  # Default
    
    def _normalize_data(self):
        """Clean and normalize all data."""
        if self.raw_data is None:
            return
        
        # Remove completely empty rows
        self.raw_data = self.raw_data.dropna(how='all')
        
        # Identify label and amount columns
        label_col, amount_col = self._identify_columns()
        
        if not label_col or not amount_col:
            logger.warning("Could not identify label/amount columns clearly")
            return
        
        # Normalize data
        normalized_rows = []
        for idx, row in self.raw_data.iterrows():
            label = str(row[label_col]).strip()
            amount_str = str(row[amount_col]).strip()
            
            # Skip if label is empty or invalid
            if not label or label.lower() in ['nan', 'none', '']:
                continue
            
            # Parse amount
            amount = self._parse_amount(amount_str)
            
            normalized_rows.append({
                'label': label,
                'amount': amount,
                'original_row': idx
            })
        
        self.normalized_data['rows'] = normalized_rows
        logger.info(f"Normalized {len(normalized_rows)} rows")
        
        # Debug: Show first few rows with non-zero amounts
        non_zero_rows = [r for r in normalized_rows if r['amount'] != 0]
        if non_zero_rows:
            logger.info(f"🔍 DEBUG: First 3 non-zero rows: {non_zero_rows[:3]}")
        else:
            logger.warning(f"⚠️ WARNING: No rows with non-zero amounts found!")
    
    def _identify_columns(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Identify which columns contain labels and amounts.
        
        Returns:
            Tuple of (label_column, amount_column)
        """
        if self.raw_data is None or len(self.raw_data.columns) == 0:
            return None, None
        
        # Keywords for label columns
        label_keywords = ['account', 'section', 'category', 'item', 'name', 
                          'particulars', 'description', 'line item']
        
        # Keywords for amount columns
        amount_keywords = ['amount', 'value', 'kes', 'ksh', 'total', 
                           'debit', 'credit', 'usd', 'balance']
        
        label_col = None
        amount_col = None
        
        # Check column names
        for col in self.raw_data.columns:
            col_lower = str(col).lower()
            
            if not label_col and any(kw in col_lower for kw in label_keywords):
                label_col = col
            
            if not amount_col and any(kw in col_lower for kw in amount_keywords):
                amount_col = col
        
        # Fallback: use heuristics
        if not label_col or not amount_col:
            # Score each column
            scores = {'text': {}, 'numeric': {}}
            
            for col in self.raw_data.columns:
                text_count = 0
                numeric_count = 0
                
                for idx in range(min(10, len(self.raw_data))):
                    val = str(self.raw_data.iloc[idx][col])
                    
                    # Check if looks like text
                    if len(val) > 3 and not val.replace('.', '').replace(',', '').replace('-', '').isdigit():
                        text_count += 1
                    
                    # Check if looks like number
                    if self._parse_amount(val) != 0:
                        numeric_count += 1
                
                scores['text'][col] = text_count
                scores['numeric'][col] = numeric_count
            
            # Choose best candidates ensuring they're different
            if not label_col:
                label_col = max(scores['text'], key=scores['text'].get, default=None)
            
            if not amount_col:
                # Get top numeric columns
                sorted_numeric = sorted(scores['numeric'].items(), key=lambda x: x[1], reverse=True)
                for col, score in sorted_numeric:
                    if col != label_col and score > 0:  # Ensure different from label_col
                        amount_col = col
                        break
                
                # If still not found, use first numeric column
                if not amount_col and sorted_numeric:
                    amount_col = sorted_numeric[0][0]
            
            # Final safety check: if they're the same, try to use different columns
            if label_col == amount_col and len(self.raw_data.columns) >= 2:
                # Use first column as label, second as amount by default
                all_cols = list(self.raw_data.columns)
                label_col = all_cols[0] if len(all_cols) > 0 else None
                amount_col = all_cols[1] if len(all_cols) > 1 else all_cols[0]
                logger.warning(f"Label and amount were same column, using positional fallback")
        
        logger.info(f"Identified columns - Label: {label_col}, Amount: {amount_col}")
        return label_col, amount_col
    
    def _parse_amount(self, amount_str: str) -> float:
        """
        Parse amount string to float.
        
        Handles:
        - Currency symbols (KES, $, €, etc.)
        - Thousands separators (1,000,000)
        - Abbreviations (1.2M, 500K)
        - Negative values
        """
        if not amount_str or str(amount_str).lower() in ['nan', 'none', '', '-']:
            return 0.0
        
        amount_str = str(amount_str).strip()
        
        # Remove currency symbols and common prefixes
        amount_str = re.sub(r'[A-Z]{3}', '', amount_str, flags=re.IGNORECASE)  # KES, USD, etc.
        amount_str = amount_str.replace('$', '').replace('€', '').replace('£', '')
        amount_str = amount_str.strip()
        
        # Handle abbreviations
        multiplier = 1
        if re.search(r'[Mm](?:illion)?$', amount_str):
            multiplier = 1_000_000
            amount_str = re.sub(r'[Mm](?:illion)?$', '', amount_str)
        elif re.search(r'[Kk](?:ilo)?$', amount_str):
            multiplier = 1_000
            amount_str = re.sub(r'[Kk](?:ilo)?$', '', amount_str)
        elif re.search(r'[Bb](?:illion)?$', amount_str):
            multiplier = 1_000_000_000
            amount_str = re.sub(r'[Bb](?:illion)?$', '', amount_str)
        
        # Remove whitespace and commas
        amount_str = amount_str.replace(',', '').replace(' ', '').strip()
        
        # Check for parentheses (negative)
        is_negative = False
        if amount_str.startswith('(') and amount_str.endswith(')'):
            is_negative = True
            amount_str = amount_str[1:-1]
        
        # Parse number
        try:
            amount = float(amount_str) * multiplier
            if is_negative:
                amount = -amount
            return amount
        except (ValueError, TypeError):
            return 0.0
    
    def _classify_sections(self):
        """Classify each row into financial sections."""
        if 'rows' not in self.normalized_data:
            return
        
        sections = {
            'revenue': [],
            'cost_of_revenue': [],
            'expenses': [],
            'gross_profit': [],
            'operating_income': [],
            'net_income': [],
            'assets': [],
            'liabilities': [],
            'equity': [],
            'cash_inflow': [],
            'cash_outflow': [],
            'other': []
        }
        
        for row in self.normalized_data['rows']:
            label_lower = row['label'].lower()
            classified = False
            
            # Check each section's keywords
            for section_name, keywords in self.SECTION_KEYWORDS.items():
                if any(kw in label_lower for kw in keywords):
                    sections[section_name].append(row)
                    classified = True
                    break
            
            if not classified:
                sections['other'].append(row)
        
        self.normalized_data['sections'] = sections
        
        # Detect statement type
        self._detect_statement_type(sections)
        
        logger.info(f"Classified into sections. Statement type: {self.statement_type}")
        
        # Debug: Show section counts and sample classifications
        logger.info(f"🔍 DEBUG: Section counts - Revenue: {len(sections['revenue'])}, Expenses: {len(sections['expenses'])}, Cost of Revenue: {len(sections['cost_of_revenue'])}, Other: {len(sections['other'])}")
        if sections['revenue']:
            logger.info(f"🔍 DEBUG: Sample revenue items: {[r['label'] for r in sections['revenue'][:3]]}")
        if sections['expenses']:
            logger.info(f"🔍 DEBUG: Sample expense items: {[r['label'] for r in sections['expenses'][:3]]}")
    
    def _detect_statement_type(self, sections: Dict[str, List]):
        """Detect the type of financial statement."""
        revenue_count = len(sections.get('revenue', []))
        expense_count = len(sections.get('expenses', []))
        asset_count = len(sections.get('assets', []))
        liability_count = len(sections.get('liabilities', []))
        cash_inflow_count = len(sections.get('cash_inflow', []))
        cash_outflow_count = len(sections.get('cash_outflow', []))
        
        # Scoring system
        scores = {
            'income_statement': revenue_count + expense_count,
            'balance_sheet': asset_count + liability_count,
            'cash_flow': cash_inflow_count + cash_outflow_count
        }
        
        self.statement_type = max(scores, key=scores.get) if max(scores.values()) > 0 else 'unknown'
    
    def _calculate_metrics(self) -> Dict[str, float]:
        """Calculate financial metrics from classified sections."""
        sections = self.normalized_data.get('sections', {})
        
        # Calculate totals
        total_revenue = sum(row['amount'] for row in sections.get('revenue', []))
        cost_of_revenue = sum(row['amount'] for row in sections.get('cost_of_revenue', []))
        total_expenses = sum(row['amount'] for row in sections.get('expenses', []))
        
        # Check for explicit totals
        gross_profit_explicit = sum(row['amount'] for row in sections.get('gross_profit', []))
        operating_income_explicit = sum(row['amount'] for row in sections.get('operating_income', []))
        net_income_explicit = sum(row['amount'] for row in sections.get('net_income', []))
        
        # Calculate derived values
        gross_profit = gross_profit_explicit if gross_profit_explicit else (total_revenue - cost_of_revenue)
        operating_income = operating_income_explicit if operating_income_explicit else (gross_profit - total_expenses)
        net_income = net_income_explicit if net_income_explicit else operating_income
        
        # Calculate ratios
        profit_margin = (net_income / total_revenue * 100) if total_revenue > 0 else 0
        profit_margin = min(profit_margin, 100)  # Cap at 100%
        
        operating_margin = (operating_income / total_revenue * 100) if total_revenue > 0 else 0
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        expense_ratio = (total_expenses / total_revenue * 100) if total_revenue > 0 else 0
        
        metrics = {
            'total_revenue': total_revenue,
            'cost_of_revenue': cost_of_revenue,
            'gross_profit': gross_profit,
            'total_operating_expenses': total_expenses,
            'operating_income': operating_income,
            'net_income': net_income,
            'profit_margin': profit_margin,
            'operating_margin': operating_margin,
            'gross_margin': gross_margin,
            'expense_ratio': expense_ratio
        }
        
        # Add balance sheet metrics if applicable
        if self.statement_type == 'balance_sheet':
            total_assets = sum(row['amount'] for row in sections.get('assets', []))
            total_liabilities = sum(row['amount'] for row in sections.get('liabilities', []))
            total_equity = sum(row['amount'] for row in sections.get('equity', []))
            
            metrics.update({
                'total_assets': total_assets,
                'total_liabilities': total_liabilities,
                'total_equity': total_equity,
                'debt_to_equity': (total_liabilities / total_equity) if total_equity > 0 else 0
            })
        
        # Add cash flow metrics if applicable
        if self.statement_type == 'cash_flow':
            cash_inflow = sum(row['amount'] for row in sections.get('cash_inflow', []))
            cash_outflow = sum(row['amount'] for row in sections.get('cash_outflow', []))
            net_cash_flow = cash_inflow - cash_outflow
            
            metrics.update({
                'cash_inflow': cash_inflow,
                'cash_outflow': cash_outflow,
                'net_cash_flow': net_cash_flow
            })
        
        logger.info(f"Calculated metrics: {metrics}")
        return metrics
    
    def _generate_projections(self, current_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Generate next-period projections based on current metrics and detected period."""
        if not self.detected_period:
            return {}
        
        period_info = self.detected_period
        end_date = period_info.get('end_date')
        period_type = period_info.get('period_type', 'unknown')
        
        # Calculate next period dates
        if period_type == 'quarterly':
            next_start = end_date + timedelta(days=1)
            next_end = next_start + relativedelta(months=3, days=-1)
            next_period_label = f"Q{((end_date.month - 1) // 3 + 1) % 4 + 1} {end_date.year if end_date.month < 10 else end_date.year + 1}"
        elif period_type == 'annual':
            next_start = end_date + timedelta(days=1)
            next_end = next_start + relativedelta(years=1, days=-1)
            next_period_label = f"Year {end_date.year + 1}"
        else:
            # Default to 3 months ahead
            next_start = end_date + timedelta(days=1)
            next_end = next_start + relativedelta(months=3, days=-1)
            next_period_label = f"{next_start.strftime('%b')}–{next_end.strftime('%b %Y')}"
        
        # Apply growth rates
        growth_rates = self.DEFAULT_GROWTH_RATES
        
        projections = {
            'period_label': next_period_label,
            'start_date': next_start.isoformat(),
            'end_date': next_end.isoformat(),
            'projected_revenue': current_metrics.get('total_revenue', 0) * (1 + growth_rates['revenue']),
            'projected_net_income': current_metrics.get('net_income', 0) * (1 + growth_rates['net_income']),
            'projected_expenses': current_metrics.get('total_operating_expenses', 0) * (1 + growth_rates['expenses']),
            'revenue_growth': growth_rates['revenue'] * 100,
            'net_income_growth': growth_rates['net_income'] * 100,
            'expense_growth': growth_rates['expenses'] * 100
        }
        
        # Calculate projected profit margin
        if projections['projected_revenue'] > 0:
            projections['projected_profit_margin'] = (
                projections['projected_net_income'] / projections['projected_revenue'] * 100
            )
        else:
            projections['projected_profit_margin'] = 0
        
        logger.info(f"Generated projections for: {next_period_label}")
        return projections
    
    def _build_output(self, metrics: Dict[str, float], projections: Dict[str, Any]) -> Dict[str, Any]:
        """Build final structured output."""
        period_info = self.detected_period or {}
        
        # Build structured JSON
        structured_data = {
            'metadata': {
                'statement_type': self.statement_type,
                'currency': self.currency,
                'period': {
                    'start_date': period_info.get('start_date').isoformat() if period_info.get('start_date') else None,
                    'end_date': period_info.get('end_date').isoformat() if period_info.get('end_date') else None,
                    'period_type': period_info.get('period_type'),
                    'quarter': period_info.get('quarter'),
                    'year': period_info.get('year')
                }
            },
            'current_metrics': metrics,
            'projections': projections
        }
        
        # Build human-readable summary
        summary = self._generate_summary(metrics, projections)
        
        output = {
            'success': True,
            'structured_data': structured_data,
            'summary': summary,
            'json_output': json.dumps(structured_data, indent=2)
        }
        
        return output
    
    def _generate_summary(self, metrics: Dict[str, float], projections: Dict[str, Any]) -> str:
        """Generate human-readable financial summary."""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("FINANCIAL STATEMENT ANALYSIS")
        lines.append("=" * 80)
        lines.append("")
        
        # Period information
        period_info = self.detected_period or {}
        if period_info.get('end_date'):
            if period_info.get('start_date'):
                lines.append(f"Period: {period_info['start_date'].strftime('%b %d, %Y')} to {period_info['end_date'].strftime('%b %d, %Y')}")
            else:
                lines.append(f"Period Ending: {period_info['end_date'].strftime('%b %d, %Y')}")
            
            if period_info.get('quarter'):
                lines.append(f"Quarter: Q{period_info['quarter']} {period_info['year']}")
            lines.append("")
        
        # Current Financial Overview
        lines.append("CURRENT FINANCIAL OVERVIEW")
        lines.append("-" * 80)
        
        if self.statement_type in ['income_statement', 'unknown']:
            lines.append(f"Total Revenue:          {self.currency} {metrics.get('total_revenue', 0):,.2f}")
            if metrics.get('cost_of_revenue', 0) > 0:
                lines.append(f"Cost of Revenue:        {self.currency} {metrics.get('cost_of_revenue', 0):,.2f}")
                lines.append(f"Gross Profit:           {self.currency} {metrics.get('gross_profit', 0):,.2f}")
            lines.append(f"Operating Expenses:     {self.currency} {metrics.get('total_operating_expenses', 0):,.2f}")
            lines.append(f"Operating Income:       {self.currency} {metrics.get('operating_income', 0):,.2f}")
            lines.append(f"Net Income:             {self.currency} {metrics.get('net_income', 0):,.2f}")
            lines.append("")
            lines.append(f"Profit Margin:          {metrics.get('profit_margin', 0):.1f}%")
            lines.append(f"Operating Margin:       {metrics.get('operating_margin', 0):.1f}%")
            if metrics.get('gross_margin', 0) > 0:
                lines.append(f"Gross Margin:           {metrics.get('gross_margin', 0):.1f}%")
        
        elif self.statement_type == 'balance_sheet':
            lines.append(f"Total Assets:           {self.currency} {metrics.get('total_assets', 0):,.2f}")
            lines.append(f"Total Liabilities:      {self.currency} {metrics.get('total_liabilities', 0):,.2f}")
            lines.append(f"Total Equity:           {self.currency} {metrics.get('total_equity', 0):,.2f}")
            lines.append("")
            lines.append(f"Debt-to-Equity Ratio:   {metrics.get('debt_to_equity', 0):.2f}")
        
        elif self.statement_type == 'cash_flow':
            lines.append(f"Cash Inflow:            {self.currency} {metrics.get('cash_inflow', 0):,.2f}")
            lines.append(f"Cash Outflow:           {self.currency} {metrics.get('cash_outflow', 0):,.2f}")
            lines.append(f"Net Cash Flow:          {self.currency} {metrics.get('net_cash_flow', 0):,.2f}")
        
        lines.append("")
        
        # Projections
        if projections:
            lines.append(f"NEXT PERIOD PROJECTIONS ({projections.get('period_label', 'N/A')})")
            lines.append("-" * 80)
            lines.append(f"Period: {projections.get('start_date')} to {projections.get('end_date')}")
            lines.append("")
            
            if self.statement_type in ['income_statement', 'unknown']:
                lines.append(f"Projected Revenue:      {self.currency} {projections.get('projected_revenue', 0):,.2f}")
                lines.append(f"                        (+{projections.get('revenue_growth', 0):.1f}% growth)")
                lines.append("")
                lines.append(f"Projected Net Income:   {self.currency} {projections.get('projected_net_income', 0):,.2f}")
                lines.append(f"                        (+{projections.get('net_income_growth', 0):.1f}% growth)")
                lines.append("")
                lines.append(f"Projected Profit Margin: {projections.get('projected_profit_margin', 0):.1f}%")
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)


def parse_financial_statement(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Convenience function to parse a financial statement.
    
    Args:
        file_path: Path to the financial statement file
        
    Returns:
        Dictionary containing parsed data and analysis
    """
    parser = UniversalFinancialParser()
    return parser.parse_file(file_path)


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python UniversalFinancialParser.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        result = parse_financial_statement(file_path)
        
        print(result['summary'])
        print("\n")
        print("STRUCTURED JSON OUTPUT:")
        print("-" * 80)
        print(result['json_output'])
        
    except Exception as e:
        logger.error(f"Error parsing file: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


