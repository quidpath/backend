"""
Financial Statement Reconciliation Engine
Validates and auto-corrects income statement inconsistencies before fraud assessment
"""
import logging
from typing import Dict, List, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)


class FinancialReconciliationEngine:
    """
    Validates and auto-corrects financial statements according to accounting rules:
    1. Gross Profit = Revenue - COGS
    2. Operating Income Before OPEX = Gross Profit + Other Income
    3. Operating Profit = Operating Income Before OPEX - Operating Expenses
    4. Profit Before Tax = Operating Profit - Finance Costs
    5. Net Profit = Profit Before Tax - Income Tax Expense
    """
    
    def __init__(self):
        self.corrections = []
        self.warnings = []
        self.critical_issues = []
        self.reconciliation_successful = False
    
    def reconcile_statement(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main reconciliation method
        Returns: {
            'reconciled_data': corrected financial data,
            'corrections_made': list of corrections,
            'reconciliation_report': detailed report,
            'risk_level': LOW/MODERATE/HIGH/CRITICAL,
            'is_reconciled': boolean
        }
        """
        self.corrections = []
        self.warnings = []
        self.critical_issues = []
        
        # Step 1: Extract and normalize values
        normalized = self._normalize_values(raw_data)
        
        # Step 2: Validate and correct the statement
        reconciled = self._validate_and_correct(normalized)
        
        # Step 3: Calculate margins
        reconciled['margins'] = self._calculate_margins(reconciled)
        
        # Step 4: Assess risk after correction
        risk_assessment = self._assess_risk_post_correction(reconciled, normalized)
        
        # Step 5: Generate reconciliation report
        report = self._generate_report(normalized, reconciled, risk_assessment)
        
        return {
            'reconciled_data': reconciled,
            'original_data': normalized,
            'corrections_made': self.corrections,
            'warnings': self.warnings,
            'critical_issues': self.critical_issues,
            'reconciliation_report': report,
            'risk_level': risk_assessment['risk_level'],
            'risk_reason': risk_assessment['reason'],
            'lending_recommendation': risk_assessment['lending_recommendation'],
            'is_reconciled': self.reconciliation_successful
        }
    
    def _normalize_values(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract and normalize all financial values
        Convert negative tax/expenses to positive
        Handle various field name variations
        """
        def get_value(*keys) -> float:
            for key in keys:
                if key in raw_data and raw_data[key] is not None:
                    try:
                        return float(raw_data[key])
                    except (ValueError, TypeError):
                        continue
            return 0.0
        
        # Extract values with field name variations
        revenue = get_value('revenue', 'totalRevenue', 'total_revenue', 'Revenue')
        cogs = get_value('costOfGoodsSold', 'cost_of_goods_sold', 'costOfRevenue', 'cost_of_revenue', 'cogs', 'COGS')
        gross_profit = get_value('grossProfit', 'gross_profit', 'Gross Profit')
        other_income = get_value('otherIncome', 'other_income', 'Other Income', 'non_operating_income')
        op_income_before_opex = get_value('operatingIncomeBeforeOPEX', 'operating_income_before_opex', 'Operating Income Before OPEX')
        operating_expenses = get_value('operatingExpenses', 'operating_expenses', 'totalOperatingExpenses', 'total_operating_expenses', 'Operating Expenses')
        operating_profit = get_value('operatingProfit', 'operating_profit', 'operatingIncome', 'operating_income', 'Operating Profit')
        finance_costs = get_value('financeCosts', 'finance_costs', 'interestExpense', 'interest_expense', 'Finance Costs')
        profit_before_tax = get_value('profitBeforeTax', 'profit_before_tax', 'Profit Before Tax', 'ebt')
        income_tax = get_value('incomeTaxExpense', 'income_tax_expense', 'Income Tax Expense', 'taxes')
        net_profit = get_value('netProfit', 'net_profit', 'netIncome', 'net_income', 'Net Profit')
        
        # ✅ NORMALIZE: Convert negative expenses/taxes to positive
        if operating_expenses < 0:
            self.corrections.append({
                'field': 'operating_expenses',
                'original': operating_expenses,
                'corrected': abs(operating_expenses),
                'reason': 'Converted negative expense to positive (expenses reduce profit)'
            })
            operating_expenses = abs(operating_expenses)
        
        if income_tax < 0:
            self.corrections.append({
                'field': 'income_tax_expense',
                'original': income_tax,
                'corrected': abs(income_tax),
                'reason': 'Converted negative tax to positive (taxes are an expense)'
            })
            income_tax = abs(income_tax)
        
        # ✅ NORMALIZE: Finance costs should be positive (they reduce profit)
        if finance_costs < 0:
            self.corrections.append({
                'field': 'finance_costs',
                'original': finance_costs,
                'corrected': abs(finance_costs),
                'reason': 'Converted negative finance costs to positive (interest is an expense)'
            })
            finance_costs = abs(finance_costs)
        
        # ✅ COGS should typically be positive unless explicitly rebates
        if cogs < 0 and abs(cogs) > revenue * 0.05:  # Allow small negative if < 5% of revenue (rebates)
            self.warnings.append(f"⚠️ UNUSUAL: COGS is negative ({cogs:,.2f}). If not rebates/returns, this is incorrect.")
        
        return {
            'revenue': revenue,
            'cost_of_goods_sold': cogs,
            'gross_profit': gross_profit,
            'other_income': other_income,
            'operating_income_before_opex': op_income_before_opex,
            'operating_expenses': operating_expenses,
            'operating_profit': operating_profit,
            'finance_costs': finance_costs,
            'profit_before_tax': profit_before_tax,
            'income_tax_expense': income_tax,
            'net_profit': net_profit
        }
    
    def _validate_and_correct(self, data: Dict[str, float]) -> Dict[str, float]:
        """
        Validate accounting equations and auto-correct where possible
        """
        reconciled = data.copy()
        tolerance = 1.0  # Allow KES 1 difference for rounding
        
        # Rule 1: Gross Profit = Revenue - COGS
        if reconciled['revenue'] > 0 or reconciled['cost_of_goods_sold'] > 0:
            calculated_gp = reconciled['revenue'] - reconciled['cost_of_goods_sold']
            
            if abs(reconciled['gross_profit'] - calculated_gp) > tolerance:
                self.corrections.append({
                    'field': 'gross_profit',
                    'original': reconciled['gross_profit'],
                    'corrected': calculated_gp,
                    'reason': f'Gross Profit must equal Revenue ({reconciled["revenue"]:,.2f}) - COGS ({reconciled["cost_of_goods_sold"]:,.2f})',
                    'formula': 'GP = Revenue - COGS'
                })
                reconciled['gross_profit'] = calculated_gp
        
        # Rule 2: Operating Income Before OPEX = Gross Profit + Other Income
        calculated_oi_before_opex = reconciled['gross_profit'] + reconciled['other_income']
        
        if abs(reconciled['operating_income_before_opex'] - calculated_oi_before_opex) > tolerance:
            self.corrections.append({
                'field': 'operating_income_before_opex',
                'original': reconciled['operating_income_before_opex'],
                'corrected': calculated_oi_before_opex,
                'reason': f'Operating Income Before OPEX = Gross Profit ({reconciled["gross_profit"]:,.2f}) + Other Income ({reconciled["other_income"]:,.2f})',
                'formula': 'OI Before OPEX = GP + Other Income'
            })
            reconciled['operating_income_before_opex'] = calculated_oi_before_opex
        
        # Rule 3: Operating Profit = Operating Income Before OPEX - Operating Expenses
        calculated_op = calculated_oi_before_opex - reconciled['operating_expenses']
        
        if abs(reconciled['operating_profit'] - calculated_op) > tolerance:
            self.corrections.append({
                'field': 'operating_profit',
                'original': reconciled['operating_profit'],
                'corrected': calculated_op,
                'reason': f'Operating Profit = OI Before OPEX ({calculated_oi_before_opex:,.2f}) - Operating Expenses ({reconciled["operating_expenses"]:,.2f})',
                'formula': 'OP = OI Before OPEX - OPEX'
            })
            reconciled['operating_profit'] = calculated_op
        
        # Rule 4: Profit Before Tax = Operating Profit - Finance Costs
        calculated_pbt = calculated_op - reconciled['finance_costs']
        
        if abs(reconciled['profit_before_tax'] - calculated_pbt) > tolerance:
            self.corrections.append({
                'field': 'profit_before_tax',
                'original': reconciled['profit_before_tax'],
                'corrected': calculated_pbt,
                'reason': f'Profit Before Tax = Operating Profit ({calculated_op:,.2f}) - Finance Costs ({reconciled["finance_costs"]:,.2f})',
                'formula': 'PBT = OP - Finance Costs'
            })
            reconciled['profit_before_tax'] = calculated_pbt
        
        # Rule 5: Net Profit = Profit Before Tax - Income Tax Expense
        calculated_np = calculated_pbt - reconciled['income_tax_expense']
        
        if abs(reconciled['net_profit'] - calculated_np) > tolerance:
            self.corrections.append({
                'field': 'net_profit',
                'original': reconciled['net_profit'],
                'corrected': calculated_np,
                'reason': f'Net Profit = Profit Before Tax ({calculated_pbt:,.2f}) - Income Tax ({reconciled["income_tax_expense"]:,.2f})',
                'formula': 'NP = PBT - Tax'
            })
            reconciled['net_profit'] = calculated_np
        
        # Mark as successfully reconciled if no critical issues
        self.reconciliation_successful = len(self.critical_issues) == 0
        
        return reconciled
    
    def _calculate_margins(self, data: Dict[str, float]) -> Dict[str, float]:
        """Calculate key financial margins"""
        revenue = data['revenue']
        
        if revenue <= 0:
            return {
                'profit_margin': 0.0,
                'operating_margin': 0.0,
                'gross_margin': 0.0,
                'cost_ratio': 0.0,
                'expense_ratio': 0.0
            }
        
        return {
            'profit_margin': round((data['net_profit'] / revenue) * 100, 2),
            'operating_margin': round((data['operating_profit'] / revenue) * 100, 2),
            'gross_margin': round((data['gross_profit'] / revenue) * 100, 2),
            'cost_ratio': round((data['cost_of_goods_sold'] / revenue) * 100, 2),
            'expense_ratio': round((data['operating_expenses'] / revenue) * 100, 2)
        }
    
    def _assess_risk_post_correction(self, reconciled: Dict[str, float], original: Dict[str, float]) -> Dict[str, Any]:
        """
        Assess risk AFTER reconciliation
        Only flag as CRITICAL if intentional fraud indicators present
        """
        risk_score = 0
        reasons = []
        
        # Check 1: Are margins still impossible after correction?
        margins = reconciled['margins']
        
        if margins['gross_margin'] > 95:
            risk_score += 30
            reasons.append(f"Gross margin of {margins['gross_margin']:.1f}% exceeds 95% even after correction")
            self.critical_issues.append("Impossibly high gross margin persists after reconciliation")
        
        if margins['profit_margin'] > 90:
            risk_score += 25
            reasons.append(f"Net profit margin of {margins['profit_margin']:.1f}% exceeds 90% even after correction")
            self.critical_issues.append("Impossibly high net margin persists after reconciliation")
        
        # Check 2: Did we make excessive corrections?
        if len(self.corrections) > 5:
            risk_score += 15
            reasons.append(f"Statement required {len(self.corrections)} corrections - indicates poor data quality or manipulation")
        elif len(self.corrections) > 3:
            risk_score += 7
            reasons.append(f"Statement required {len(self.corrections)} corrections - data entry errors present")
        
        # Check 3: Tax patterns (but only if profitable)
        if reconciled['profit_before_tax'] > 10000:  # Profitable company
            if reconciled['income_tax_expense'] == 0:
                risk_score += 20
                reasons.append(f"Profitable company (PBT: KES {reconciled['profit_before_tax']:,.2f}) shows zero taxes")
            elif reconciled['income_tax_expense'] > 0:
                tax_rate = (reconciled['income_tax_expense'] / reconciled['profit_before_tax']) * 100
                if tax_rate < 10:
                    risk_score += 10
                    reasons.append(f"Unusually low tax rate of {tax_rate:.1f}% (expected 20-30%)")
        
        # Check 4: COGS patterns
        if reconciled['revenue'] > 0:
            cogs_ratio = (reconciled['cost_of_goods_sold'] / reconciled['revenue']) * 100
            if cogs_ratio < 5 and reconciled['revenue'] > 1000000:
                risk_score += 10
                reasons.append(f"COGS is only {cogs_ratio:.1f}% of revenue - verify if accurate")
            elif cogs_ratio > 95:
                risk_score += 15
                reasons.append(f"COGS is {cogs_ratio:.1f}% of revenue - selling below cost")
        
        # Check 5: Operating expenses reasonableness
        if reconciled['revenue'] > 0:
            opex_ratio = (reconciled['operating_expenses'] / reconciled['revenue']) * 100
            if opex_ratio < 3 and reconciled['revenue'] > 1000000:
                risk_score += 8
                reasons.append(f"Operating expenses are only {opex_ratio:.1f}% of revenue - unusually low")
        
        # ✅ DOWNGRADE to DATA ERROR if statement reconciles properly
        if len(self.corrections) > 0 and len(self.critical_issues) == 0:
            if risk_score < 25:
                risk_level = 'LOW'
                lending_recommendation = 'PROCEED - Statement has been reconciled. Arithmetic errors corrected.'
            else:
                risk_level = 'MODERATE'
                lending_recommendation = 'PROCEED WITH CAUTION - Statement corrected but some unusual patterns present.'
        elif risk_score >= 75:
            risk_level = 'CRITICAL'
            lending_recommendation = 'DO NOT PROCEED - Multiple fraud indicators present even after correction.'
        elif risk_score >= 50:
            risk_level = 'HIGH'
            lending_recommendation = 'WAIT - Significant issues detected. Request clarification before proceeding.'
        elif risk_score >= 25:
            risk_level = 'MODERATE'
            lending_recommendation = 'PROCEED WITH CAUTION - Some concerns present but not critical.'
        else:
            risk_level = 'LOW'
            lending_recommendation = 'PROCEED - Financial statement appears sound.'
        
        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'reason': ' | '.join(reasons) if reasons else 'Statement reconciles properly',
            'lending_recommendation': lending_recommendation
        }
    
    def _generate_report(self, original: Dict[str, float], reconciled: Dict[str, float], risk: Dict[str, Any]) -> str:
        """Generate human-readable reconciliation report"""
        report = []
        report.append("=" * 80)
        report.append("FINANCIAL STATEMENT RECONCILIATION REPORT")
        report.append("=" * 80)
        
        # Corrections Made
        if self.corrections:
            report.append(f"\n✅ CORRECTIONS MADE: {len(self.corrections)}")
            report.append("-" * 80)
            for i, corr in enumerate(self.corrections, 1):
                report.append(f"\n{i}. Field: {corr['field'].replace('_', ' ').title()}")
                report.append(f"   Original Value:  KES {corr['original']:>15,.2f}")
                report.append(f"   Corrected Value: KES {corr['corrected']:>15,.2f}")
                report.append(f"   Difference:      KES {abs(corr['corrected'] - corr['original']):>15,.2f}")
                report.append(f"   Reason: {corr['reason']}")
                if 'formula' in corr:
                    report.append(f"   Formula: {corr['formula']}")
        else:
            report.append("\n✅ NO CORRECTIONS NEEDED")
            report.append("   All accounting equations are satisfied.")
        
        # Warnings
        if self.warnings:
            report.append(f"\n⚠️ WARNINGS: {len(self.warnings)}")
            report.append("-" * 80)
            for warning in self.warnings:
                report.append(f"   • {warning}")
        
        # Critical Issues
        if self.critical_issues:
            report.append(f"\n🚨 CRITICAL ISSUES: {len(self.critical_issues)}")
            report.append("-" * 80)
            for issue in self.critical_issues:
                report.append(f"   • {issue}")
        
        # Reconciled Margins
        report.append("\n📊 RECONCILED FINANCIAL RATIOS")
        report.append("-" * 80)
        margins = reconciled['margins']
        report.append(f"   Gross Margin:      {margins['gross_margin']:>6.2f}%")
        report.append(f"   Operating Margin:  {margins['operating_margin']:>6.2f}%")
        report.append(f"   Net Profit Margin: {margins['profit_margin']:>6.2f}%")
        report.append(f"   COGS Ratio:        {margins['cost_ratio']:>6.2f}%")
        report.append(f"   Expense Ratio:     {margins['expense_ratio']:>6.2f}%")
        
        # Risk Assessment
        report.append(f"\n🎯 RISK ASSESSMENT")
        report.append("-" * 80)
        report.append(f"   Risk Level: {risk['risk_level']}")
        report.append(f"   Risk Score: {risk['risk_score']}/100")
        report.append(f"   Reason: {risk['reason']}")
        
        # Lending Recommendation
        report.append(f"\n💼 LENDING RECOMMENDATION")
        report.append("-" * 80)
        report.append(f"   {risk['lending_recommendation']}")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)

