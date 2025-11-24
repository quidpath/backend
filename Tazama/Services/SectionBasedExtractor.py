# SectionBasedExtractor.py - Section-Aware Financial Statement Parser
"""
Advanced financial statement extractor that:
1. Ignores placeholder "Total for X" rows
2. Detects grouped sections (Operating Income, COGS, Operating Expenses, etc.)
3. Sums line items within each section
4. Calculates accurate totals and derived metrics
"""

import pandas as pd
import numpy as np
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal

from quidpath_backend.core.utils.Logbase import TransactionLogBase
from Tazama.Services.DataNormalizationPipeline import DataNormalizationPipeline

logger = logging.getLogger(__name__)


class SectionBasedExtractor:
    """
    Section-aware extractor that groups line items by section
    and calculates accurate totals by summing, not trusting spreadsheet totals
    """
    
    def __init__(self):
        self.normalization_pipeline = DataNormalizationPipeline()
        self.section_keywords = self._initialize_section_keywords()
        
    def _initialize_section_keywords(self) -> Dict[str, List[str]]:
        """Initialize section detection keywords"""
        return {
            'operating_income': [
                'operating income', 'sales', 'revenue', 'service revenue',
                'product revenue', 'other operating income', 'income from operations',
                'other income', 'other revenue'  # Include other income in revenue
            ],
            'cogs': [
                'cost of goods sold', 'cogs', 'cost of sales', 'direct costs',
                'cost of revenue', 'production costs', 'purchases', 'parts', 'materials',
                'labor costs', 'casuals', 'hire of small tools', 'equipment'
            ],
            'operating_expenses': [
                'operating expenses', 'operating expense', 'opex',
                'salaries', 'wages', 'rent', 'rent expense', 'utilities', 'marketing',
                'advertising', 'office supplies', 'administrative',
                'selling expenses', 'general expenses', 'sg&a',
                'selling, general and administrative', 'office expense',
                'professional fees', 'travel', 'accommodation', 'allowance',
                'delivery', 'postage', 'telephone', 'internet', 'electricity', 'water',
                'insurance', 'repairs', 'maintenance', 'fuel', 'vehicle', 'parking',
                'meals', 'entertainment', 'printing', 'stationery', 'consultant',
                'credit card', 'bank fees', 'charges', 'fines', 'penalty',
                'tendering', 'clearing', 'forwarding', 'promotions', 'commissions',
                'business licenses', 'permits', 'bad debt', 'employee bonuses',
                'staff costs', 'staff uniforms', 'housing levy', 'nita fee',
                'nssf company contribution', 'statutory expense', 'internship allowance',
                'merchant account fees', 'computer', 'hardware', 'subscriptions'
            ],
            'non_operating_income': [
                'non-operating income', 'other income', 'interest income',
                'investment income', 'gain', 'other revenue'
            ],
            'non_operating_expenses': [
                'non-operating expenses', 'other expenses', 'interest expense',
                'interest paid', 'loss', 'other expense'
            ],
            'tax': [
                'income tax', 'tax expense', 'tax', 'provision for income tax'
            ]
        }
    
    def extract_from_dataframe(self, df: pd.DataFrame, sheet_name: str = 'Sheet1',
                              corporate=None, user=None, upload_record=None) -> Dict[str, Any]:
        """
        Extract financial data by detecting sections and summing line items
        
        Args:
            df: DataFrame to extract from
            sheet_name: Name of the sheet
            corporate: Corporate instance for logging
            user: User instance for logging
            upload_record: Upload record for logging
            
        Returns:
            Dictionary with extracted totals and line items
        """
        try:
            logger.info(f"🔍 Starting section-based extraction from sheet: {sheet_name}")
            logger.info(f"   DataFrame shape: {df.shape[0]} rows x {df.shape[1]} columns")
            logger.info(f"   DataFrame columns: {list(df.columns)}")
            logger.info(f"   First few rows preview:")
            for i in range(min(3, len(df))):
                logger.info(f"      Row {i+1}: {[str(df.iloc[i, j])[:50] if pd.notna(df.iloc[i, j]) else 'NaN' for j in range(min(3, len(df.columns)))]}")
            
            # Step 1: Parse all rows into structured line items
            line_items = self._parse_line_items(df)
            
            if len(line_items) == 0:
                logger.error("❌ CRITICAL: No line items parsed! Extraction will fail.")
                logger.error("   This usually means column detection failed or all rows were skipped.")
                logger.error("   Check the column detection logs above to see what went wrong.")
            
            # Step 2: Group line items by section
            sections = self._group_by_section(line_items)
            
            # Step 3: Calculate totals for each section
            totals = self._calculate_section_totals(sections)
            
            # Step 4: Calculate derived metrics
            derived = self._calculate_derived_metrics(totals)
            
            # Step 5: Create final output structure
            output = self._create_output_structure(totals, derived, line_items)
            
            # Step 6: Normalize the data (but preserve original output structure)
            normalized = self.normalization_pipeline.normalize_and_calculate(output)
            
            # ✅ CRITICAL: Use output structure directly for JSON (not normalized which may have zeros)
            # The normalization pipeline might set values to 0, but we want the actual calculated totals
            # Merge normalized calculated values back into output if they're better
            for key in ['gross_profit', 'operating_profit', 'net_profit']:
                if key in normalized and normalized[key] != 0:
                    output[key] = normalized[key]
            
            # Step 7: Create JSON for model (use output, not normalized)
            json_data = self._create_model_json(output)
            
            # Step 8: Log to database
            if corporate and user:
                self._log_to_database(
                    line_items, sections, totals, derived, output, json_data,
                    corporate, user, upload_record, sheet_name
                )
            
            # Step 9: Print to terminal
            self._print_to_terminal(line_items, sections, totals, derived, output, json_data)
            
            return {
                'success': True,
                'line_items': line_items,
                'sections': sections,
                'totals': totals,
                'derived_metrics': derived,
                'output': output,
                'normalized_data': normalized,
                'json_data': json_data,
                'sheet_name': sheet_name
            }
            
        except Exception as e:
            logger.error(f"Error in section-based extraction: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _parse_line_items(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Parse all rows into structured line items, ignoring placeholder totals and section headers"""
        line_items = []
        
        # ✅ IMPROVED: Detect column structure first (Account/Amount format)
        account_col_idx = None
        amount_col_idx = None
        
        # Check column headers to identify Account and Amount columns
        # ✅ IMPROVED: More comprehensive header detection
        for col_idx, col_name in enumerate(df.columns):
            col_lower = str(col_name).lower().strip()
            # Account column: look for "account", "item", "description", "line item", etc.
            if account_col_idx is None:
                if any(keyword in col_lower for keyword in ['account', 'item', 'description', 'line item', 'line', 'name', 'label']):
                    account_col_idx = col_idx
                    logger.info(f"✅ Found Account column at index {col_idx}: '{col_name}'")
            # Amount column: look for "amount", "value", "kes", "total", etc.
            if amount_col_idx is None:
                if any(keyword in col_lower for keyword in ['amount', 'value', 'kes', 'total', 'balance', 'sum']):
                    amount_col_idx = col_idx
                    logger.info(f"✅ Found Amount column at index {col_idx}: '{col_name}'")
        
        # If not found in headers, try to detect from first few rows
        if account_col_idx is None or amount_col_idx is None:
            for row_idx in range(min(3, len(df))):
                row_data = df.iloc[row_idx]
                for col_idx in range(len(df.columns)):
                    cell_value = row_data.iloc[col_idx]
                    if pd.notna(cell_value):
                        cell_str = str(cell_value).strip().lower()
                        # Check if it looks like a header
                        if account_col_idx is None and ('account' in cell_str or 'item' in cell_str):
                            account_col_idx = col_idx
                        elif amount_col_idx is None and ('amount' in cell_str or 'value' in cell_str or 'kes' in cell_str):
                            amount_col_idx = col_idx
        
        # Fallback: assume first column is account, last numeric column is amount
        if account_col_idx is None:
            account_col_idx = 0
            logger.info(f"⚠️  Account column not detected, using first column (index {account_col_idx})")
        
        if amount_col_idx is None:
            # Find the rightmost column with numeric data
            logger.info("🔍 Searching for amount column by analyzing data...")
            best_col = None
            best_numeric_ratio = 0.0
            
            for col_idx in range(len(df.columns)):
                if col_idx == account_col_idx:
                    continue  # Skip account column
                sample_values = df.iloc[:min(20, len(df)), col_idx].dropna()
                if len(sample_values) > 0:
                    numeric_count = sum(1 for v in sample_values if self._is_numeric(str(v)))
                    numeric_ratio = numeric_count / len(sample_values) if len(sample_values) > 0 else 0
                    logger.debug(f"   Column {col_idx} ('{df.columns[col_idx]}'): {numeric_count}/{len(sample_values)} numeric ({numeric_ratio:.1%})")
                    if numeric_ratio > best_numeric_ratio:
                        best_numeric_ratio = numeric_ratio
                        best_col = col_idx
            
            if best_col is not None and best_numeric_ratio > 0.3:  # At least 30% numeric
                amount_col_idx = best_col
                logger.info(f"✅ Detected amount column: {amount_col_idx} ('{df.columns[amount_col_idx]}') with {best_numeric_ratio:.1%} numeric values")
            else:
                # Default to last column
                amount_col_idx = len(df.columns) - 1
                logger.warning(f"⚠️  Amount column not detected, using last column (index {amount_col_idx}, '{df.columns[amount_col_idx] if amount_col_idx < len(df.columns) else 'N/A'}')")
        
        logger.info(f"📋 Detected columns: Account={account_col_idx} ('{df.columns[account_col_idx] if account_col_idx < len(df.columns) else 'N/A'}'), Amount={amount_col_idx} ('{df.columns[amount_col_idx] if amount_col_idx < len(df.columns) else 'N/A'}')")
        
        # ✅ VALIDATION: Verify column detection worked
        if account_col_idx >= len(df.columns) or amount_col_idx >= len(df.columns):
            logger.error(f"❌ Column detection failed! DataFrame has {len(df.columns)} columns, but detected indices are Account={account_col_idx}, Amount={amount_col_idx}")
            logger.error(f"   DataFrame columns: {list(df.columns)}")
            logger.error(f"   DataFrame shape: {df.shape}")
            # Try to recover by using first and last columns
            account_col_idx = 0
            amount_col_idx = len(df.columns) - 1 if len(df.columns) > 1 else 0
            logger.warning(f"   Recovering: Using Account={account_col_idx}, Amount={amount_col_idx}")
        
        # Section header keywords to skip
        section_header_keywords = [
            'revenue section', 'cogs section', 'cost section', 'operating expenses section',
            'operating expense section', 'non-operating', 'non operating', 'tax section',
            'profit section', 'summary section'
        ]
        
        # ✅ DEBUG: Log first few rows to understand structure
        logger.info(f"🔍 Analyzing first 5 rows to understand structure:")
        for row_idx in range(min(5, len(df))):
            row_data = df.iloc[row_idx]
            account_val = row_data.iloc[account_col_idx] if account_col_idx < len(df.columns) else 'N/A'
            amount_val = row_data.iloc[amount_col_idx] if amount_col_idx < len(df.columns) else 'N/A'
            logger.info(f"   Row {row_idx+1}: Account='{account_val}' | Amount='{amount_val}'")
        
        for row_idx in range(len(df)):
            row_data = df.iloc[row_idx]
            
            # Get account name from detected account column
            account_name = None
            if account_col_idx < len(df.columns):
                account_cell = row_data.iloc[account_col_idx]
                if pd.notna(account_cell):
                    account_name = str(account_cell).strip()
            
            # Get amount from detected amount column
            amount = None
            amount_cell = None
            if amount_col_idx < len(df.columns):
                amount_cell = row_data.iloc[amount_col_idx]
                amount = self._extract_numeric_value(amount_cell)
            
            # Skip empty rows
            if not account_name or account_name == '':
                continue
            
            account_name_lower = account_name.lower()
            
            # ✅ Skip section headers (e.g., "Revenue Section", "COGS Section")
            if any(keyword in account_name_lower for keyword in section_header_keywords):
                logger.debug(f"⏭️  Skipping section header row {row_idx+1}: '{account_name}'")
                continue
            
            # ✅ Skip placeholder totals (e.g., "Total for Revenue Section")
            # BUT: Keep explicit totals like "Total Revenue", "Total COGS", "Total Operating Expenses"
            if account_name_lower.startswith('total for'):
                logger.debug(f"⏭️  Skipping placeholder total row {row_idx+1}: '{account_name}'")
                continue
            
            # ✅ Skip column headers (but allow "Total" as an account name if it has an amount)
            if account_name_lower in ['account', 'account code', 'item', 'description', 'amount', 'value']:
                continue
            
            # ✅ Special handling: "Total" alone might be a header, but "Total Revenue" is a valid line item
            if account_name_lower == 'total' and amount is None:
                continue
            
            # ✅ Skip rows with no amount (section headers, empty rows, etc.)
            # BUT: Allow rows with amount = 0 (legitimate zero values)
            # Only skip if amount is None (couldn't extract)
            if amount is None:
                # Log why we're skipping
                if account_name_lower in ['account', 'account code', 'item', 'description', 'amount', 'value', 'total']:
                    logger.debug(f"⏭️  Skipping header row {row_idx+1}: '{account_name}'")
                elif 'section' in account_name_lower:
                    logger.debug(f"⏭️  Skipping section header row {row_idx+1}: '{account_name}'")
                else:
                    logger.debug(f"⏭️  Skipping row {row_idx+1} (no amount extracted): '{account_name}' | Amount cell: '{amount_cell if amount_col_idx < len(df.columns) else 'N/A'}'")
                continue
            
            # ✅ Allow zero amounts (legitimate financial values can be zero)
            # Only skip if it's clearly a header or section marker
            if amount == 0:
                # Check if it's a section header or total row
                if any(keyword in account_name_lower for keyword in ['section', 'total for', 'summary']):
                    logger.debug(f"⏭️  Skipping section/total row with zero amount {row_idx+1}: '{account_name}'")
                    continue
                # Otherwise, include it (legitimate zero value)
            
            # ✅ Add line item
            line_item = {
                'row': row_idx + 1,
                'account_name': account_name,
                'account_col': account_col_idx,
                'amount': amount,
                'amount_col': amount_col_idx,
                'raw_row': [str(cell) if pd.notna(cell) else '' for cell in row_data]
            }
            line_items.append(line_item)
            # ✅ DETAILED LOGGING: Log all line items for debugging
            logger.info(f"✅ Line item [{row_idx+1}]: '{account_name}' = {amount:,.2f}")
        
        logger.info(f"📊 Parsed {len(line_items)} valid line items (ignored section headers and placeholder totals)")
        return line_items
    
    def _is_numeric(self, text: str) -> bool:
        """Check if text represents a number"""
        if not text or text.strip() == '':
            return False
        try:
            # Remove currency symbols, commas, spaces
            cleaned = re.sub(r'[^\d\.\-\(\)]', '', text.replace(',', '').strip())
            if cleaned == '':
                return False
            # Handle parentheses for negative numbers
            if '(' in cleaned and ')' in cleaned:
                cleaned = '-' + cleaned.replace('(', '').replace(')', '')
            float(cleaned)
            return True
        except ValueError:
            return False
    
    def _extract_numeric_value(self, value: Any) -> Optional[float]:
        """Extract numeric value from cell, handling negatives, commas, and currency symbols"""
        if pd.isna(value):
            return None
        
        # If already numeric
        if isinstance(value, (int, float)):
            return float(value)
        
        # If string, try to parse
        if isinstance(value, str):
            value_str = value.strip()
            if not value_str:
                return None
            
            # ✅ IMPROVED: Handle various formats
            # Remove currency symbols (KES, $, €, £, etc.)
            # Remove commas (thousand separators)
            # Keep digits, dots (decimals), dashes (negatives), parentheses (negatives)
            cleaned = re.sub(r'[^\d\.\-\(\)]', '', value_str.replace(',', '').strip())
            
            # Handle empty after cleaning
            if not cleaned or cleaned == '.':
                return None
            
            # Handle parentheses for negative numbers (e.g., "(100)" = -100)
            if '(' in cleaned and ')' in cleaned:
                cleaned = '-' + cleaned.replace('(', '').replace(')', '')
            
            # Handle multiple dashes (shouldn't happen, but be safe)
            if cleaned.count('-') > 1:
                cleaned = cleaned.replace('-', '', cleaned.count('-') - 1)
            
            try:
                result = float(cleaned)
                # ✅ DEBUG: Log if we're extracting a large number (might indicate parsing issue)
                if abs(result) > 1000000:
                    logger.debug(f"   Extracted large number: {value_str} → {result:,.2f}")
                return result
            except (ValueError, OverflowError) as e:
                logger.debug(f"   Failed to extract numeric from '{value_str}': {e}")
                return None
        
        return None
    
    def _group_by_section(self, line_items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group line items by financial section"""
        sections = {
            'operating_income': [],
            'cogs': [],
            'operating_expenses': [],
            'non_operating_income': [],
            'non_operating_expenses': [],
            'tax': [],
            'other': []
        }
        
        current_section = 'other'
        
        for item in line_items:
            account_name_lower = item['account_name'].lower().strip()
            account_name_original = item['account_name'].strip()
            
            # ✅ IMPROVED: Check for explicit section headers first (exact matches)
            section_found = False
            
            # Check for explicit section headers (usually capitalized, standalone)
            explicit_headers = {
                'operating_income': [
                    'operating income', 'revenue', 'sales revenue', 'sales', 'total operating income',
                    'revenue section', 'sales section', 'income section'
                ],
                'cogs': [
                    'cost of goods sold', 'cogs', 'cost of sales', 'cost of revenue', 'total cogs',
                    'cogs section', 'cost section', 'cost of goods sold section'
                ],
                'operating_expenses': [
                    'operating expenses', 'operating expense', 'opex', 'total operating expenses',
                    'operating expenses section', 'expenses section'
                ],
                'non_operating_income': [
                    'non-operating income', 'non operating income', 'other income',
                    'interest income', 'non-operating income section'
                ],
                'non_operating_expenses': [
                    'non-operating expenses', 'non operating expenses', 'other expenses',
                    'bank fees', 'foreign exchange', 'non-operating expenses section'
                ],
                'tax': [
                    'income tax', 'tax expense', 'taxation', 'tax', 'tax expense (30%)',
                    'tax section', 'income tax expense'
                ]
            }
            
            for section, headers in explicit_headers.items():
                for header in headers:
                    if account_name_lower == header or account_name_lower.startswith(header + ' '):
                        current_section = section
                        section_found = True
                        logger.info(f"📂 Section header detected: {section} (from '{account_name_original}')")
                        break
                if section_found:
                    break
            
            # ✅ If not an explicit header, check for COGS patterns (more specific)
            if not section_found:
                for keyword in self.section_keywords['cogs']:
                    if keyword in account_name_lower:
                        # Check for specific COGS patterns
                        if any(pattern in account_name_lower for pattern in ['purchases', 'parts', 'materials', 'labor', 'casuals', 'tools', 'equipment']):
                            current_section = 'cogs'
                            section_found = True
                            logger.debug(f"📂 Section detected: cogs (from '{account_name_original}')")
                            break
            
            # ✅ Then check for operating income items (sales, revenue, other income)
            # ✅ IMPORTANT: "Other Income" should be in operating_income (part of revenue), not non-operating
            if not section_found:
                for keyword in self.section_keywords['operating_income']:
                    if keyword in account_name_lower:
                        # Check if it's a revenue item (sales, revenue, other income, etc.)
                        # "Other Income" is part of operating revenue, not non-operating
                        if any(pattern in account_name_lower for pattern in ['sales', 'revenue', 'other income', 'other revenue', 'income']):
                            # But exclude if it's explicitly non-operating
                            if 'non-operating' not in account_name_lower and 'non operating' not in account_name_lower:
                                current_section = 'operating_income'
                                section_found = True
                                logger.debug(f"📂 Section detected: operating_income (from '{account_name_original}')")
                                break
            
            # ✅ Then check for operating expenses (salaries, rent, utilities, etc.)
            # ✅ CRITICAL: Operating expenses detection must be comprehensive
            if not section_found:
                # Check explicit keywords first (exact matches or contains)
                for keyword in self.section_keywords['operating_expenses']:
                    # Use both exact match and contains for better detection
                    if keyword in account_name_lower or account_name_lower == keyword:
                        # But exclude if it's clearly a total (we'll handle totals separately)
                        if 'total' not in account_name_lower or 'total operating expenses' in account_name_lower:
                            current_section = 'operating_expenses'
                            section_found = True
                            logger.info(f"📂 Section detected: operating_expenses (keyword: '{keyword}' from '{account_name_original}')")
                            break
                
                # ✅ Also check if it's an expense by common patterns (if not already found)
                if not section_found:
                    expense_patterns = ['expense', 'cost', 'fee', 'charge', 'payment', 'salary', 'wage', 'rent', 'utility', 
                                       'supplies', 'marketing', 'advertising', 'office', 'internet', 'communication',
                                       'transport', 'repairs', 'maintenance', 'insurance', 'licenses', 'permits',
                                       'miscellaneous', 'depreciation', 'amortization', 'administrative', 'selling',
                                       'general', 'overhead', 'professional', 'travel', 'accommodation', 'allowance',
                                       'delivery', 'postage', 'telephone', 'electricity', 'water', 'fuel', 'vehicle',
                                       'parking', 'meals', 'entertainment', 'printing', 'stationery', 'consultant',
                                       'credit card', 'bank fees', 'charges', 'fines', 'penalty', 'tendering',
                                       'clearing', 'forwarding', 'promotions', 'commissions', 'business licenses',
                                       'bad debt', 'employee bonuses', 'staff costs', 'staff uniforms', 'housing levy',
                                       'nita fee', 'nssf', 'statutory', 'internship allowance', 'merchant account',
                                       'computer', 'hardware', 'subscriptions']
                    matched_patterns = [p for p in expense_patterns if p in account_name_lower]
                    if matched_patterns:
                        # But exclude COGS and non-operating items
                        if 'cost of goods' not in account_name_lower and 'cogs' not in account_name_lower:
                            if 'non-operating' not in account_name_lower and 'non operating' not in account_name_lower:
                                # Interest expense can be operating or non-operating - check context
                                if 'interest' in account_name_lower:
                                    # If it says "interest expense" or "interest paid", it's likely non-operating
                                    if 'interest expense' in account_name_lower or 'interest paid' in account_name_lower:
                                        logger.debug(f"   ⏭️  Skipped '{account_name_original}' - interest expense (non-operating)")
                                    else:
                                        # Otherwise, treat as operating expense
                                        current_section = 'operating_expenses'
                                        section_found = True
                                        logger.info(f"📂 Section detected: operating_expenses (pattern: {matched_patterns} from '{account_name_original}')")
                                else:
                                    current_section = 'operating_expenses'
                                    section_found = True
                                    logger.info(f"📂 Section detected: operating_expenses (pattern: {matched_patterns} from '{account_name_original}')")
                            else:
                                logger.debug(f"   ⏭️  Skipped '{account_name_original}' - non-operating")
                        else:
                            logger.debug(f"   ⏭️  Skipped '{account_name_original}' - COGS item")
                    else:
                        logger.debug(f"   ⏭️  '{account_name_original}' - no expense pattern match")
            
            # ✅ Then check for non-operating items
            if not section_found:
                for keyword in self.section_keywords['non_operating_income']:
                    if keyword in account_name_lower:
                        current_section = 'non_operating_income'
                        section_found = True
                        logger.debug(f"📂 Section detected: non_operating_income (from '{account_name_original}')")
                        break
                
                for keyword in self.section_keywords['non_operating_expenses']:
                    if keyword in account_name_lower:
                        current_section = 'non_operating_expenses'
                        section_found = True
                        logger.debug(f"📂 Section detected: non_operating_expenses (from '{account_name_original}')")
                        break
            
            # ✅ Check for tax items
            if not section_found:
                for keyword in self.section_keywords['tax']:
                    if keyword in account_name_lower:
                        current_section = 'tax'
                        section_found = True
                        logger.debug(f"📂 Section detected: tax (from '{account_name_original}')")
                        break
            
            # Add item to current section
            sections[current_section].append(item)
        
        # ✅ DETAILED LOGGING: Log all sections and their items
        logger.info("="*80)
        logger.info("📊 SECTION GROUPING RESULTS")
        logger.info("="*80)
        for section, items in sections.items():
            if items:
                logger.info(f"\n📂 Section '{section}': {len(items)} line items")
                total_section = sum(abs(item['amount']) for item in items)
                logger.info(f"   Total (sum of items): {total_section:,.2f}")
                # Log ALL items in operating_expenses section for debugging
                if section == 'operating_expenses':
                    logger.info(f"   🔍 ALL OPERATING EXPENSE ITEMS:")
                    for i, item in enumerate(items, 1):
                        logger.info(f"      {i}. '{item['account_name']}' (Row {item['row']}) = {item['amount']:,.2f}")
                else:
                    # Log first 5 items for other sections
                    for i, item in enumerate(items[:5], 1):
                        logger.info(f"      {i}. '{item['account_name']}' (Row {item['row']}) = {item['amount']:,.2f}")
                    if len(items) > 5:
                        logger.info(f"      ... and {len(items) - 5} more items")
        logger.info("="*80)
        
        return sections
    
    def _calculate_section_totals(self, sections: Dict[str, List[Dict[str, Any]]]) -> Dict[str, float]:
        """Calculate totals by summing line items in each section, or use explicit totals if available"""
        totals = {
            'operating_income_total': 0.0,
            'cogs_total': 0.0,
            'operating_expenses_total': 0.0,
            'non_operating_income_total': 0.0,
            'non_operating_expense_total': 0.0,
            'tax_total': 0.0
        }
        
        # ✅ IMPROVED: Check for explicit totals first (e.g., "Total Operating Income", "Total COGS")
        # These are more reliable than summing line items
        explicit_totals = {}
        for section_name, items in sections.items():
            for item in items:
                account_lower = item['account_name'].lower()
                # Check for explicit total rows
                if 'total operating income' in account_lower or account_lower == 'total operating income':
                    explicit_totals['operating_income'] = item['amount']
                    logger.info(f"✅ Found explicit Total Operating Income: {item['amount']:,.2f}")
                elif 'total cogs' in account_lower or 'total cost of goods' in account_lower:
                    explicit_totals['cogs'] = abs(item['amount'])
                    logger.info(f"✅ Found explicit Total COGS: {item['amount']:,.2f}")
                elif 'total operating expenses' in account_lower or account_lower == 'total operating expenses':
                    explicit_totals['operating_expenses'] = abs(item['amount'])
                    logger.info(f"✅ Found explicit Total Operating Expenses: {item['amount']:,.2f}")
                elif 'gross profit' in account_lower:
                    explicit_totals['gross_profit'] = item['amount']
                    logger.info(f"✅ Found explicit Gross Profit: {item['amount']:,.2f}")
                elif 'operating profit' in account_lower or 'operating income' in account_lower:
                    if 'total' not in account_lower:  # Don't double-count
                        explicit_totals['operating_profit'] = item['amount']
                        logger.info(f"✅ Found explicit Operating Profit: {item['amount']:,.2f}")
        
        # Sum operating income (usually positive)
        # ✅ Include ALL operating income items: Sales, Revenue, Other Income, etc.
        # But exclude explicit totals (they'll be used instead)
        operating_income_items = []
        for item in sections['operating_income']:
            account_lower = item['account_name'].lower()
            # Skip explicit totals (we'll use them separately)
            if 'total operating income' not in account_lower:
                operating_income_items.append(item)
                amount = item['amount']
                totals['operating_income_total'] += amount
                logger.debug(f"   Operating Income item: {item['account_name']} = {amount:,.2f}")
        
        # ✅ Use explicit total if available, otherwise use sum
        if 'operating_income' in explicit_totals:
            totals['operating_income_total'] = explicit_totals['operating_income']
            logger.info(f"✅ Using explicit Total Operating Income: {totals['operating_income_total']:,.2f} (instead of sum: {sum(item['amount'] for item in operating_income_items):,.2f})")
        
        # Sum COGS (usually positive, represents costs)
        # But exclude explicit totals
        cogs_items = []
        for item in sections['cogs']:
            account_lower = item['account_name'].lower()
            # Skip explicit totals
            if 'total cogs' not in account_lower and 'total cost' not in account_lower:
                cogs_items.append(item)
                # COGS is always positive (costs), but handle negative values gracefully
                totals['cogs_total'] += abs(item['amount'])
        
        # ✅ Use explicit total if available
        if 'cogs' in explicit_totals:
            totals['cogs_total'] = explicit_totals['cogs']
            logger.info(f"✅ Using explicit Total COGS: {totals['cogs_total']:,.2f} (instead of sum: {sum(abs(item['amount']) for item in cogs_items):,.2f})")
        
        # Sum operating expenses (usually positive, represents costs)
        # ✅ CRITICAL: Operating expenses must be summed correctly
        logger.info("\n" + "="*80)
        logger.info("💰 CALCULATING OPERATING EXPENSES TOTAL")
        logger.info("="*80)
        logger.info(f"📊 Found {len(sections['operating_expenses'])} items in operating_expenses section")
        
        # ✅ CRITICAL DEBUG: Log ALL items in operating_expenses section to see what we have
        if len(sections['operating_expenses']) > 0:
            logger.info("🔍 ALL ITEMS IN OPERATING_EXPENSES SECTION:")
            for i, item in enumerate(sections['operating_expenses'], 1):
                logger.info(f"   {i}. Row {item['row']}: '{item['account_name']}' = {item['amount']:,.2f}")
        else:
            logger.error("❌ CRITICAL: operating_expenses section is EMPTY!")
            logger.error("   This means section grouping failed to categorize expense items")
            # Try to find where expense items went
            logger.error("   Checking other sections for expense items...")
            for section_name, items in sections.items():
                if section_name != 'operating_expenses' and len(items) > 0:
                    expense_keywords = ['salary', 'wage', 'rent', 'utility', 'marketing', 'office', 'supplies', 'expense', 'fee', 'charge']
                    expense_items = [item for item in items if any(kw in item['account_name'].lower() for kw in expense_keywords)]
                    if expense_items:
                        logger.error(f"   ⚠️  Found {len(expense_items)} potential expense items in '{section_name}' section:")
                        for item in expense_items[:5]:
                            logger.error(f"      - '{item['account_name']}' = {item['amount']:,.2f}")
        
        # Check for explicit total first
        operating_expense_items = []
        for item in sections['operating_expenses']:
            account_lower = item['account_name'].lower()
            # Skip explicit totals (we'll use them separately)
            if 'total operating expenses' not in account_lower:
                operating_expense_items.append(item)
        
        if len(operating_expense_items) == 0 and 'operating_expenses' not in explicit_totals:
            logger.error("❌ NO ITEMS FOUND IN OPERATING_EXPENSES SECTION!")
            logger.error("   This means the section detection logic did not categorize any items as operating expenses")
            logger.error(f"   Total items in section: {len(sections['operating_expenses'])}")
            logger.error(f"   Items after filtering totals: {len(operating_expense_items)}")
        else:
            logger.info("🔍 Summing operating expense items:")
            running_total = 0.0
            for i, item in enumerate(operating_expense_items, 1):
                amount = item['amount']
                # Handle both positive and negative amounts (expenses are usually positive)
                expense_amount = abs(amount) if amount < 0 else amount
                running_total += expense_amount
                totals['operating_expenses_total'] += expense_amount
                logger.info(f"   {i}. '{item['account_name']}' (Row {item['row']}): {amount:,.2f} → {expense_amount:,.2f} | Running Total: {running_total:,.2f}")
            
            logger.info(f"\n✅ Calculated Operating Expenses Total (sum): {totals['operating_expenses_total']:,.2f}")
        
        # ✅ Use explicit total if available
        if 'operating_expenses' in explicit_totals:
            totals['operating_expenses_total'] = explicit_totals['operating_expenses']
            sum_total = sum(abs(item['amount']) if item['amount'] < 0 else item['amount'] for item in operating_expense_items)
            logger.info(f"✅ Using explicit Total Operating Expenses: {totals['operating_expenses_total']:,.2f} (instead of sum: {sum_total:,.2f})")
        
        # ✅ VALIDATION: If operating expenses is 0 but we have gross profit and operating income,
        # calculate it from the difference
        if totals['operating_expenses_total'] == 0.0:
            gross_profit = totals['operating_income_total'] - totals['cogs_total']
            logger.warning(f"\n⚠️⚠️⚠️ OPERATING EXPENSES IS ZERO! ⚠️⚠️⚠️")
            logger.warning(f"   Operating Expenses Total: {totals['operating_expenses_total']:,.2f}")
            logger.warning(f"   Items in operating_expenses section: {len(sections['operating_expenses'])}")
            logger.warning(f"   Gross Profit: {gross_profit:,.2f}")
            
            if len(sections['operating_expenses']) > 0:
                # Re-sum with better logic
                logger.warning(f"   Attempting to re-calculate from {len(sections['operating_expenses'])} items...")
                recalc_total = sum(abs(item['amount']) for item in sections['operating_expenses'])
                logger.info(f"✅ Re-calculated Operating Expenses: {recalc_total:,.2f}")
                totals['operating_expenses_total'] = recalc_total
            else:
                logger.error(f"❌ NO ITEMS IN OPERATING_EXPENSES SECTION - Section detection failed!")
                logger.error(f"   Check the section grouping logic above to see where expense items went")
        
        logger.info("="*80 + "\n")
        
        # Sum non-operating income (can be positive or negative)
        for item in sections['non_operating_income']:
            totals['non_operating_income_total'] += item['amount']
        
        # Sum non-operating expenses (usually positive)
        for item in sections['non_operating_expenses']:
            totals['non_operating_expense_total'] += abs(item['amount'])
        
        # Sum tax (usually positive)
        for item in sections['tax']:
            totals['tax_total'] += abs(item['amount'])
        
        logger.info(f"📊 Section Totals:")
        logger.info(f"   Operating Income: {totals['operating_income_total']:,.2f} ({len(sections['operating_income'])} items)")
        logger.info(f"   COGS: {totals['cogs_total']:,.2f} ({len(sections['cogs'])} items)")
        logger.info(f"   Operating Expenses: {totals['operating_expenses_total']:,.2f} ({len(sections['operating_expenses'])} items)")
        
        # ✅ VALIDATION: Check if operating expenses should be calculated from gross profit and operating income
        gross_profit_calc = totals['operating_income_total'] - totals['cogs_total']
        if totals['operating_expenses_total'] == 0.0 and gross_profit_calc > 0:
            # Try to infer from derived metrics if available
            logger.warning(f"⚠️ Operating Expenses is 0, but Gross Profit = {gross_profit_calc:,.2f}")
            logger.warning(f"   This suggests operating expenses items may not have been detected correctly")
            logger.warning(f"   Found {len(sections['operating_expenses'])} items in operating_expenses section")
            if len(sections['operating_expenses']) > 0:
                logger.warning(f"   Items in section: {[item['account_name'] for item in sections['operating_expenses'][:5]]}")
        
        logger.info(f"   Non-Operating Income: {totals['non_operating_income_total']:,.2f}")
        logger.info(f"   Non-Operating Expenses: {totals['non_operating_expense_total']:,.2f}")
        logger.info(f"   Tax: {totals['tax_total']:,.2f}")
        
        return totals
    
    def _calculate_derived_metrics(self, totals: Dict[str, float]) -> Dict[str, float]:
        """Calculate derived financial metrics"""
        operating_income = totals['operating_income_total']
        cogs = totals['cogs_total']
        operating_expenses = totals['operating_expenses_total']
        non_op_income = totals['non_operating_income_total']
        non_op_expenses = totals['non_operating_expense_total']
        tax = totals['tax_total']
        
        # Gross Profit = Operating Income - COGS
        gross_profit = operating_income - cogs
        
        # ✅ VALIDATION: If operating expenses is 0 but we can calculate it from gross profit and operating profit
        # This is a fallback to ensure we have the correct operating expenses
        if operating_expenses == 0.0 and gross_profit > 0:
            # We can't calculate it here without operating profit, but we'll log a warning
            logger.warning(f"⚠️ Operating Expenses is 0.0, but Gross Profit = {gross_profit:,.2f}")
            logger.warning(f"   Operating Expenses should be calculated from line items, not derived")
        
        # Operating Profit = Gross Profit - Operating Expenses
        operating_profit = gross_profit - operating_expenses
        
        # Profit before tax = Operating Profit + Non-Operating Income - Non-Operating Expenses
        profit_before_tax = operating_profit + non_op_income - non_op_expenses
        
        # ✅ CRITICAL: Net Profit = Profit before tax - Tax
        # If tax is not provided but we have profit before tax, calculate tax at 30% (Kenya corporate tax rate)
        if tax == 0.0 and profit_before_tax > 0:
            # Calculate tax at 30% if not provided
            calculated_tax = profit_before_tax * 0.30
            logger.info(f"💰 Tax not provided, calculating at 30%: {calculated_tax:,.2f}")
            tax = calculated_tax
        
        net_profit = profit_before_tax - tax
        
        logger.info(f"📊 Derived Metrics Calculation:")
        logger.info(f"   Gross Profit: {gross_profit:,.2f}")
        logger.info(f"   Operating Profit: {operating_profit:,.2f}")
        logger.info(f"   Profit Before Tax: {profit_before_tax:,.2f}")
        logger.info(f"   Tax: {tax:,.2f}")
        logger.info(f"   Net Profit (After Tax): {net_profit:,.2f}")
        
        derived = {
            'gross_profit': gross_profit,
            'operating_profit': operating_profit,
            'profit_before_tax': profit_before_tax,
            'net_profit': net_profit
        }
        
        logger.info(f"📊 Derived Metrics:")
        logger.info(f"   Gross Profit: {gross_profit:,.2f}")
        logger.info(f"   Operating Profit: {operating_profit:,.2f}")
        logger.info(f"   Profit Before Tax: {profit_before_tax:,.2f}")
        logger.info(f"   Net Profit: {net_profit:,.2f}")
        
        return derived
    
    def _create_output_structure(self, totals: Dict[str, float], derived: Dict[str, float],
                                 line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create the final output structure"""
        # Flatten line items for output
        output_line_items = []
        for item in line_items:
            output_line_items.append({
                'account_name': item['account_name'],
                'amount': item['amount'],
                'row': item['row']
            })
        
        return {
            'operating_income_total': totals['operating_income_total'],
            'cogs_total': totals['cogs_total'],
            'gross_profit': derived['gross_profit'],
            'operating_expenses_total': totals['operating_expenses_total'],
            'operating_profit': derived['operating_profit'],
            'non_operating_income_total': totals['non_operating_income_total'],
            'non_operating_expense_total': totals['non_operating_expense_total'],
            'net_profit': derived['net_profit'],
            'line_items': output_line_items
        }
    
    def _create_model_json(self, normalized_data: Dict[str, float]) -> Dict[str, Any]:
        """Create JSON structure for model input"""
        # ✅ FIXED: Map section-based structure to model format correctly
        # Use the output structure values, not normalized_data (which may have been modified)
        # Get from the output structure that was passed to normalization
        
        # ✅ DETAILED LOGGING: Log what's being passed to the model
        logger.info("\n" + "="*80)
        logger.info("🤖 CREATING JSON DATA FOR MODEL INPUT")
        logger.info("="*80)
        logger.info("📊 Source Data (from normalized_data):")
        logger.info(f"   operating_income_total: {normalized_data.get('operating_income_total', 0.0):,.2f}")
        logger.info(f"   cogs_total: {normalized_data.get('cogs_total', 0.0):,.2f}")
        logger.info(f"   gross_profit: {normalized_data.get('gross_profit', 0.0):,.2f}")
        logger.info(f"   operating_expenses_total: {normalized_data.get('operating_expenses_total', 0.0):,.2f} ⚠️")
        logger.info(f"   operating_profit: {normalized_data.get('operating_profit', 0.0):,.2f}")
        logger.info(f"   net_profit: {normalized_data.get('net_profit', 0.0):,.2f}")
        logger.info(f"   non_operating_income_total: {normalized_data.get('non_operating_income_total', 0.0):,.2f}")
        logger.info(f"   non_operating_expense_total: {normalized_data.get('non_operating_expense_total', 0.0):,.2f}")
        logger.info(f"   tax_total: {normalized_data.get('tax_total', 0.0):,.2f}")
        
        json_data = {
            'totalRevenue': normalized_data.get('operating_income_total', 0.0),
            'costOfRevenue': normalized_data.get('cogs_total', 0.0),
            'grossProfit': normalized_data.get('gross_profit', 0.0),
            'totalOperatingExpenses': normalized_data.get('operating_expenses_total', 0.0),
            'operatingIncome': normalized_data.get('operating_profit', 0.0),  # operating_profit is the derived metric
            'netIncome': normalized_data.get('net_profit', 0.0),
            'interestIncome': normalized_data.get('non_operating_income_total', 0.0),
            'interestExpense': normalized_data.get('non_operating_expense_total', 0.0),
            'incomeTaxExpense': normalized_data.get('tax_total', 0.0),
            'researchDevelopment': 0.0,  # Default if not found
        }
        
        logger.info("\n📦 Final JSON Data (being sent to model):")
        for key, value in json_data.items():
            marker = " ⚠️⚠️⚠️" if key == 'totalOperatingExpenses' and value == 0.0 else ""
            logger.info(f"   {key}: {value:,.2f}{marker}")
        
        if json_data['totalOperatingExpenses'] == 0.0:
            logger.error("\n❌❌❌ CRITICAL: totalOperatingExpenses is 0.0 in JSON data! ❌❌❌")
            logger.error("   This will cause incorrect calculations in the model!")
            logger.error("   Check the section detection and summing logic above.")
        
        logger.info("="*80 + "\n")
        
        return json_data
    
    def _log_to_database(self, line_items: List[Dict], sections: Dict, totals: Dict,
                         derived: Dict, output: Dict, json_data: Dict,
                         corporate, user, upload_record, sheet_name: str):
        """Log extraction data to database"""
        try:
            TransactionLogBase.log(
                transaction_type="TAZAMA_SECTION_EXTRACTION",
                user=user,
                message=f"Section-based extraction completed for sheet: {sheet_name}",
                state_name="Success",
                extra={
                    'sheet_name': sheet_name,
                    'total_line_items': len(line_items),
                    'sections': {k: len(v) for k, v in sections.items()},
                    'totals': totals,
                    'derived_metrics': derived,
                    'upload_record_id': upload_record.id if upload_record else None,
                }
            )
            
            TransactionLogBase.log(
                transaction_type="TAZAMA_SECTION_JSON",
                user=user,
                message="JSON data structure created for model input",
                state_name="Success",
                extra={
                    'json_data': json_data,
                    'sheet_name': sheet_name,
                    'upload_record_id': upload_record.id if upload_record else None,
                }
            )
            
            logger.info("✅ Section-based extraction logged to database")
            
        except Exception as e:
            logger.error(f"Error logging to database: {e}", exc_info=True)
    
    def _print_to_terminal(self, line_items: List[Dict], sections: Dict, totals: Dict,
                          derived: Dict, output: Dict, json_data: Dict):
        """Print extraction data to terminal"""
        import json
        
        print("\n" + "="*80)
        print("📊 SECTION-BASED EXTRACTION RESULTS")
        print("="*80)
        
        print(f"\n✅ Total Line Items Parsed: {len(line_items)}")
        print(f"   (Placeholder 'Total for' rows ignored)")
        
        print("\n📂 SECTIONS:")
        print("-" * 80)
        for section, items in sections.items():
            if items:
                print(f"   {section:25s}: {len(items):3d} line items")
        
        print("\n💰 SECTION TOTALS (Summed from Line Items):")
        print("-" * 80)
        print(f"   Operating Income Total    : {totals['operating_income_total']:>15,.2f}")
        print(f"   COGS Total                : {totals['cogs_total']:>15,.2f}")
        print(f"   Operating Expenses Total  : {totals['operating_expenses_total']:>15,.2f}")
        print(f"   Non-Operating Income      : {totals['non_operating_income_total']:>15,.2f}")
        print(f"   Non-Operating Expenses    : {totals['non_operating_expense_total']:>15,.2f}")
        print(f"   Tax Total                 : {totals['tax_total']:>15,.2f}")
        
        print("\n📈 DERIVED METRICS:")
        print("-" * 80)
        print(f"   Gross Profit              : {derived['gross_profit']:>15,.2f}")
        print(f"   Operating Profit          : {derived['operating_profit']:>15,.2f}")
        print(f"   Profit Before Tax         : {derived['profit_before_tax']:>15,.2f}")
        print(f"   Net Profit                : {derived['net_profit']:>15,.2f}")
        
        print("\n📦 OUTPUT STRUCTURE:")
        print("-" * 80)
        print(json.dumps(output, indent=2, default=str))
        
        print("\n🤖 JSON DATA (For Model Input):")
        print("-" * 80)
        print(json.dumps(json_data, indent=2))
        
        print("\n" + "="*80 + "\n")

