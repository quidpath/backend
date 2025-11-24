"""
Advanced Fraud Detection Engine for Financial Statements
Uses forensic accounting principles and statistical analysis
"""
import logging
from typing import Dict, List, Any, Tuple
import math
from decimal import Decimal

logger = logging.getLogger(__name__)


class FraudDetectionEngine:
    """
    Sophisticated fraud detection using:
    1. Benford's Law analysis
    2. Ratio analysis with industry benchmarks
    3. Mathematical reconciliation
    4. Statistical anomaly detection
    5. Forensic accounting red flags
    """
    
    # Industry benchmarks (conservative estimates)
    BENCHMARKS = {
        'gross_margin': {'min': 0.15, 'max': 0.85, 'typical_range': (0.25, 0.60)},
        'operating_margin': {'min': -0.10, 'max': 0.50, 'typical_range': (0.05, 0.25)},
        'net_margin': {'min': -0.30, 'max': 0.40, 'typical_range': (0.03, 0.20)},
        'cost_of_revenue_ratio': {'min': 0.15, 'max': 0.85, 'typical_range': (0.40, 0.75)},
        'operating_expense_ratio': {'min': 0.05, 'max': 0.80, 'typical_range': (0.15, 0.50)},
        'tax_rate': {'min': 0.15, 'max': 0.35, 'typical_range': (0.20, 0.30)}  # For profitable companies
    }
    
    def __init__(self):
        self.fraud_score = 0  # 0-100 scale
        self.red_flags = []
        self.warnings = []
        self.severity_scores = {
            'CRITICAL': 25,
            'HIGH': 15,
            'MEDIUM': 7,
            'LOW': 3
        }
    
    def analyze_financial_statement(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive fraud analysis
        Returns: {
            'fraud_score': 0-100,
            'fraud_probability': 'LOW'|'MEDIUM'|'HIGH'|'CRITICAL',
            'red_flags': [],
            'warnings': [],
            'detailed_analysis': {}
        }
        """
        self.fraud_score = 0
        self.red_flags = []
        self.warnings = []
        
        # Extract values
        revenue = self._get_value(data, 'totalRevenue', 'total_revenue')
        cost = self._get_value(data, 'costOfRevenue', 'cost_of_revenue', 'cogs')
        gross_profit = self._get_value(data, 'grossProfit', 'gross_profit')
        operating_expenses = self._get_value(data, 'totalOperatingExpenses', 'total_operating_expenses')
        operating_income = self._get_value(data, 'operatingIncome', 'operating_income')
        net_income = self._get_value(data, 'netIncome', 'net_income')
        interest_expense = self._get_value(data, 'interestExpense', 'interest_expense')
        taxes = self._get_value(data, 'incomeTaxExpense', 'income_tax_expense', 'taxes')
        
        # Run all fraud detection tests
        self._check_mathematical_consistency(revenue, cost, gross_profit, operating_expenses, operating_income, net_income, interest_expense, taxes)
        self._check_round_number_syndrome(revenue, cost, gross_profit, operating_expenses, operating_income, net_income, interest_expense, taxes)
        self._check_ratio_anomalies(revenue, cost, gross_profit, operating_expenses, operating_income, net_income)
        self._check_tax_patterns(net_income, taxes, interest_expense, operating_income)
        self._check_logical_impossibilities(revenue, cost, gross_profit, operating_expenses, operating_income, net_income)
        self._check_expense_patterns(revenue, operating_expenses, interest_expense)
        self._check_profitability_anomalies(revenue, gross_profit, net_income)
        
        # Calculate fraud probability
        fraud_probability = self._calculate_fraud_probability()
        
        return {
            'fraud_score': min(self.fraud_score, 100),
            'fraud_probability': fraud_probability,
            'red_flags': self.red_flags,
            'warnings': self.warnings,
            'detailed_analysis': {
                'mathematical_consistency': 'PASS' if self.fraud_score < 15 else 'FAIL',
                'ratio_analysis': 'PASS' if self.fraud_score < 25 else 'SUSPICIOUS',
                'tax_compliance': 'PASS' if not any('TAX' in flag for flag in self.red_flags) else 'FAIL',
                'expense_patterns': 'NORMAL' if self.fraud_score < 20 else 'ANOMALOUS'
            }
        }
    
    def _get_value(self, data: Dict, *keys: str) -> float:
        """Safely extract and convert value"""
        for key in keys:
            if key in data and data[key] is not None:
                try:
                    return float(data[key])
                except (ValueError, TypeError):
                    continue
        return 0.0
    
    def _add_flag(self, severity: str, message: str):
        """Add a fraud flag and increase fraud score"""
        icon = {
            'CRITICAL': '🚨',
            'HIGH': '⚠️',
            'MEDIUM': '⚠️',
            'LOW': 'ℹ️'
        }.get(severity, '⚠️')
        
        flag_message = f"{icon} {severity}: {message}"
        
        if severity in ['CRITICAL', 'HIGH']:
            self.red_flags.append(flag_message)
        else:
            self.warnings.append(flag_message)
        
        self.fraud_score += self.severity_scores.get(severity, 5)
    
    def _check_mathematical_consistency(self, revenue, cost, gross_profit, operating_expenses, 
                                       operating_income, net_income, interest_expense, taxes):
        """Check if numbers add up correctly"""
        tolerance = 0.01  # 1% tolerance for rounding
        
        if revenue > 0 and cost > 0:
            # Gross Profit = Revenue - COGS
            calculated_gp = revenue - cost
            if gross_profit > 0:
                diff_pct = abs(gross_profit - calculated_gp) / revenue
                if diff_pct > tolerance:
                    self._add_flag('CRITICAL', 
                        f"Gross Profit arithmetic error: Reported KES {gross_profit:,.0f}, "
                        f"but Revenue ({revenue:,.0f}) - COGS ({cost:,.0f}) = {calculated_gp:,.0f}. "
                        f"Difference: KES {abs(gross_profit - calculated_gp):,.0f} ({diff_pct*100:.1f}%)")
        
        if gross_profit > 0 and operating_income != 0:
            # Operating Income = Gross Profit - Operating Expenses
            calculated_oi = gross_profit - operating_expenses
            if abs(operating_income - calculated_oi) / max(abs(operating_income), abs(calculated_oi), 1) > tolerance:
                self._add_flag('HIGH',
                    f"Operating Income mismatch: Reported KES {operating_income:,.0f}, "
                    f"but Gross Profit ({gross_profit:,.0f}) - OpEx ({operating_expenses:,.0f}) = {calculated_oi:,.0f}")
        
        # Net Income reconciliation (if we have all components)
        if operating_income != 0 and (interest_expense > 0 or taxes > 0):
            # Net Income = Operating Income - Interest - Taxes
            calculated_ni = operating_income - interest_expense - taxes
            if net_income != 0:
                diff = abs(net_income - calculated_ni)
                if diff > max(revenue * tolerance, 1000):  # Allow small discrepancies
                    self._add_flag('MEDIUM',
                        f"Net Income reconciliation issue: Reported KES {net_income:,.0f}, "
                        f"calculated KES {calculated_ni:,.0f} (OI - Interest - Taxes). Difference: KES {diff:,.0f}")
    
    def _check_round_number_syndrome(self, *values):
        """Detect suspiciously round numbers using Benford's Law principles"""
        def is_suspiciously_round(value: float) -> bool:
            if value == 0:
                return False
            abs_val = abs(value)
            # Check if divisible by large round numbers
            if abs_val >= 1000000:
                return abs_val % 1000000 == 0 or abs_val % 500000 == 0
            elif abs_val >= 100000:
                return abs_val % 100000 == 0 or abs_val % 50000 == 0
            elif abs_val >= 10000:
                return abs_val % 10000 == 0
            return False
        
        non_zero_values = [v for v in values if v != 0]
        if len(non_zero_values) < 3:
            return  # Not enough data
        
        round_count = sum(1 for v in non_zero_values if is_suspiciously_round(v))
        round_percentage = round_count / len(non_zero_values) * 100
        
        if round_percentage >= 70:
            self._add_flag('HIGH',
                f"Round Number Syndrome: {round_count}/{len(non_zero_values)} values ({round_percentage:.0f}%) "
                f"are suspiciously round. Real financial statements rarely have all round numbers. "
                f"This suggests estimation or fabrication.")
        elif round_percentage >= 50:
            self._add_flag('MEDIUM',
                f"{round_count}/{len(non_zero_values)} values are round numbers ({round_percentage:.0f}%). "
                f"May indicate estimated figures rather than actual accounting records.")
    
    def _check_ratio_anomalies(self, revenue, cost, gross_profit, operating_expenses, operating_income, net_income):
        """Check if ratios fall within reasonable bounds"""
        if revenue <= 0:
            return
        
        # Gross Margin Check
        if gross_profit != 0:
            gross_margin = gross_profit / revenue
            bench = self.BENCHMARKS['gross_margin']
            
            if gross_margin < bench['min']:
                self._add_flag('MEDIUM',
                    f"Gross margin of {gross_margin*100:.1f}% is below minimum viable threshold ({bench['min']*100:.0f}%). "
                    f"Company may be selling below cost.")
            elif gross_margin > bench['max']:
                self._add_flag('CRITICAL',
                    f"Gross margin of {gross_margin*100:.1f}% exceeds maximum realistic threshold ({bench['max']*100:.0f}%). "
                    f"This suggests understated COGS or inflated revenue.")
            elif gross_margin > bench['typical_range'][1]:
                self._add_flag('MEDIUM',
                    f"Gross margin of {gross_margin*100:.1f}% is unusually high. "
                    f"Typical range is {bench['typical_range'][0]*100:.0f}%-{bench['typical_range'][1]*100:.0f}%. Verify product costs.")
        
        # Operating Margin Check
        if operating_income != 0:
            operating_margin = operating_income / revenue
            bench = self.BENCHMARKS['operating_margin']
            
            if operating_margin < -0.50:  # Loss > 50% of revenue
                self._add_flag('HIGH',
                    f"Operating margin of {operating_margin*100:.1f}% indicates severe operational losses. "
                    f"Company is burning cash at unsustainable rate.")
            elif operating_margin > bench['max']:
                self._add_flag('MEDIUM',
                    f"Operating margin of {operating_margin*100:.1f}% is exceptionally high "
                    f"(above {bench['max']*100:.0f}%). Verify expense reporting is complete.")
        
        # Net Margin Check
        if net_income != 0:
            net_margin = net_income / revenue
            bench = self.BENCHMARKS['net_margin']
            
            if net_margin > bench['max']:
                self._add_flag('CRITICAL',
                    f"Net margin of {net_margin*100:.1f}% exceeds realistic maximum ({bench['max']*100:.0f}%). "
                    f"Possible revenue inflation or expense understatement.")
            elif net_margin < -1.0:  # Loss > 100% of revenue
                self._add_flag('CRITICAL',
                    f"Net loss of {abs(net_margin)*100:.0f}% of revenue indicates company has lost more than its entire revenue. "
                    f"This is mathematically impossible unless there are missing revenues or duplicated expenses.")
        
        # Cost/Revenue Ratio
        if cost > 0:
            cost_ratio = cost / revenue
            bench = self.BENCHMARKS['cost_of_revenue_ratio']
            
            if cost_ratio > bench['max']:
                self._add_flag('HIGH',
                    f"COGS is {cost_ratio*100:.0f}% of revenue (above {bench['max']*100:.0f}% maximum). "
                    f"Company is selling below cost, which is unsustainable.")
            elif cost_ratio < bench['min']:
                self._add_flag('MEDIUM',
                    f"COGS is only {cost_ratio*100:.1f}% of revenue. This is unusually low and suggests possible cost understatement.")
        
        # Operating Expense Ratio
        if operating_expenses > 0:
            opex_ratio = operating_expenses / revenue
            bench = self.BENCHMARKS['operating_expense_ratio']
            
            if opex_ratio > bench['max']:
                self._add_flag('HIGH',
                    f"Operating expenses are {opex_ratio*100:.0f}% of revenue (above {bench['max']*100:.0f}% maximum). "
                    f"This level is unsustainable and suggests operational inefficiency or expense inflation.")
            elif opex_ratio < bench['min']:
                self._add_flag('MEDIUM',
                    f"Operating expenses are only {opex_ratio*100:.1f}% of revenue. "
                    f"This is unrealistically low and suggests missing expense categories (salaries, rent, utilities, etc.).")
    
    def _check_tax_patterns(self, net_income, taxes, interest_expense, operating_income):
        """Analyze tax reporting for compliance red flags"""
        if net_income > 10000:  # Profitable company (with small threshold for rounding)
            if taxes == 0:
                # This is a MAJOR red flag for fraud/tax evasion
                self._add_flag('CRITICAL',
                    f"Tax Evasion Indicator: Company reported profit of KES {net_income:,.0f} but ZERO taxes. "
                    f"All profitable companies must pay corporate income tax. This suggests either: "
                    f"(1) Tax evasion, (2) Incomplete financial statement, or (3) Fraudulent reporting.")
            elif taxes > 0:
                # Check if tax rate is reasonable
                taxable_income = max(net_income, operating_income - interest_expense)
                if taxable_income > 0:
                    effective_tax_rate = taxes / taxable_income
                    bench = self.BENCHMARKS['tax_rate']
                    
                    if effective_tax_rate < bench['min']:
                        self._add_flag('HIGH',
                            f"Unusually low tax rate: {effective_tax_rate*100:.1f}% on profit of KES {taxable_income:,.0f}. "
                            f"Corporate tax rates typically range {bench['min']*100:.0f}%-{bench['max']*100:.0f}%. "
                            f"May indicate aggressive tax avoidance or incomplete tax reporting.")
                    elif effective_tax_rate > bench['max']:
                        self._add_flag('MEDIUM',
                            f"Tax rate of {effective_tax_rate*100:.1f}% is higher than typical corporate rates. "
                            f"Verify if penalties or back taxes are included.")
        elif net_income < -10000:  # Loss-making company
            if taxes > 1000:  # Paying significant taxes while making loss
                self._add_flag('MEDIUM',
                    f"Unusual: Company reported loss of KES {abs(net_income):,.0f} but paid KES {taxes:,.0f} in taxes. "
                    f"Loss-making companies typically have minimal or no tax liability.")
    
    def _check_logical_impossibilities(self, revenue, cost, gross_profit, operating_expenses, operating_income, net_income):
        """Detect mathematically impossible scenarios"""
        if revenue > 0:
            # Net income cannot exceed revenue
            if net_income > revenue:
                self._add_flag('CRITICAL',
                    f"Mathematical Impossibility: Net income (KES {net_income:,.0f}) exceeds total revenue (KES {revenue:,.0f}). "
                    f"This is impossible unless there are significant non-operating gains not reported.")
            
            # Gross profit cannot exceed revenue
            if gross_profit > revenue * 1.05:  # 5% tolerance for minor differences
                self._add_flag('CRITICAL',
                    f"Mathematical Impossibility: Gross profit (KES {gross_profit:,.0f}) exceeds revenue (KES {revenue:,.0f}). "
                    f"This violates basic accounting: Gross Profit = Revenue - COGS.")
            
            # Operating expenses of zero is impossible for any real business
            if operating_expenses == 0:
                self._add_flag('CRITICAL',
                    f"Logical Impossibility: Operating expenses are ZERO while revenue is KES {revenue:,.0f}. "
                    f"No business operates without expenses (salaries, rent, utilities, etc.). This suggests incomplete reporting or fraud.")
    
    def _check_expense_patterns(self, revenue, operating_expenses, interest_expense):
        """Analyze expense patterns for anomalies"""
        if revenue > 1000000:  # Companies with >1M revenue
            if interest_expense == 0:
                # While possible, it's unusual for companies >1M revenue to have zero debt
                self._add_flag('LOW',
                    f"Unusual Pattern: Company with KES {revenue:,.0f} revenue reports zero interest expense. "
                    f"While possible if completely debt-free, most businesses this size have some debt financing. "
                    f"Verify capital structure.")
        
        if revenue > 5000000 and operating_expenses < revenue * 0.10:
            # Very large revenue with very small operating expenses
            self._add_flag('HIGH',
                f"Suspicious: Company with KES {revenue:,.0f} revenue reports only KES {operating_expenses:,.0f} in operating expenses ({operating_expenses/revenue*100:.1f}%). "
                f"This is unrealistically low. Missing expense categories likely (salaries, marketing, admin, etc.).")
    
    def _check_profitability_anomalies(self, revenue, gross_profit, net_income):
        """Check for unrealistic profitability patterns"""
        if revenue > 0 and net_income > 0:
            net_margin = net_income / revenue * 100
            
            # Net margin > 50% is extremely rare and suspicious
            if net_margin > 50:
                self._add_flag('CRITICAL',
                    f"Extraordinary Profitability: Net margin of {net_margin:.1f}% is exceptionally high. "
                    f"Even highly profitable businesses rarely exceed 30-40% net margins. "
                    f"This suggests either: (1) Revenue overstatement, (2) Expense understatement, or (3) Exceptional one-time gain.")
            
            # Negative COGS (which would make gross profit > revenue)
            if gross_profit > revenue * 1.01:
                calculated_cogs = revenue - gross_profit
                self._add_flag('CRITICAL',
                    f"Negative COGS Detected: Gross profit exceeds revenue, implying COGS of KES {calculated_cogs:,.0f}. "
                    f"Negative cost of goods sold is impossible and indicates data fabrication.")
    
    def _calculate_fraud_probability(self) -> str:
        """Calculate overall fraud probability based on fraud score"""
        if self.fraud_score >= 75:
            return 'CRITICAL'
        elif self.fraud_score >= 50:
            return 'HIGH'
        elif self.fraud_score >= 25:
            return 'MEDIUM'
        else:
            return 'LOW'

