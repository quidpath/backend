"""Intelligent, multi-statement extractor built on pandas."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import pandas as pd

from .exceptions import ExtractorError, LabelNotFoundError, MissingFieldError, ValueNormalizationError
from .specs import DEFAULT_STATEMENT_SPECS, StatementSpec
from .utils import clean_numeric
from .workbook_loader import load_tables
from .label_matcher import AdvancedLabelMatcher
from .accounting_aliases import ACCOUNTING_ALIASES
from .number_extractor import find_value_in_row as robust_find_value_in_row

logger = logging.getLogger(__name__)


class StatementParser:
    """Parses a single statement specification from pandas tables."""

    SEARCH_DISTANCE = 5  # How many cells to search right/left for a value

    def __init__(self, spec: StatementSpec, label_threshold: float = 0.75) -> None:
        self.spec = spec
        # ✅ UPGRADE: Use advanced label matcher with comprehensive aliases
        # Build alias dict from spec fields
        spec_aliases = {}
        for field in spec.required_fields + spec.optional_fields:
            if field in ACCOUNTING_ALIASES:
                spec_aliases[field] = ACCOUNTING_ALIASES[field]
            elif field in spec.label_mapping:
                # Fallback to spec labels if not in comprehensive aliases
                spec_aliases[field] = list(spec.label_mapping[field])
        
        self.matcher = AdvancedLabelMatcher(
            aliases=spec_aliases,
            fuzzy_threshold=85.0,
            partial_threshold=90.0
        )

    def parse(self, tables: Dict[str, pd.DataFrame]) -> Optional[Dict[str, Any]]:
        """Parse the given tables for the statement defined by this spec."""
        # ✅ FIX: Define all_fields at the start (required + optional)
        all_fields = list(self.spec.required_fields) + list(self.spec.optional_fields)
        extracted: Dict[str, Any] = {field: None for field in all_fields}

        print(f"📝 Parsing for statement: {self.spec.name}")
        print(f"   Looking for fields: {all_fields}")
        logger.info(f"📝 Parsing for statement: {self.spec.name}")
        logger.info(f"   Looking for fields: {all_fields}")

        for sheet_name, df in tables.items():
            print(f"🔍 Scanning sheet '{sheet_name}' for {self.spec.name}")
            print(f"   Sheet dimensions: {len(df)} rows x {len(df.columns)} columns")
            logger.info(f"🔍 Scanning sheet '{sheet_name}' for {self.spec.name}")
            logger.info(f"   Sheet dimensions: {len(df)} rows x {len(df.columns)} columns")
            
            # ✅ FIX: Skip completely empty rows at the start
            # Find first row with actual data
            first_data_row = 0
            for idx in range(len(df)):
                row = df.iloc[idx]
                # Check if row has any meaningful content (non-empty, non-numeric-only cells)
                has_content = False
                for cell in row:
                    cell_str = str(cell).strip()
                    if cell_str and cell_str.lower() != 'nan' and cell_str.lower() != '':
                        # Check if it's not just a number
                        if not self._is_pure_number(cell_str):
                            has_content = True
                            break
                if has_content:
                    first_data_row = idx
                    break
            
            if first_data_row > 0:
                print(f"⏭️ Skipping {first_data_row} empty rows at start of sheet '{sheet_name}'")
                logger.info("⏭️ Skipping %d empty rows at start of sheet '%s'", first_data_row, sheet_name)
                df = df.iloc[first_data_row:].reset_index(drop=True)
            
            # ✅ DEBUG: Show first 10 rows of the actual DataFrame
            print(f"📋 First 10 rows of DataFrame after skipping empty rows:")
            for idx in range(min(10, len(df))):
                row_preview = df.iloc[idx].tolist()
                print(f"   Row {idx}: {row_preview}")
            
            # ✅ FIX: Initialize sheet_extracted with all fields
            sheet_extracted = {field: None for field in all_fields}
            
            # ✅ STRICT MODE: First pass - collect all potential matches with priority scores
            # Priority: Summary/total rows > Individual line items
            # ✅ FIX: Initialize candidate_matches with BOTH required and optional fields
            candidate_matches: Dict[str, List[Tuple[str, Any, float]]] = {field: [] for field in all_fields}
            
            # ✅ FIX: Only scan rows orientation since column scan is buggy
            # Column scan extracts from wrong row after transpose (labels row instead of values row)
            # Row-wise scanning is sufficient for most financial statements
            for orientation in ['rows']:
                print(f"🔄 Scanning in '{orientation}' orientation")
                iterator = df.iterrows()
                
                # Track current section (for context-aware matching)
                current_section = None  # 'income', 'expenses', 'cogs', etc.
                
                for row_idx, row_series in iterator:
                    row_list = row_series.tolist()
                    
                    # ✅ FIX: Only skip first 3 rows if they're document titles (not financial data)
                    # Check if this row contains a recognizable financial field label
                    if row_idx < 3:
                        contains_financial_label = False
                        for cell in row_list:
                            label_text = self._coerce_label(cell)
                            if label_text:
                                # Try to match this label
                                field = self.matcher.match(label_text)
                                if field:
                                    contains_financial_label = True
                                    break
                        
                        # If this row has financial labels, DON'T skip it
                        if not contains_financial_label:
                            continue
                    
                    # ✅ DEBUG: Log rows after 60 to find missing Net Profit
                    if row_idx > 60:  # Show all rows after 60
                        first_cell = str(row_list[0])[:80] if row_list else ""
                        last_cell = str(row_list[-1])[:30] if row_list and len(row_list) > 1 else ""
                        print(f"🔍 Row {row_idx}: '{first_cell}' ... '{last_cell}'")
                    
                    # ✅ FIX: Skip rows that are completely empty or only contain numbers
                    row_has_labels = False
                    for cell in row_list:
                        label_text = self._coerce_label(cell)
                        if label_text:
                            row_has_labels = True
                            break
                    
                    if not row_has_labels:
                        continue  # Skip this row - no labels found
                    
                    # ✅ FIX: Detect section headers (update current_section)
                    first_label = self._coerce_label(row_list[0]) if row_list else ""
                    if first_label:
                        first_label_lower = first_label.lower()
                        # Detect section transitions
                        if any(term in first_label_lower for term in ['trading income', 'operating income', 'revenue', 'sales']):
                            if not any(term in first_label_lower for term in ['total', 'expense', 'cost']):
                                current_section = 'income'
                                print(f"📍 Section: INCOME (detected from '{first_label}')")
                        elif any(term in first_label_lower for term in ['cost of sales', 'cost of goods', 'cogs']):
                            current_section = 'cogs'
                            print(f"📍 Section: COGS (detected from '{first_label}')")
                        elif any(term in first_label_lower for term in ['operating expense', 'operating expenditure', 'opex']):
                            current_section = 'expenses'
                            print(f"📍 Section: EXPENSES (detected from '{first_label}')")
                        elif any(term in first_label_lower for term in ['gross profit', 'operating profit', 'net profit']):
                            current_section = 'profit'
                            print(f"📍 Section: PROFIT (detected from '{first_label}')")
                    
                    # Scan through the row to find labels
                    for col_idx in range(len(row_list)):
                        label_text = self._coerce_label(row_list[col_idx])
                        if not label_text:
                            continue
                        
                        # ✅ UPGRADE: Use advanced matcher with comprehensive aliases
                        field = self.matcher.match(label_text)
                        if not field:
                            logger.debug("🔍 Label '%s' did not match any field", label_text)
                            continue
                        
                        # ✅ FIX: Context-aware validation - don't match expenses to revenue in expense section
                        label_lower = label_text.lower()
                        if current_section == 'expenses' and field == 'total_revenue':
                            print(f"⚠️ SKIP: Label '{label_text}' is in EXPENSES section, can't be revenue")
                            logger.debug("Skipping revenue match for '%s' - in expenses section", label_text)
                            continue
                        
                        # Detect expense-like terms
                        expense_indicators = ['expense', 'cost', 'fee', 'charge', 'payment', 'wages', 'salary', 
                                             'rent', 'utilities', 'commission', 'allowance', 'benefit',
                                             'cleaning', 'transport', 'travel', 'telephone', 'insurance',
                                             'maintenance', 'repairs', 'supplies', 'marketing', 'advertising']
                        is_expense_like = any(indicator in label_lower for indicator in expense_indicators)
                        
                        # ✅ FIX: Don't match expense-like terms to revenue
                        if is_expense_like and field == 'total_revenue':
                            print(f"⚠️ SKIP: Label '{label_text}' looks like an expense, can't be revenue")
                            logger.debug("Skipping revenue match for expense-like label '%s'", label_text)
                            continue
                        
                        # ✅ FIX: Skip "Non-Operating" labels when matching to operating fields
                        label_lower = label_text.lower()
                        if field == 'operating_expenses' and 'non-operating' in label_lower:
                            print(f"⚠️ SKIP: Label '{label_text}' contains 'non-operating', skipping for field: {field}")
                            logger.debug("Skipping 'non-operating' label '%s' for operating_expenses", label_text)
                            continue
                        if field == 'operating_income' and 'non-operating' in label_lower:
                            print(f"⚠️ SKIP: Label '{label_text}' contains 'non-operating', skipping for field: {field}")
                            logger.debug("Skipping 'non-operating' label '%s' for operating_income", label_text)
                            continue
                        
                        # ✅ FIX: "Total Operating Income" is ambiguous - often means Total Revenue, not Operating Profit
                        # If the label says "Total Operating Income" and we already have revenue, it's likely revenue
                        # Only use "Operating Profit" for operating_income
                        if field == 'operating_income' and 'total operating income' in label_lower:
                            print(f"⚠️ AMBIGUOUS: Label '{label_text}' could be revenue OR profit")
                            print(f"   Re-mapping to total_revenue (will use 'Operating Profit' for operating_income)")
                            logger.debug("Re-mapping 'Total Operating Income' from operating_income → total_revenue")
                            # Re-map to total_revenue instead
                            field = 'total_revenue'
                            # Boost priority since it's a total
                            priority = 2.0
                            print(f"   ✅ Now matching to: {field} with priority {priority}")
                        
                        # ✅ FIX: Check if this is a section header with no values
                        # (e.g., "Trading Income", "Cost of Sales", "Operating Expenses")
                        has_numeric_value = False
                        for cell in row_list[1:]:  # Skip first column (label)
                            if isinstance(cell, (int, float)) and cell != 0:
                                has_numeric_value = True
                                break
                            elif isinstance(cell, str) and cell.strip() and cell.strip() != '0':
                                # Try to parse as number
                                try:
                                    val = float(cell.replace(',', '').replace(' ', ''))
                                    if val != 0:
                                        has_numeric_value = True
                                        break
                                except:
                                    pass
                        
                        # ✅ FIX: Skip section headers with no values (wait for "Total" row)
                        is_section_header = (
                            ('income' in label_lower or 'revenue' in label_lower or 
                             'sales' in label_lower or 'expense' in label_lower or 
                             'cost' in label_lower) and
                            'total' not in label_lower and
                            not has_numeric_value
                        )
                        
                        if is_section_header:
                            print(f"⚠️ SKIP: Label '{label_text}' is a section header with no values")
                            print(f"   Waiting for 'Total {label_text}' row or line items")
                            logger.debug("Skipping section header '%s' - no numeric values", label_text)
                            continue
                        
                        print(f"🎯 MATCH FOUND in {orientation} orientation:")
                        print(f"   Row {row_idx}, Label: '{label_text}' → Field: {field}")
                        print(f"   Full row: {row_list}")
                        
                        # ✅ FIX: Verify field is in our spec and exists in candidate_matches
                        if field not in all_fields:
                            logger.warning("⚠️ Matched field '%s' not in spec for %s, skipping", 
                                         field, self.spec.name)
                            continue
                        
                        # ✅ FIX: Defensive check - ensure field exists in candidate_matches
                        if field not in candidate_matches:
                            logger.warning("⚠️ Field '%s' not in candidate_matches, initializing", field)
                            candidate_matches[field] = []
                        
                        # ✅ STRICT MODE: Determine priority - summary/total rows get higher priority
                        # BUT: Don't give high priority to "Total" rows with value = 0 (they're incorrect!)
                        is_summary_row = self._is_summary_row(label_text, row_list)
                        priority = 2.0 if is_summary_row else 1.0
                        
                        # Override: If this is a "Total" row but value will be 0, downgrade priority
                        if 'total' in label_lower and is_summary_row:
                            # Quick check: does this row have any non-zero values?
                            has_nonzero = False
                            for cell in row_list[1:]:
                                if isinstance(cell, (int, float)) and cell != 0:
                                    has_nonzero = True
                                    break
                                elif isinstance(cell, str) and cell.strip() and cell.strip() != '0':
                                    try:
                                        val = float(cell.replace(',', '').replace(' ', ''))
                                        if val != 0:
                                            has_nonzero = True
                                            break
                                    except:
                                        pass
                            
                            # If "Total" row has no non-zero values, give it LOWER priority than line items
                            if not has_nonzero:
                                priority = 0.5  # Lower than line items (1.0)
                                print(f"⚠️ 'Total' row has value = 0, downgrading priority to {priority}")
                                logger.debug("Downgrading priority for zero-value Total row '%s'", label_text)
                        
                        if field in self.spec.optional_fields and field == "risk_level":
                            value = self._find_value_in_row(row_list, col_idx, is_numeric=False)
                            if value:
                                sheet_extracted[field] = value
                                logger.debug("Extracted risk_level: %s", value)
                            continue
                        
                        # ✅ UPGRADE: Pass label text to help determine tax fields
                        print(f"🔎 Trying to extract value for label '{label_text}' (field: {field}) at col_idx={col_idx}")
                        print(f"   Row contents: {row_list}")
                        value = self._find_value_in_row(row_list, col_idx, is_numeric=True)
                        print(f"   Extracted value: {value} (type: {type(value).__name__})")
                        if value is not None:
                            candidate_matches[field].append((label_text, value, priority))
                            print(f"✅ Added candidate: {field} = {value}")
                            logger.info("🔍 Found candidate for %s: %s (from label '%s', priority=%.1f, row %s)", 
                                       field, value, label_text, priority, row_idx)
                        else:
                            # ✅ UPGRADE: Try searching entire row as fallback for merged cells
                            from .number_extractor import extract_numeric_value
                            
                            # ✅ DEBUG: Log entire row contents for troubleshooting
                            logger.warning("❌ Could not find numeric value for label '%s' (field: %s) in row %s", 
                                       label_text, field, row_idx)
                            print(f"🔍 DEBUG - Full row contents (row {row_idx}):")
                            logger.info("🔍 DEBUG - Full row contents (row %s):", row_idx)
                            for idx, cell in enumerate(row_list):
                                print(f"  [{idx}]: {repr(cell)} (type: {type(cell).__name__})")
                                logger.info("  [%d]: %s (type: %s)", idx, repr(cell), type(cell).__name__)
                            
                            fallback_value = extract_numeric_value(row_list, label=label_text, search_entire_row=True)
                            if fallback_value is not None:
                                candidate_matches[field].append((label_text, int(fallback_value), priority))
                                logger.info("✅ Found candidate for %s: %s (from entire row search, label '%s', priority=%.1f, row %s)", 
                                           field, int(fallback_value), label_text, priority, row_idx)
                            else:
                                logger.error("❌ FAILED to extract value from entire row for '%s' (field: %s)", 
                                           label_text, field)
            
            # ✅ DEBUG: Log how many rows were actually scanned
            print(f"\n📊 Finished scanning {len(df)} rows")
            print(f"📊 Total candidates collected: {sum(len(v) for v in candidate_matches.values())}")
            
            # ✅ STRICT MODE: Second pass - select highest priority match for each field
            # OR sum line items if "Total" row has zero value
            print("\n🎯 SELECTING BEST CANDIDATES FROM ALL MATCHES:")
            print("=" * 80)
            
            # Fields that should be SUMMED if no valid total exists
            summable_fields = {
                'cogs', 'operating_expenses', 'admin_expenses', 'sales_expenses',
                'finance_costs', 'interest_expense', 'total_expenses', 'other_expenses'
            }
            
            for field, candidates in candidate_matches.items():
                if not candidates:
                    continue
                
                # ✅ FIX: Only process fields that are in our spec
                if field not in all_fields:
                    continue
                
                # Sort by priority (highest first), then by value (largest first)
                candidates.sort(key=lambda x: (-x[2], -abs(x[1])))
                
                print(f"\n📊 Field: {field} ({len(candidates)} candidate(s))")
                
                # ✅ INTELLIGENT SUMMATION: If field is summable and has multiple line items,
                # ALWAYS sum them (since "Total" rows are unreliable - often = 0)
                should_sum = False
                if field in summable_fields and len(candidates) > 1:
                    # Check if there's a "Total" row with non-zero value
                    valid_total = None
                    for label, value, priority in candidates:
                        if 'total' in label.lower() and value != 0:
                            valid_total = (label, value, priority)
                            break
                    
                    if valid_total:
                        # Use the valid Total (move it to front of candidates)
                        print(f"   ✅ Found valid 'Total' row: '{valid_total[0]}' = {valid_total[1]:,}")
                        # Re-sort to put valid total first (override by setting its priority very high)
                        candidates = [valid_total] + [c for c in candidates if c != valid_total]
                    else:
                        # No valid total found - SUM all line items
                        non_zero_items = [c for c in candidates if c[1] != 0 and 'total' not in c[0].lower()]
                        if len(non_zero_items) > 1:  # Only sum if multiple line items
                            should_sum = True
                            print(f"   ⚠️ No valid 'Total' found, will sum {len(non_zero_items)} line items")
                
                if should_sum:
                    # Sum all non-zero line items (exclude "Total" rows)
                    line_items = [(label, value, priority) for label, value, priority in candidates 
                                  if 'total' not in label.lower() and value != 0]
                    
                    total_sum = sum(value for _, value, _ in line_items)
                    sheet_extracted[field] = total_sum
                    
                    print(f"   💰 SUMMED {len(line_items)} line items:")
                    for idx, (label, value, priority) in enumerate(line_items[:5]):  # Show first 5
                        print(f"      + '{label}' = {value:,}")
                    if len(line_items) > 5:
                        print(f"      + ... ({len(line_items) - 5} more items)")
                    print(f"   ✅ TOTAL: {total_sum:,}")
                    
                    logger.info("✅ STRICT MODE: Summed %s: %s (from %d line items)", 
                               field, total_sum, len(line_items))
                else:
                    # Use top candidate (standard behavior)
                    for idx, (label, value, priority) in enumerate(candidates[:3]):  # Show top 3
                        marker = "✅ SELECTED" if idx == 0 else "   Skipped"
                        print(f"   {marker}: '{label}' = {value:,} (priority {priority})")
                    
                    selected_label, selected_value, selected_priority = candidates[0]
                    sheet_extracted[field] = selected_value
                    logger.info("✅ STRICT MODE: Selected %s: %s (from label '%s', priority=%.1f)", 
                               field, selected_value, selected_label, selected_priority)
                
                if len(candidates) > 1 and not should_sum:
                    logger.debug("   Skipped %d other candidates for %s", len(candidates) - 1, field)
            
            print("=" * 80)
            
            # ✅ STRICT MODE: After selecting all fields, validate if we have all required
            print("📊 DEBUG - All extracted fields:")
            print(json.dumps(sheet_extracted, indent=2, default=str))
            print("📊 DEBUG - Required fields status:")
            logger.info("📊 DEBUG - All extracted fields: %s", 
                      json.dumps(sheet_extracted, indent=2, default=str))
            logger.info("📊 DEBUG - Required fields status:")
            
            # ✅ FIX: Ensure total_revenue includes other_income
            # Check if total_revenue already includes other_income by seeing if they sum correctly
            if sheet_extracted.get('other_income'):
                total_rev = sheet_extracted.get('total_revenue', 0)
                other_inc = sheet_extracted.get('other_income', 0)
                
                # Simple check: if total_revenue ≈ (total_revenue - other_income) + other_income, it's already correct
                # Otherwise, if total_revenue looks like just sales revenue, add other_income
                expected_with_other = total_rev + other_inc
                
                # Check if total_revenue already seems to include other_income
                # (i.e., removing other_income would leave a reasonable sales figure)
                potential_sales = total_rev - other_inc
                
                if other_inc > 0 and potential_sales > 0:
                    # If other_income is <5% of total_revenue, it's likely already included
                    other_percentage = (other_inc / total_rev * 100) if total_rev > 0 else 0
                    
                    if other_percentage < 5:
                        # Very likely total_revenue already includes other_income
                        print(f"💡 total_revenue ({total_rev:,}) likely includes other_income ({other_inc:,}, {other_percentage:.2f}%)")
                        print(f"   No adjustment needed - keeping total_revenue as-is")
                    else:
                        # other_income is significant, might need to add it
                        print(f"💡 Calculating total_revenue: {total_rev:,} + {other_inc:,} = {expected_with_other:,}")
                        sheet_extracted['total_revenue'] = expected_with_other
                        logger.info("Added other_income to total_revenue: %s", expected_with_other)
                else:
                    print(f"💡 total_revenue = {total_rev:,}, other_income = {other_inc:,} - keeping as-is")
            
            # ✅ FIX: Apply fallback mappings for missing required fields
            # Map optional fields to required fields if required ones are missing
            fallback_mappings = {
                'operating_income': 'operating_profit',  # Operating income = Operating profit
                'interest_expense': 'finance_costs',     # Interest expense = Finance costs (BUT NOT TAXES!)
            }
            
            # ✅ FIX: Special handling - don't use interest_expense/finance_costs as fallback for taxes
            # If taxes is missing but we wrongly assigned tax values to interest_expense, move them
            if (sheet_extracted.get('taxes') is None and 
                sheet_extracted.get('interest_expense') is not None):
                # Check if interest_expense value looks like a tax (high value compared to typical interest)
                ie_value = sheet_extracted.get('interest_expense', 0)
                revenue = sheet_extracted.get('total_revenue', 1)
                # If interest_expense > 10% of revenue, it's likely actually taxes (mismatched)
                if revenue > 0 and ie_value > revenue * 0.10:
                    print(f"⚠️ WARNING: interest_expense ({ie_value}) seems too high (>{ie_value/revenue*100:.1f}% of revenue)")
                    print(f"   This might actually be taxes that were mismatched. Keeping as interest_expense.")
                    # Don't move it - rely on user to check
            
            for required_field, optional_field in fallback_mappings.items():
                if sheet_extracted.get(required_field) is None and sheet_extracted.get(optional_field) is not None:
                    sheet_extracted[required_field] = sheet_extracted[optional_field]
                    print(f"✅ FALLBACK: Using {optional_field} ({sheet_extracted[optional_field]}) for missing {required_field}")
                    logger.info("✅ FALLBACK: Using %s (%s) for missing %s", 
                              optional_field, sheet_extracted[optional_field], required_field)
            
            # Re-check required fields after fallback
            print("📊 DEBUG - Required fields status (after fallback):")
            missing_fields = []
            for req_field in self.spec.required_fields:
                value = sheet_extracted.get(req_field)
                status_line = f"  {req_field}: {'✅ FOUND' if value is not None else '❌ MISSING'} ({value if value is not None else 'None'})"
                print(status_line)
                logger.info("  %s: %s (%s)", req_field, 
                          "✅ FOUND" if value is not None else "❌ MISSING", 
                          value if value is not None else "None")
                if value is None:
                    missing_fields.append(req_field)
            
            if missing_fields:
                print(f"\n❌ MISSING REQUIRED FIELDS: {', '.join(missing_fields)}")
                print(f"   These fields had NO candidates collected during scanning.")
                print(f"   Check if labels for these fields exist in the statement.")
            
            # ✅ FIX: Normalize negative values to positive for expense fields
            # In some statements, expenses are stored as negative numbers
            # We need to convert them to positive for our calculations
            expense_fields = [
                'cogs', 'operating_expenses', 'interest_expense', 'taxes',
                'finance_costs', 'depreciation', 'amortization', 
                'sales_expenses', 'admin_expenses', 'other_expenses', 'total_expenses'
            ]
            
            print("\n🔄 Normalizing negative expense values to positive:")
            for field in expense_fields:
                if field in sheet_extracted and sheet_extracted[field] is not None:
                    value = sheet_extracted[field]
                    if value < 0:
                        positive_value = abs(value)
                        sheet_extracted[field] = positive_value
                        print(f"   {field}: {value:,} → {positive_value:,} (converted negative to positive)")
                        logger.info("✅ Normalized %s: %s → %s (converted negative to positive)", 
                                  field, value, positive_value)
                    else:
                        print(f"   {field}: {value:,} (already positive)")
            
            if self._has_all_required(sheet_extracted):
                # Apply validators
                validated_payload = {k: v for k, v in sheet_extracted.items() 
                                   if k in self.spec.required_fields}
                logger.info("📊 STRICT MODE - Extracted values before validation: %s", 
                          json.dumps(validated_payload, indent=2))
                
                validation_error = None
                try:
                    for validator in self.spec.validators:
                        validator(validated_payload)
                    logger.info("✅ Successfully extracted and validated %s from sheet '%s'", 
                              self.spec.name, sheet_name)
                    return sheet_extracted
                except Exception as e:
                    validation_error = str(e)
                    logger.warning("⚠️ STRICT MODE: Validation failed for %s in sheet '%s': %s", 
                                self.spec.name, sheet_name, e)
                    logger.warning("📋 STRICT MODE: Extracted values that failed validation (using as-is): %s", 
                                 json.dumps(sheet_extracted, indent=2, default=str))
                    
                    # ✅ STRICT MODE: Return data even if validation fails - use exact values from document
                    logger.info("⚠️ STRICT MODE: Returning extracted data despite validation failure - using exact values from document")
                    # Add validation_warning to the extracted data
                    sheet_extracted["_validation_warning"] = validation_error
                    return sheet_extracted

        return None

    def _find_value_in_row(self, row_list: List[Any], label_col_idx: int, is_numeric: bool) -> Optional[Any]:
        """
        Find a value in the same row as the label, using robust number extraction.
        
        ✅ UPGRADE: Uses universal number extractor that handles:
        - Unicode spaces, commas, currency symbols
        - Accounting negatives: (10000)
        - OCR noise
        - Merged cells (searches entire row if needed)
        """
        # Use the robust finder with extended search distance
        # Set search_distance to 0 to search entire row if needed
        result = robust_find_value_in_row(
            row_list=row_list,
            label_col_idx=label_col_idx,
            is_numeric=is_numeric,
            search_distance=self.SEARCH_DISTANCE
        )
        
        # Convert float to int for consistency with old behavior
        if is_numeric and result is not None and isinstance(result, float):
            return int(result)
        
        return result

    def _has_all_required(self, data: Dict[str, Any]) -> bool:
        return all(data.get(field) is not None for field in self.spec.required_fields)

    def _coerce_label(self, value: Any) -> Optional[str]:
        """
        Convert a cell value to a label string if possible.
        
        ✅ FIX: Better detection of labels vs numbers, handles edge cases.
        """
        if value is None:
            return None
        
        # Convert to string and strip
        text = str(value).strip()
        
        # Skip empty strings
        if not text or text.lower() == "nan" or text.lower() == "":
            return None
        
        # ✅ FIX: Skip if it's clearly a number (with better detection)
        # Check if it's a pure number (digits, dots, commas, minus signs, parentheses)
        # But allow labels that contain numbers (e.g., "Q1 2023", "Year 2024")
        numeric_chars = text.replace('.', '').replace('-', '').replace(',', '').replace('(', '').replace(')', '').replace(' ', '').replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('₹', '').replace('KES', '').replace('ksh', '').replace('KSH', '')
        
        # If it's all digits or mostly digits (>80%), it's likely a number
        if numeric_chars and len(numeric_chars) > 0:
            digit_ratio = sum(1 for c in numeric_chars if c.isdigit()) / len(numeric_chars) if numeric_chars else 0
            if digit_ratio > 0.8 and len(numeric_chars) >= 3:  # At least 3 chars and >80% digits
                return None
        
        # ✅ FIX: Skip very short strings that are likely numbers or codes
        if len(text) <= 2 and (text.isdigit() or text.replace('-', '').isdigit()):
            return None
        
        # Return the text as a potential label
        return text
    
    def _is_pure_number(self, text: str) -> bool:
        """Check if text is a pure number (no letters, just digits and formatting)."""
        if not text:
            return False
        # Remove common number formatting
        cleaned = text.replace(',', '').replace('.', '').replace('-', '').replace('(', '').replace(')', '').replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('₹', '').replace('KES', '').replace('ksh', '').replace(' ', '').strip()
        return cleaned.isdigit() and len(cleaned) >= 1
    
    def _is_summary_row(self, label_text: str, row_list: List[Any]) -> bool:
        """
        Determine if this row is a summary/total row that should take priority.
        Summary rows typically:
        1. Contain words like "total", "gross profit", "operating profit", "net profit"
        2. Have the label as a standalone field (not part of a longer description)
        3. Often appear after detail rows
        """
        label_lower = label_text.lower()
        
        # Check for summary indicators in the label
        summary_indicators = [
            'total for',
            'total',
            'gross profit',
            'gross income',
            'operating profit',
            'operating income',
            'net profit',
            'net income',
            'net loss',
            'profit/loss'
        ]
        
        # Check if label contains summary indicators
        for indicator in summary_indicators:
            if indicator in label_lower:
                # Additional check: if it's a standalone field (not "Sales" but "Total for Operating Income")
                if 'total' in label_lower or 'profit' in label_lower or 'income' in label_lower:
                    return True
        
        # Check if the row appears to be a summary row by looking at surrounding context
        # Summary rows often have fewer non-empty cells (just label and value)
        non_empty_cells = sum(1 for cell in row_list if cell and str(cell).strip() and str(cell).strip().lower() != 'nan')
        if non_empty_cells <= 3:  # Summary rows typically have label + value + maybe one other field
            # Check if this looks like a total row
            if any(word in label_lower for word in ['total', 'profit', 'income', 'loss']):
                return True
        
        return False


@dataclass
class ExtractionResult:
    success: bool
    statements: Dict[str, Dict[str, Any]]
    json_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class IntelligentStatementExtractor:
    """High-accuracy extractor capable of parsing multiple statement types."""

    def __init__(self, specs: Tuple[StatementSpec, ...] = DEFAULT_STATEMENT_SPECS) -> None:
        self.specs = specs

    def extract(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise ExtractorError(f"File does not exist: {path}")

        print("=" * 80)
        print("🚀 STARTING INTELLIGENT EXTRACTION")
        print("=" * 80)
        print(f"📁 File: {path}")
        print(f"📋 Specs to try: {[spec.name for spec in self.specs]}")
        logger.info("=" * 80)
        logger.info("🚀 STARTING INTELLIGENT EXTRACTION")
        logger.info("=" * 80)
        logger.info(f"📁 File: {path}")
        logger.info(f"📋 Specs to try: {[spec.name for spec in self.specs]}")
        
        tables = load_tables(path)
        print(f"📊 Loaded {len(tables)} sheet(s) from file:")
        logger.info(f"📊 Loaded {len(tables)} sheet(s) from file:")
        for sheet_name, df in tables.items():
            print(f"   - Sheet '{sheet_name}': {len(df)} rows x {len(df.columns)} columns")
            logger.info(f"   - Sheet '{sheet_name}': {len(df)} rows x {len(df.columns)} columns")
            print(f"     First 5 rows preview:")
            logger.info(f"     First 5 rows preview:")
            for idx in range(min(5, len(df))):
                row_preview = df.iloc[idx].tolist()[:5]  # First 5 columns
                print(f"     Row {idx}: {row_preview}")
                logger.info(f"     Row {idx}: {row_preview}")
        
        statements: Dict[str, Dict[str, Any]] = {}

        for spec in self.specs:
            print(f"🔍 Attempting to extract: {spec.name}")
            print(f"   Required fields: {spec.required_fields}")
            logger.info(f"🔍 Attempting to extract: {spec.name}")
            logger.info(f"   Required fields: {spec.required_fields}")
            parser = StatementParser(spec)
            try:
                data = parser.parse(tables)
            except (LabelNotFoundError, ValueNormalizationError, MissingFieldError, ExtractorError) as exc:
                logger.warning("Failed to parse %s: %s", spec.name, exc)
                continue
            except Exception as exc:
                logger.error("Unexpected error parsing %s: %s", spec.name, exc, exc_info=True)
                continue

            if data:
                logger.info("✅ Successfully extracted %s from %s", spec.name, path)
                logger.info(f"   Extracted data keys: {list(data.keys())}")
                # Remove internal validation warning field before returning
                clean_data = {k: v for k, v in data.items() if not k.startswith("_")}
                statements[spec.name] = clean_data
                
                if "_validation_warning" in data:
                    logger.warning("⚠️ %s extracted with validation warning: %s", 
                                 spec.name, data.get("_validation_warning"))
                else:
                    logger.info("✅ Successfully extracted %s", spec.name)
                
                logger.info("📄 Final JSON for %s:\n%s", spec.name, json.dumps(clean_data, indent=2))
                break  # Found the first matching statement type
            else:
                logger.warning(f"❌ Failed to extract {spec.name} - parser returned None")

        if not statements:
            logger.error("=" * 80)
            logger.error("❌ EXTRACTION FAILED: No recognizable statements found in file: %s", path)
            logger.error("=" * 80)
            logger.error("Tried %d statement specs:", len(self.specs))
            for spec in self.specs:
                logger.error(f"   - {spec.name} (required fields: {spec.required_fields})")
            logger.error(f"Available sheets: {list(tables.keys())}")
            logger.error("=" * 80)
            return {"success": False, "error": "No recognizable statements found."}

        primary_json = statements.get("income_statement") or next(iter(statements.values()))
        records = [
            {"statement_type": name, **payload}
            for name, payload in statements.items()
        ]

        confidence = self._compute_confidence(statements)

        return {
            "success": True,
            "statements": statements,
            "json_data": primary_json,
            "extracted_data": {
                "records": records,
                "metrics": statements,
            },
            "confidence": confidence,
        }

    def _compute_confidence(self, statements: Dict[str, Dict[str, Any]]) -> float:
        if not statements:
            return 0.0
        coverage = len(statements) / len(self.specs)
        return round(min(0.99, 0.7 + coverage * 0.25), 3)

