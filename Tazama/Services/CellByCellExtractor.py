# CellByCellExtractor.py - Intelligent Cell-by-Cell Financial Data Extraction
"""
Advanced cell-by-cell extraction system that:
1. Reads every single cell in the uploaded sheet
2. Intelligently identifies financial data from cell content and position
3. Creates structured JSON data
4. Logs everything to database and terminal
5. Feeds clean JSON to the model
"""

import pandas as pd
import numpy as np
import json
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from decimal import Decimal

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from Tazama.Services.DataNormalizationPipeline import DataNormalizationPipeline

logger = logging.getLogger(__name__)


class CellByCellExtractor:
    """
    Intelligent cell-by-cell extractor that parses every cell
    and builds structured financial data
    """
    
    def __init__(self):
        self.normalization_pipeline = DataNormalizationPipeline()
        self.financial_keywords = self._initialize_financial_keywords()
        self.cell_data = []  # Store all parsed cells
        self.structured_data = {}  # Final structured JSON
        
    def _get_excel_cell_reference(self, row_idx: int, col_idx: int) -> str:
        """Convert row/column indices to Excel cell reference (A1, B2, AA1, etc.)"""
        col_letters = ""
        col_num = col_idx + 1  # 1-indexed
        while col_num > 0:
            col_num -= 1
            col_letters = chr(65 + (col_num % 26)) + col_letters
            col_num //= 26
        return f"{col_letters}{row_idx + 1}"
    
    def _initialize_financial_keywords(self) -> Dict[str, List[str]]:
        """Initialize comprehensive financial keywords for cell matching"""
        return {
            'total_revenue': [
                'total revenue', 'revenue', 'sales revenue', 'service revenue',
                'other operating income', 'total sales', 'net sales', 'gross sales',
                'sales', 'income', 'total income', 'operating revenue'
            ],
            'cost_of_revenue': [
                'cost of goods sold', 'cost of sales', 'cogs', 'cost of revenue',
                'purchases', 'direct labor', 'equipment', 'materials'
            ],
            'gross_profit': [
                'gross profit', 'gross income', 'gross margin'
            ],
            'operating_expenses': [
                'operating expenses', 'total operating expenses', 'opex',
                'salaries', 'wages', 'rent', 'utilities', 'marketing', 'advertising',
                'office supplies', 'internet', 'communication', 'transport', 'delivery',
                'repairs', 'maintenance', 'insurance', 'licenses', 'permits',
                'miscellaneous', 'administrative', 'selling', 'general'
            ],
            'operating_income': [
                'operating income', 'operating profit', 'operating earnings'
            ],
            'net_income': [
                'net income', 'net profit', 'net income after tax', 'profit after tax',
                'net income before tax', 'income before tax'
            ],
            'interest_income': [
                'interest income', 'interest earned'
            ],
            'interest_expense': [
                'interest expense', 'interest paid'
            ],
            'tax_expense': [
                'income tax', 'tax expense', 'tax', 'income tax expense'
            ],
            'other_income': [
                'other income', 'gain', 'other operating income'
            ],
            'other_expenses': [
                'other expenses', 'loss', 'other expense'
            ]
        }
    
    def extract_from_dataframe(self, df: pd.DataFrame, sheet_name: str = 'Sheet1', 
                              corporate=None, user=None, upload_record=None) -> Dict[str, Any]:
        """
        Extract financial data by parsing every cell in the dataframe
        
        Args:
            df: DataFrame to extract from
            sheet_name: Name of the sheet
            corporate: Corporate instance for logging
            user: User instance for logging
            upload_record: Upload record for logging
            
        Returns:
            Dictionary with extracted and structured data
        """
        try:
            logger.info(f"🔍 Starting cell-by-cell extraction from sheet: {sheet_name}")
            logger.info(f"   DataFrame shape: {df.shape[0]} rows x {df.shape[1]} columns")
            
            # Reset cell data storage
            self.cell_data = []
            self.structured_data = {}
            
            # Step 1: Parse every cell
            parsed_cells = self._parse_all_cells(df, sheet_name)
            
            # Step 2: Build structured data from parsed cells (using DataFrame for better matching)
            structured = self._build_structured_data(parsed_cells, df)
            
            # Step 3: Normalize the data
            normalized = self.normalization_pipeline.normalize_and_calculate(structured)
            
            # Step 4: Create JSON structure for model
            json_data = self._create_model_json(normalized)
            
            # Step 5: Log to database
            if corporate and user:
                self._log_to_database(
                    parsed_cells, structured, normalized, json_data,
                    corporate, user, upload_record, sheet_name
                )
            
            # Step 6: Print to terminal
            self._print_to_terminal(parsed_cells, structured, normalized, json_data)
            
            return {
                'success': True,
                'parsed_cells': parsed_cells,
                'structured_data': structured,
                'normalized_data': normalized,
                'json_data': json_data,
                'total_cells_parsed': len(parsed_cells),
                'sheet_name': sheet_name
            }
            
        except Exception as e:
            logger.error(f"Error in cell-by-cell extraction: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _parse_all_cells(self, df: pd.DataFrame, sheet_name: str) -> List[Dict[str, Any]]:
        """Parse every single cell in the dataframe"""
        parsed_cells = []
        
        # Iterate through every cell
        for row_idx in range(len(df)):
            for col_idx in range(len(df.columns)):
                cell_value = df.iloc[row_idx, col_idx]
                
                # Skip NaN/empty cells
                if pd.isna(cell_value) or (isinstance(cell_value, str) and cell_value.strip() == ''):
                    continue
                
                # Parse cell
                cell_info = self._parse_cell(
                    cell_value, row_idx, col_idx, 
                    df.columns[col_idx], df, sheet_name
                )
                
                if cell_info:
                    parsed_cells.append(cell_info)
        
        logger.info(f"✅ Parsed {len(parsed_cells)} cells from {df.shape[0]} rows x {df.shape[1]} columns")
        return parsed_cells
    
    def _parse_cell(self, value: Any, row_idx: int, col_idx: int, 
                   col_name: str, df: pd.DataFrame, sheet_name: str) -> Optional[Dict[str, Any]]:
        """Parse a single cell and identify its type and value"""
        cell_info = {
            'sheet': sheet_name,
            'row': row_idx + 1,  # 1-indexed for readability
            'column': col_idx + 1,
            'column_name': str(col_name),
            'raw_value': str(value) if value is not None else '',
            'cell_reference': self._get_excel_cell_reference(row_idx, col_idx),  # Excel-style (A1, B2, etc.)
            'data_type': None,
            'financial_category': None,
            'numeric_value': None,
            'is_total': False,
            'is_label': False,
            'context': {}
        }
        
        # Convert to string for analysis
        cell_str = str(value).strip().lower() if value is not None else ''
        
        # Check if it's a number
        numeric_value = self._extract_numeric_value(value)
        if numeric_value is not None:
            cell_info['numeric_value'] = numeric_value
            cell_info['data_type'] = 'numeric'
        
        # Check if it's a label/header
        if self._is_label(cell_str):
            cell_info['is_label'] = True
            cell_info['data_type'] = 'label'
            # Identify financial category
            category = self._identify_financial_category(cell_str)
            if category:
                cell_info['financial_category'] = category
        
        # Check if it's a total row
        if 'total' in cell_str and numeric_value is not None:
            cell_info['is_total'] = True
        
        # Get context (surrounding cells)
        cell_info['context'] = self._get_cell_context(df, row_idx, col_idx)
        
        return cell_info
    
    def _extract_numeric_value(self, value: Any) -> Optional[float]:
        """Extract numeric value from cell"""
        if pd.isna(value):
            return None
        
        # If already numeric
        if isinstance(value, (int, float)):
            return float(value)
        
        # If string, try to parse
        if isinstance(value, str):
            # Remove currency symbols, commas, spaces
            cleaned = re.sub(r'[^\d\.\-\(\)]', '', value.replace(',', '').strip())
            # Handle parentheses for negative numbers
            if '(' in cleaned and ')' in cleaned:
                cleaned = '-' + cleaned.replace('(', '').replace(')', '')
            try:
                return float(cleaned) if cleaned else None
            except ValueError:
                return None
        
        return None
    
    def _is_label(self, text: str) -> bool:
        """Check if cell contains a label/header"""
        if not text:
            return False
        
        # Check if it contains financial keywords
        for category, keywords in self.financial_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return True
        
        # Check for common label patterns
        label_patterns = [
            r'^[a-zA-Z\s]+$',  # Only letters and spaces
            r'revenue', r'expense', r'income', r'profit', r'cost', r'tax'
        ]
        
        for pattern in label_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _identify_financial_category(self, text: str) -> Optional[str]:
        """Identify which financial category a label belongs to"""
        text_lower = text.lower().strip()
        
        # ✅ PRIORITY: Check for exact matches first (most specific)
        # Order matters - check more specific categories first
        category_priority = [
            ('net_income', ['net income', 'net profit', 'net income after tax', 'profit after tax']),
            ('operating_income', ['operating income', 'operating profit', 'operating earnings']),
            ('gross_profit', ['gross profit', 'gross income', 'gross margin']),
            ('total_operating_expenses', ['total operating expenses', 'operating expenses', 'opex']),
            ('cost_of_revenue', ['cost of goods sold', 'cost of sales', 'cogs', 'cost of revenue']),
            ('total_revenue', ['total revenue', 'revenue', 'sales revenue', 'service revenue', 'total sales', 'net sales']),
            ('interest_income', ['interest income', 'interest earned']),
            ('interest_expense', ['interest expense', 'interest paid']),
            ('income_tax_expense', ['income tax', 'tax expense', 'income tax expense']),
        ]
        
        # Check exact phrase matches first
        for category, keywords in category_priority:
            for keyword in keywords:
                if keyword in text_lower:
                    # Additional check: make sure it's not a substring match that's too generic
                    # e.g., "income" alone shouldn't match "operating income" when we want "operating_income"
                    if len(keyword) >= 5 or text_lower == keyword:  # Only short keywords need exact match
                        return category
        
        # Fallback: check for partial matches (but be more careful)
        # Only match if the keyword is substantial (at least 6 chars) to avoid false positives
        for category, keywords in self.financial_keywords.items():
            for keyword in keywords:
                if len(keyword) >= 6 and keyword in text_lower:
                    # Avoid matching "income" in "operating income" to "total_revenue"
                    if category == 'total_revenue' and 'operating' in text_lower:
                        continue  # Skip - this is likely operating income, not revenue
                    if category == 'total_revenue' and 'net' in text_lower:
                        continue  # Skip - this is likely net income, not revenue
                    return category
        
        return None
    
    def _get_cell_context(self, df: pd.DataFrame, row_idx: int, col_idx: int) -> Dict[str, Any]:
        """Get context from surrounding cells"""
        context = {
            'left_cell': None,
            'right_cell': None,
            'above_cell': None,
            'below_cell': None,
            'row_data': [],
            'column_data': []
        }
        
        # Left cell
        if col_idx > 0:
            context['left_cell'] = str(df.iloc[row_idx, col_idx - 1]) if not pd.isna(df.iloc[row_idx, col_idx - 1]) else None
        
        # Right cell
        if col_idx < len(df.columns) - 1:
            context['right_cell'] = str(df.iloc[row_idx, col_idx + 1]) if not pd.isna(df.iloc[row_idx, col_idx + 1]) else None
        
        # Above cell
        if row_idx > 0:
            context['above_cell'] = str(df.iloc[row_idx - 1, col_idx]) if not pd.isna(df.iloc[row_idx - 1, col_idx]) else None
        
        # Below cell
        if row_idx < len(df) - 1:
            context['below_cell'] = str(df.iloc[row_idx + 1, col_idx]) if not pd.isna(df.iloc[row_idx + 1, col_idx]) else None
        
        # Row data (all cells in same row)
        context['row_data'] = [str(df.iloc[row_idx, c]) if not pd.isna(df.iloc[row_idx, c]) else '' 
                               for c in range(len(df.columns))]
        
        # Column data (all cells in same column, limited to 10 for performance)
        context['column_data'] = [str(df.iloc[r, col_idx]) if not pd.isna(df.iloc[r, col_idx]) else '' 
                                  for r in range(max(0, row_idx - 5), min(len(df), row_idx + 6))]
        
        return context
    
    def _build_structured_data(self, parsed_cells: List[Dict[str, Any]], df: pd.DataFrame) -> Dict[str, float]:
        """Build structured financial data from parsed cells using DataFrame for accurate value matching"""
        structured = {
            'total_revenue': 0.0,
            'cost_of_revenue': 0.0,
            'gross_profit': 0.0,
            'total_operating_expenses': 0.0,
            'operating_income': 0.0,
            'net_income': 0.0,
            'interest_income': 0.0,
            'interest_expense': 0.0,
            'income_tax_expense': 0.0,
            'net_income_before_tax': 0.0,
        }
        
        # ✅ IMPROVED: Find values by looking at the actual DataFrame structure
        # Look for label cells and find their corresponding values in the same row
        for cell in parsed_cells:
            if cell.get('is_label') and cell.get('financial_category'):
                category = cell['financial_category']
                row_idx = cell['row'] - 1  # Convert to 0-indexed
                col_idx = cell['column'] - 1
                
                # Check all columns in the same row for numeric values
                for c in range(len(df.columns)):
                    if c != col_idx:  # Skip the label column itself
                        try:
                            cell_value = df.iloc[row_idx, c]
                            numeric_value = self._extract_numeric_value(cell_value)
                            if numeric_value is not None and abs(numeric_value) > 0:
                                # For revenue, prefer positive values; for expenses, accept both
                                if category == 'total_revenue' and numeric_value < 0:
                                    continue  # Skip negative values for revenue
                                # Use absolute value for comparison, but keep sign
                                if abs(numeric_value) > abs(structured[category]):
                                    structured[category] = abs(numeric_value) if category == 'total_revenue' else numeric_value
                                    logger.info(f"✅ Found {category}: {structured[category]:,.2f} at row {row_idx+1}, col {c+1} (label: '{cell['raw_value']}')")
                        except (IndexError, KeyError):
                            continue
        
        # ✅ Also check for cells with numeric values that might be totals
        # Look for cells with "total" in nearby labels
        for cell in parsed_cells:
            if cell.get('numeric_value') and cell.get('numeric_value') != 0:
                row_idx = cell['row'] - 1
                col_idx = cell['column'] - 1
                value = cell['numeric_value']
                
                # Check if there's a label in the same row
                for c in range(len(df.columns)):
                    if c != col_idx:
                        try:
                            label_cell = df.iloc[row_idx, c]
                            if pd.notna(label_cell):
                                label_str = str(label_cell).strip().lower()
                                # Check if label matches any financial category
                                for category, keywords in self.financial_keywords.items():
                                    for keyword in keywords:
                                        if keyword in label_str:
                                            # Use this value if it's larger
                                            if abs(value) > abs(structured[category]):
                                                structured[category] = value
                                                logger.info(f"✅ Matched {category}: {value:,.2f} with label '{label_str}'")
                                                break
                        except (IndexError, KeyError):
                            continue
        
        # ✅ Sum up detail rows for categories that might have multiple entries
        # This helps with cases where there are multiple revenue/expense lines
        category_sums = {}
        for cell in parsed_cells:
            if cell.get('financial_category') and cell.get('numeric_value'):
                category = cell['financial_category']
                if category not in category_sums:
                    category_sums[category] = []
                category_sums[category].append(cell['numeric_value'])
        
        # For categories with multiple values, sum them if they're all positive (revenue) or all negative (expenses)
        for category, values in category_sums.items():
            if len(values) > 1:
                # Check if all same sign
                all_positive = all(v > 0 for v in values)
                all_negative = all(v < 0 for v in values)
                if all_positive or all_negative:
                    total = sum(values)
                    if abs(total) > abs(structured[category]):
                        structured[category] = total
                        logger.info(f"✅ Summed {category}: {total:,.2f} from {len(values)} entries")
        
        logger.info(f"📊 Final structured data: {structured}")
        return structured
    
    def _create_model_json(self, normalized_data: Dict[str, float]) -> Dict[str, Any]:
        """Create JSON structure for model input"""
        return {
            'totalRevenue': normalized_data.get('total_revenue', 0.0),
            'costOfRevenue': normalized_data.get('cost_of_revenue', 0.0),
            'grossProfit': normalized_data.get('gross_profit', 0.0),
            'totalOperatingExpenses': normalized_data.get('total_operating_expenses', 0.0),
            'operatingIncome': normalized_data.get('operating_income', 0.0),
            'netIncome': normalized_data.get('net_income', 0.0),
            'interestIncome': normalized_data.get('interest_income', 0.0),
            'interestExpense': normalized_data.get('interest_expense', 0.0),
            'incomeTaxExpense': normalized_data.get('income_tax_expense', 0.0),
            'researchDevelopment': 0.0,  # Default if not found
        }
    
    def _log_to_database(self, parsed_cells: List[Dict], structured: Dict, 
                         normalized: Dict, json_data: Dict,
                         corporate, user, upload_record, sheet_name: str):
        """Log extraction data to database using TransactionLogBase"""
        try:
            # Log parsed cells summary
            TransactionLogBase.log(
                transaction_type="TAZAMA_DATA_EXTRACTION_CELLS",
                user=user,
                message=f"Cell-by-cell extraction completed for sheet: {sheet_name}",
                state_name="Success",
                extra={
                    'sheet_name': sheet_name,
                    'total_cells_parsed': len(parsed_cells),
                    'cells_with_data': len([c for c in parsed_cells if c.get('numeric_value')]),
                    'cells_with_labels': len([c for c in parsed_cells if c.get('is_label')]),
                    'upload_record_id': upload_record.id if upload_record else None,
                }
            )
            
            # Log structured data
            TransactionLogBase.log(
                transaction_type="TAZAMA_DATA_EXTRACTION_STRUCTURED",
                user=user,
                message="Structured financial data extracted",
                state_name="Success",
                extra={
                    'structured_data': structured,
                    'sheet_name': sheet_name,
                    'upload_record_id': upload_record.id if upload_record else None,
                }
            )
            
            # Log normalized data
            TransactionLogBase.log(
                transaction_type="TAZAMA_DATA_EXTRACTION_NORMALIZED",
                user=user,
                message="Normalized financial data ready for model",
                state_name="Success",
                extra={
                    'normalized_data': normalized,
                    'sheet_name': sheet_name,
                    'upload_record_id': upload_record.id if upload_record else None,
                }
            )
            
            # Log final JSON data
            TransactionLogBase.log(
                transaction_type="TAZAMA_DATA_EXTRACTION_JSON",
                user=user,
                message="JSON data structure created for model input",
                state_name="Success",
                extra={
                    'json_data': json_data,
                    'sheet_name': sheet_name,
                    'upload_record_id': upload_record.id if upload_record else None,
                }
            )
            
            logger.info("✅ Data extraction logged to database")
            
        except Exception as e:
            logger.error(f"Error logging to database: {e}", exc_info=True)
    
    def _print_to_terminal(self, parsed_cells: List[Dict], structured: Dict,
                          normalized: Dict, json_data: Dict):
        """Print extraction data to terminal for visibility"""
        print("\n" + "="*80)
        print("📊 CELL-BY-CELL EXTRACTION RESULTS")
        print("="*80)
        
        print(f"\n✅ Total Cells Parsed: {len(parsed_cells)}")
        print(f"   - Cells with numeric values: {len([c for c in parsed_cells if c.get('numeric_value')])}")
        print(f"   - Cells with labels: {len([c for c in parsed_cells if c.get('is_label')])}")
        print(f"   - Total rows: {len(set([c['row'] for c in parsed_cells]))}")
        print(f"   - Total columns: {len(set([c['column'] for c in parsed_cells]))}")
        
        print("\n📋 STRUCTURED DATA (Before Normalization):")
        print("-" * 80)
        for key, value in structured.items():
            if value > 0:
                print(f"   {key:30s}: {value:>15,.2f}")
        
        print("\n🔧 NORMALIZED DATA (After Calculation):")
        print("-" * 80)
        for key, value in normalized.items():
            if value > 0:
                print(f"   {key:30s}: {value:>15,.2f}")
        
        print("\n📦 JSON DATA (For Model Input):")
        print("-" * 80)
        print(json.dumps(json_data, indent=2))
        
        print("\n🔍 SAMPLE PARSED CELLS (First 10 with data):")
        print("-" * 80)
        cells_with_data = [c for c in parsed_cells if c.get('numeric_value') or c.get('is_label')][:10]
        for cell in cells_with_data:
            print(f"   Cell {cell['cell_reference']:5s} (R{cell['row']:3d},C{cell['column']:2d}): "
                  f"{cell['raw_value'][:40]:40s} | "
                  f"Type: {cell['data_type']:8s} | "
                  f"Value: {cell.get('numeric_value', 'N/A')}")
            if cell.get('financial_category'):
                print(f"      └─ Category: {cell['financial_category']}")
        
        print("\n" + "="*80 + "\n")

