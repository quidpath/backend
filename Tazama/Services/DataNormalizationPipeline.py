# DataNormalizationPipeline.py - Dynamic Data Normalization and Calculation Pipeline
"""
Dynamic data normalization pipeline that:
1. Detects and normalizes various Excel/CSV structures
2. Calculates missing/zero values using financial formulas
3. Validates and corrects data integrity
4. Handles different data formats and structures
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import logging
from decimal import Decimal, InvalidOperation
import re

logger = logging.getLogger(__name__)


class DataNormalizationPipeline:
    """Dynamic pipeline for normalizing and calculating financial data"""
    
    def __init__(self):
        self.calculation_order = [
            'total_revenue',
            'cost_of_revenue', 
            'gross_profit',
            'total_operating_expenses',
            'operating_income',
            'other_income',
            'other_expenses',
            'net_income_before_tax',
            'income_tax_expense',
            'net_income'
        ]
        
    def normalize_and_calculate(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Main entry point: Normalize raw data and calculate all missing values
        
        Args:
            raw_data: Raw financial data from Excel/CSV upload
            
        Returns:
            Normalized and calculated financial data with all fields populated
        """
        try:
            # Step 1: Detect and normalize data structure
            normalized = self._detect_and_normalize_structure(raw_data)
            
            # Step 2: Extract and clean numeric values
            cleaned = self._extract_and_clean_values(normalized)
            
            # Step 3: Calculate all derived fields
            calculated = self._calculate_derived_fields(cleaned)
            
            # Step 4: Validate and correct data integrity
            validated = self._validate_and_correct(calculated)
            
            # Step 5: Final normalization
            final = self._final_normalization(validated)
            
            logger.info(f"✅ Data normalization complete. Revenue: {final.get('total_revenue', 0):,.0f}, "
                       f"Net Income: {final.get('net_income', 0):,.0f}")
            
            return final
            
        except Exception as e:
            logger.error(f"Error in data normalization pipeline: {e}", exc_info=True)
            return self._get_default_structure()
    
    def _detect_and_normalize_structure(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect the structure of the data and normalize it"""
        normalized = {}
        
        # Handle DataFrame structures (from Excel/CSV)
        if isinstance(raw_data, dict):
            # Check for common Excel structures
            for key, value in raw_data.items():
                if isinstance(value, pd.DataFrame):
                    # Process DataFrame
                    df_normalized = self._normalize_dataframe(value)
                    normalized.update(df_normalized)
                elif isinstance(value, (list, dict)):
                    # Process structured data
                    normalized.update(self._normalize_structured_data(value))
                else:
                    normalized[key] = value
        
        # Handle direct dictionary with financial fields
        if not normalized:
            normalized = raw_data.copy() if isinstance(raw_data, dict) else {}
        
        return normalized
    
    def _normalize_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Normalize DataFrame structure to standard format"""
        normalized = {}
        
        # Detect structure type
        cols_lower = {str(c).lower(): c for c in df.columns}
        
        # Structure 1: Section/Item/Amount format (like the image)
        if any('section' in k or 'category' in k for k in cols_lower.keys()):
            if any('item' in k or 'description' in k for k in cols_lower.keys()):
                if any('amount' in k or 'kes' in k or 'value' in k for k in cols_lower.keys()):
                    return self._normalize_section_item_amount(df, cols_lower)
        
        # Structure 2: Direct field mapping
        field_mappings = {
            'total revenue': 'total_revenue',
            'revenue': 'total_revenue',
            'sales revenue': 'sales_revenue',
            'service revenue': 'service_revenue',
            'other operating income': 'other_operating_income',
            'cost of goods sold': 'cost_of_revenue',
            'cost of sales': 'cost_of_revenue',
            'cogs': 'cost_of_revenue',
            'purchases': 'purchases',
            'direct labor': 'direct_labor',
            'equipment depreciation': 'equipment_depreciation',
            'gross profit': 'gross_profit',
            'operating expenses': 'total_operating_expenses',
            'salaries & wages': 'salaries_wages',
            'rent expense': 'rent_expense',
            'utilities': 'utilities',
            'marketing': 'marketing',
            'office supplies': 'office_supplies',
            'internet & communication': 'internet_communication',
            'transport': 'transport',
            'repairs & maintenance': 'repairs_maintenance',
            'insurance': 'insurance',
            'licenses & permits': 'licenses_permits',
            'miscellaneous expenses': 'miscellaneous_expenses',
            'operating income': 'operating_income',
            'operating profit': 'operating_income',
            'interest income': 'interest_income',
            'interest expense': 'interest_expense',
            'gain/(loss) on asset sale': 'gain_loss_asset_sale',
            'net income before tax': 'net_income_before_tax',
            'income tax expense': 'income_tax_expense',
            'net income after tax': 'net_income',
            'net income': 'net_income'
        }
        
        # Try to map columns directly
        for col_lower, field_name in field_mappings.items():
            matching_col = next((orig for k, orig in cols_lower.items() if col_lower in k), None)
            if matching_col:
                values = df[matching_col].dropna()
                if len(values) > 0:
                    # Sum if multiple rows, take first if single
                    value = float(values.sum()) if len(values) > 1 else float(values.iloc[0])
                    normalized[field_name] = value
        
        return normalized
    
    def _normalize_section_item_amount(self, df: pd.DataFrame, cols_lower: Dict[str, str]) -> Dict[str, Any]:
        """Normalize Section/Item/Amount structure (like the image)"""
        normalized = {}
        
        # Find columns
        section_col = next((orig for k, orig in cols_lower.items() if 'section' in k or 'category' in k), None)
        item_col = next((orig for k, orig in cols_lower.items() if 'item' in k or 'description' in k), None)
        amount_col = next((orig for k, orig in cols_lower.items() if 'amount' in k or 'kes' in k or 'value' in k), None)
        
        if not section_col or not amount_col:
            return normalized
        
        # Process data
        w = df[[section_col, amount_col]].copy()
        if item_col:
            w[item_col] = df[item_col]
        w.columns = ['section', 'amount'] + (['item'] if item_col else [])
        
        # Clean amounts
        def to_float(x):
            try:
                if pd.isna(x):
                    return 0.0
                if isinstance(x, str):
                    y = x.replace(',', '').replace('KES', '').replace('$', '').strip()
                    if '(' in y and ')' in y:
                        y = '-' + y.replace('(', '').replace(')', '')
                    return float(y)
                return float(x)
            except:
                return 0.0
        
        w['amount'] = w['amount'].apply(to_float)
        w['section_norm'] = w['section'].astype(str).str.lower().str.strip()
        
        # Aggregate by section
        sections = {
            'revenue': ['revenue', 'sales', 'income'],
            'cost_of_revenue': ['cost of goods sold', 'cost of sales', 'cogs', 'cost'],
            'operating_expenses': ['operating expenses', 'operating expense', 'expenses'],
            'other_income': ['other income', 'interest income'],
            'other_expenses': ['other expenses', 'interest expense'],
            'gross_profit': ['gross profit'],
            'operating_income': ['operating income', 'operating profit'],
            'net_income_before_tax': ['net income before tax', 'income before tax'],
            'income_tax_expense': ['income tax', 'tax expense', 'tax'],
            'net_income': ['net income after tax', 'net income', 'profit after tax']
        }
        
        for field, keywords in sections.items():
            mask = w['section_norm'].str.contains('|'.join(keywords), case=False, na=False)
            # Exclude "Total" rows to avoid double counting
            mask = mask & ~w['section_norm'].str.contains('total', case=False, na=False)
            value = float(w.loc[mask, 'amount'].sum())
            
            # Also check for explicit "Total" rows
            total_mask = w['section_norm'].str.contains('total', case=False, na=False)
            for keyword in keywords:
                if total_mask.any() and keyword in w['section_norm'].str.lower().str:
                    total_row_mask = total_mask & w['section_norm'].str.contains(keyword, case=False, na=False)
                    if total_row_mask.any():
                        total_value = float(w.loc[total_row_mask, 'amount'].sum())
                        if total_value > 0:
                            value = total_value
                            break
            
            if value > 0:
                normalized[field] = value
        
        # Extract individual expense items
        expense_items = {
            'salaries_wages': ['salaries', 'wages'],
            'rent_expense': ['rent'],
            'utilities': ['utilities', 'electricity', 'water'],
            'marketing': ['marketing'],
            'office_supplies': ['office supplies', 'supplies'],
            'internet_communication': ['internet', 'communication'],
            'transport': ['transport'],
            'repairs_maintenance': ['repairs', 'maintenance'],
            'insurance': ['insurance'],
            'licenses_permits': ['licenses', 'permits'],
            'miscellaneous_expenses': ['miscellaneous']
        }
        
        for field, keywords in expense_items.items():
            mask = w['section_norm'].str.contains('|'.join(keywords), case=False, na=False)
            value = float(w.loc[mask, 'amount'].sum())
            if value > 0:
                normalized[field] = value
        
        return normalized
    
    def _normalize_structured_data(self, data: Any) -> Dict[str, Any]:
        """Normalize structured data (list of dicts, etc.)"""
        normalized = {}
        
        if isinstance(data, list):
            # Sum all items in list
            for item in data:
                if isinstance(item, dict):
                    for key, value in item.items():
                        if key not in normalized:
                            normalized[key] = 0.0
                        try:
                            normalized[key] += float(value or 0)
                        except:
                            pass
        
        return normalized
    
    def _extract_and_clean_values(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract and clean numeric values from normalized data"""
        cleaned = {}
        
        # Standard field names
        field_mappings = {
            'total_revenue': ['total_revenue', 'revenue', 'total revenue', 'sales revenue'],
            'sales_revenue': ['sales_revenue', 'sales revenue'],
            'service_revenue': ['service_revenue', 'service revenue'],
            'other_operating_income': ['other_operating_income', 'other operating income'],
            'cost_of_revenue': ['cost_of_revenue', 'cost of revenue', 'cost of goods sold', 'cogs', 'cost_of_goods_sold'],
            'gross_profit': ['gross_profit', 'gross profit'],
            'total_operating_expenses': ['total_operating_expenses', 'operating_expenses', 'operating expenses', 'total operating expenses'],
            'operating_income': ['operating_income', 'operating income', 'operating profit'],
            'interest_income': ['interest_income', 'interest income'],
            'interest_expense': ['interest_expense', 'interest expense'],
            'other_income': ['other_income', 'other income'],
            'other_expenses': ['other_expenses', 'other expenses'],
            'net_income_before_tax': ['net_income_before_tax', 'net income before tax', 'income before tax'],
            'income_tax_expense': ['income_tax_expense', 'income tax', 'tax expense', 'tax'],
            'net_income': ['net_income', 'net income', 'net income after tax', 'profit after tax']
        }
        
        # Extract values with fuzzy matching
        for standard_field, variations in field_mappings.items():
            value = None
            for var in variations:
                # Direct match
                if var in data:
                    value = data[var]
                    break
                # Case-insensitive match
                for key in data.keys():
                    if str(key).lower() == var.lower():
                        value = data[key]
                        break
                if value is not None:
                    break
            
            if value is not None:
                cleaned[standard_field] = self._clean_numeric_value(value)
            else:
                cleaned[standard_field] = 0.0
        
        # Sum revenue components if total is missing
        if cleaned['total_revenue'] == 0:
            revenue_sum = (
                cleaned.get('sales_revenue', 0) +
                cleaned.get('service_revenue', 0) +
                cleaned.get('other_operating_income', 0)
            )
            if revenue_sum > 0:
                cleaned['total_revenue'] = revenue_sum
        
        # Sum cost components if total is missing
        if cleaned['cost_of_revenue'] == 0:
            # Try to get from individual cost items
            cost_items = ['purchases', 'direct_labor', 'equipment_depreciation']
            cost_sum = sum(cleaned.get(item, 0) for item in cost_items)
            if cost_sum > 0:
                cleaned['cost_of_revenue'] = cost_sum
        
        # Sum operating expenses if total is missing
        if cleaned['total_operating_expenses'] == 0:
            expense_items = [
                'salaries_wages', 'rent_expense', 'utilities', 'marketing',
                'office_supplies', 'internet_communication', 'transport',
                'repairs_maintenance', 'insurance', 'licenses_permits',
                'miscellaneous_expenses'
            ]
            expense_sum = sum(cleaned.get(item, 0) for item in expense_items)
            if expense_sum > 0:
                cleaned['total_operating_expenses'] = expense_sum
        
        return cleaned
    
    def _clean_numeric_value(self, value: Any) -> float:
        """Clean and convert value to float"""
        if value is None:
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove currency symbols, commas, spaces
            cleaned = value.replace(',', '').replace('$', '').replace('€', '').replace('£', '').replace('KES', '').strip()
            # Handle parentheses for negative numbers
            if '(' in cleaned and ')' in cleaned:
                cleaned = '-' + cleaned.replace('(', '').replace(')', '')
            # Remove any remaining non-numeric characters except minus and decimal
            cleaned = re.sub(r'[^\d\.\-]', '', cleaned)
            try:
                return float(cleaned) if cleaned else 0.0
            except:
                return 0.0
        
        try:
            return float(value)
        except:
            return 0.0
    
    def _calculate_derived_fields(self, data: Dict[str, float]) -> Dict[str, float]:
        """Calculate all derived fields using financial formulas"""
        calculated = data.copy()
        
        # Formula 1: Gross Profit = Total Revenue - Cost of Revenue
        if calculated['gross_profit'] == 0 and calculated['total_revenue'] > 0:
            if calculated['cost_of_revenue'] > 0:
                calculated['gross_profit'] = calculated['total_revenue'] - calculated['cost_of_revenue']
                logger.info(f"✅ Calculated Gross Profit: {calculated['total_revenue']:,.0f} - {calculated['cost_of_revenue']:,.0f} = {calculated['gross_profit']:,.0f}")
            else:
                # If cost is missing, estimate (typically 20-40% of revenue)
                estimated_cost = calculated['total_revenue'] * 0.30
                calculated['cost_of_revenue'] = estimated_cost
                calculated['gross_profit'] = calculated['total_revenue'] - estimated_cost
                logger.info(f"⚠️ Estimated Cost of Revenue: {estimated_cost:,.0f} (30% of revenue)")
        
        # Formula 2: Operating Income = Gross Profit - Operating Expenses
        if calculated['operating_income'] == 0 and calculated['gross_profit'] > 0:
            if calculated['total_operating_expenses'] > 0:
                calculated['operating_income'] = calculated['gross_profit'] - calculated['total_operating_expenses']
                logger.info(f"✅ Calculated Operating Income: {calculated['gross_profit']:,.0f} - {calculated['total_operating_expenses']:,.0f} = {calculated['operating_income']:,.0f}")
            else:
                # Calculate expenses from operating income if we have it
                # This shouldn't happen if we have gross profit, but handle it
                pass
        
        # Formula 3: Operating Expenses = Gross Profit - Operating Income (if expenses missing)
        if calculated['total_operating_expenses'] == 0 and calculated['gross_profit'] > 0:
            if calculated['operating_income'] > 0:
                calculated['total_operating_expenses'] = calculated['gross_profit'] - calculated['operating_income']
                logger.info(f"✅ Calculated Operating Expenses: {calculated['gross_profit']:,.0f} - {calculated['operating_income']:,.0f} = {calculated['total_operating_expenses']:,.0f}")
            elif calculated['gross_profit'] > 0:
                # Estimate expenses (typically 30-40% of revenue)
                estimated_expenses = calculated['total_revenue'] * 0.35
                if estimated_expenses < calculated['gross_profit']:
                    calculated['total_operating_expenses'] = estimated_expenses
                    calculated['operating_income'] = calculated['gross_profit'] - estimated_expenses
                    logger.info(f"⚠️ Estimated Operating Expenses: {estimated_expenses:,.0f} (35% of revenue)")
        
        # Formula 4: Net Income Before Tax = Operating Income + Other Income - Other Expenses
        if calculated['net_income_before_tax'] == 0:
            other_income = calculated.get('interest_income', 0) + calculated.get('other_income', 0)
            other_expenses = abs(calculated.get('interest_expense', 0)) + abs(calculated.get('other_expenses', 0))
            calculated['net_income_before_tax'] = calculated['operating_income'] + other_income - other_expenses
            if calculated['net_income_before_tax'] != calculated['operating_income']:
                logger.info(f"✅ Calculated Net Income Before Tax: {calculated['operating_income']:,.0f} + {other_income:,.0f} - {other_expenses:,.0f} = {calculated['net_income_before_tax']:,.0f}")
        
        # Formula 5: Net Income = Net Income Before Tax - Income Tax Expense
        if calculated['net_income'] == 0:
            if calculated['income_tax_expense'] > 0:
                calculated['net_income'] = calculated['net_income_before_tax'] - calculated['income_tax_expense']
                logger.info(f"✅ Calculated Net Income: {calculated['net_income_before_tax']:,.0f} - {calculated['income_tax_expense']:,.0f} = {calculated['net_income']:,.0f}")
            elif calculated['net_income_before_tax'] > 0:
                # Estimate tax (typically 25-30% of income before tax)
                estimated_tax = calculated['net_income_before_tax'] * 0.30
                calculated['income_tax_expense'] = estimated_tax
                calculated['net_income'] = calculated['net_income_before_tax'] - estimated_tax
                logger.info(f"⚠️ Estimated Income Tax: {estimated_tax:,.0f} (30% of income before tax)")
            else:
                # Fallback: Net Income ≈ Operating Income * 0.85 (after-tax approximation)
                if calculated['operating_income'] > 0:
                    calculated['net_income'] = calculated['operating_income'] * 0.85
                    logger.info(f"⚠️ Estimated Net Income: {calculated['net_income']:,.0f} (85% of operating income)")
        
        return calculated
    
    def _validate_and_correct(self, data: Dict[str, float]) -> Dict[str, float]:
        """Validate data integrity and correct any inconsistencies"""
        validated = data.copy()
        
        # ✅ CRITICAL VALIDATION: Check if Revenue and Net Income are swapped
        total_revenue = validated.get('total_revenue', 0)
        net_income = validated.get('net_income', 0)
        
        if total_revenue > 0 and net_income > 0 and total_revenue < net_income:
            logger.error(f"❌ CRITICAL: Revenue ({total_revenue:,.0f}) < Net Income ({net_income:,.0f}) - values may be swapped!")
            # This is a critical error - Revenue should always be >= Net Income
            # If we have other values, try to reconstruct
            cost_of_revenue = validated.get('cost_of_revenue', 0)
            gross_profit = validated.get('gross_profit', 0)
            operating_income = validated.get('operating_income', 0)
            total_operating_expenses = validated.get('total_operating_expenses', 0)
            
            # If we have enough data, try to calculate what revenue should be
            if gross_profit > 0 and cost_of_revenue > 0:
                calculated_revenue = gross_profit + cost_of_revenue
                if calculated_revenue > net_income:
                    logger.warning(f"⚠️ Attempting to correct: Using calculated revenue {calculated_revenue:,.0f} instead of {total_revenue:,.0f}")
                    validated['total_revenue'] = calculated_revenue
                    total_revenue = calculated_revenue
            elif operating_income > 0 and total_operating_expenses > 0:
                calculated_gross_profit = operating_income + total_operating_expenses
                if cost_of_revenue > 0:
                    calculated_revenue = calculated_gross_profit + cost_of_revenue
                    if calculated_revenue > net_income:
                        logger.warning(f"⚠️ Attempting to correct: Using calculated revenue {calculated_revenue:,.0f}")
                        validated['total_revenue'] = calculated_revenue
                        validated['gross_profit'] = calculated_gross_profit
                        total_revenue = calculated_revenue
        
        # Validation 1: Revenue should be positive
        if validated['total_revenue'] <= 0:
            logger.warning("⚠️ Total Revenue is zero or negative - data may be incomplete")
        
        # Validation 2: Cost of Revenue should be less than Revenue
        if validated['cost_of_revenue'] > validated['total_revenue'] and validated['total_revenue'] > 0:
            logger.warning(f"⚠️ Cost of Revenue ({validated['cost_of_revenue']:,.0f}) exceeds Revenue ({validated['total_revenue']:,.0f})")
            # Correct: Cap cost at 90% of revenue
            validated['cost_of_revenue'] = validated['total_revenue'] * 0.90
            validated['gross_profit'] = validated['total_revenue'] - validated['cost_of_revenue']
        
        # Validation 3: Operating Expenses should be less than Gross Profit
        if validated['total_operating_expenses'] > validated['gross_profit'] and validated['gross_profit'] > 0:
            logger.warning(f"⚠️ Operating Expenses ({validated['total_operating_expenses']:,.0f}) exceed Gross Profit ({validated['gross_profit']:,.0f})")
            # Correct: Cap expenses at 95% of gross profit
            validated['total_operating_expenses'] = validated['gross_profit'] * 0.95
            validated['operating_income'] = validated['gross_profit'] - validated['total_operating_expenses']
        
        # Validation 4: Operating Income should be positive for healthy business
        if validated['operating_income'] < 0:
            logger.warning(f"⚠️ Operating Income is negative: {validated['operating_income']:,.0f}")
        
        # Validation 5: Tax should not exceed income before tax
        if validated['income_tax_expense'] > validated['net_income_before_tax'] and validated['net_income_before_tax'] > 0:
            logger.warning(f"⚠️ Tax Expense exceeds Income Before Tax")
            validated['income_tax_expense'] = validated['net_income_before_tax'] * 0.30
            validated['net_income'] = validated['net_income_before_tax'] - validated['income_tax_expense']
        
        # Validation 6: Check ratios are reasonable
        if validated['total_revenue'] > 0:
            cost_ratio = validated['cost_of_revenue'] / validated['total_revenue']
            expense_ratio = validated['total_operating_expenses'] / validated['total_revenue']
            
            if cost_ratio > 0.90:
                logger.warning(f"⚠️ Cost ratio is very high: {cost_ratio:.2%}")
            if expense_ratio > 0.80:
                logger.warning(f"⚠️ Expense ratio is very high: {expense_ratio:.2%}")
        
        return validated
    
    def _final_normalization(self, data: Dict[str, float]) -> Dict[str, float]:
        """Final normalization to ensure all required fields are present"""
        final = {
            'total_revenue': data.get('total_revenue', 0.0),
            'cost_of_revenue': data.get('cost_of_revenue', 0.0),
            'gross_profit': data.get('gross_profit', 0.0),
            'total_operating_expenses': data.get('total_operating_expenses', 0.0),
            'operating_income': data.get('operating_income', 0.0),
            'net_income': data.get('net_income', 0.0),
            'interest_income': data.get('interest_income', 0.0),
            'interest_expense': data.get('interest_expense', 0.0),
            'income_tax_expense': data.get('income_tax_expense', 0.0),
            'net_income_before_tax': data.get('net_income_before_tax', 0.0),
        }
        
        # Ensure all values are non-negative where appropriate
        for key in ['total_revenue', 'cost_of_revenue', 'gross_profit', 'total_operating_expenses', 
                   'operating_income', 'net_income', 'interest_income', 'income_tax_expense']:
            if final[key] < 0:
                final[key] = 0.0
        
        return final
    
    def _get_default_structure(self) -> Dict[str, float]:
        """Return default structure with zeros"""
        return {
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

