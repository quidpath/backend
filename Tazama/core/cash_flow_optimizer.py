# cash_flow_optimizer.py - Advanced Cash Flow Optimization Engine
"""
Advanced cash flow optimization algorithms for Tazama
Provides intelligent cash management recommendations
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class CashFlowOptimizer:
    """Advanced cash flow optimization engine"""
    
    def __init__(self):
        self.optimization_strategies = {
            'working_capital': self._optimize_working_capital,
            'cash_conversion': self._optimize_cash_conversion_cycle,
            'liquidity_management': self._optimize_liquidity_management,
            'payment_terms': self._optimize_payment_terms,
            'inventory_optimization': self._optimize_inventory_management
        }
    
    def analyze_cash_flow_opportunities(self, financial_data: Dict) -> Dict:
        """
        Comprehensive cash flow optimization analysis
        """
        opportunities = {
            'immediate_cash_release': [],
            'working_capital_optimization': [],
            'payment_optimization': [],
            'inventory_optimization': [],
            'receivables_optimization': [],
            'payables_optimization': [],
            'cash_forecasting': {},
            'liquidity_ratios': {},
            'optimization_potential': {}
        }
        
        # Analyze each optimization area
        for strategy_name, strategy_func in self.optimization_strategies.items():
            try:
                result = strategy_func(financial_data)
                opportunities[f'{strategy_name}_recommendations'] = result
            except Exception as e:
                logger.error(f"Error in {strategy_name} optimization: {e}")
        
        # Calculate overall optimization potential
        opportunities['optimization_potential'] = self._calculate_optimization_potential(
            financial_data, opportunities
        )
        
        return opportunities
    
    def _optimize_working_capital(self, data: Dict) -> List[Dict]:
        """Optimize working capital management"""
        recommendations = []
        
        revenue = float(data.get('totalRevenue', 0))
        current_assets = float(data.get('currentAssets', 0))
        current_liabilities = float(data.get('currentLiabilities', 0))
        
        if revenue > 0 and current_assets > 0:
            # Working capital ratio optimization
            current_ratio = current_assets / max(current_liabilities, 1)
            
            if current_ratio > 2.5:
                excess_cash = (current_ratio - 2.0) * current_liabilities
                recommendations.append({
                    'type': 'excess_liquidity',
                    'priority': 'HIGH',
                    'action': 'Deploy Excess Cash',
                    'description': f'Excess liquidity of ${excess_cash:,.0f} can be invested or used for growth',
                    'potential_impact': f'Investment return of 5-8% annually on ${excess_cash:,.0f}',
                    'timeline': '1-3 months',
                    'implementation': 'Consider short-term investments, debt reduction, or growth initiatives'
                })
            
            elif current_ratio < 1.5:
                recommendations.append({
                    'type': 'liquidity_risk',
                    'priority': 'CRITICAL',
                    'action': 'Improve Liquidity Position',
                    'description': 'Low current ratio indicates potential liquidity constraints',
                    'potential_impact': 'Prevent cash flow crises and improve credit rating',
                    'timeline': 'Immediate',
                    'implementation': 'Accelerate receivables collection, extend payables, secure credit line'
                })
        
        return recommendations
    
    def _optimize_cash_conversion_cycle(self, data: Dict) -> List[Dict]:
        """Optimize cash conversion cycle"""
        recommendations = []
        
        # Calculate key metrics
        revenue = float(data.get('totalRevenue', 0))
        cogs = float(data.get('costOfRevenue', 0))
        
        if revenue > 0:
            # Days Sales Outstanding (DSO) optimization
            avg_daily_sales = revenue / 365
            target_dso = 30  # Industry standard
            
            recommendations.append({
                'type': 'receivables_optimization',
                'priority': 'HIGH',
                'action': 'Accelerate Receivables Collection',
                'description': f'Target DSO of {target_dso} days to improve cash flow',
                'potential_impact': f'Cash release of ${avg_daily_sales * target_dso:,.0f}',
                'timeline': '2-4 months',
                'implementation': 'Implement early payment discounts, improve invoicing process, credit management'
            })
            
            # Inventory optimization
            if cogs > 0:
                inventory_turnover = cogs / max(float(data.get('inventory', 0)), 1)
                target_turnover = 6  # Industry benchmark
                
                if inventory_turnover < target_turnover:
                    recommendations.append({
                        'type': 'inventory_optimization',
                        'priority': 'MEDIUM',
                        'action': 'Improve Inventory Turnover',
                        'description': f'Current turnover: {inventory_turnover:.1f}x, Target: {target_turnover}x',
                        'potential_impact': f'Reduce inventory by ${(cogs / target_turnover) - (cogs / inventory_turnover):,.0f}',
                        'timeline': '3-6 months',
                        'implementation': 'Implement JIT inventory, improve demand forecasting, vendor management'
                    })
        
        return recommendations
    
    def _optimize_liquidity_management(self, data: Dict) -> List[Dict]:
        """Optimize liquidity management strategies"""
        recommendations = []
        
        revenue = float(data.get('totalRevenue', 0))
        cash_balance = float(data.get('cashAndCashEquivalents', 0))
        
        if revenue > 0:
            # Cash ratio analysis
            cash_ratio = cash_balance / max(revenue / 12, 1)  # Monthly revenue
            
            if cash_ratio > 3:
                recommendations.append({
                    'type': 'excess_cash',
                    'priority': 'MEDIUM',
                    'action': 'Optimize Cash Holdings',
                    'description': f'Excess cash of ${cash_balance - (revenue / 4):,.0f} can be better utilized',
                    'potential_impact': 'Investment returns of 3-5% annually',
                    'timeline': '1-2 months',
                    'implementation': 'Consider money market funds, short-term bonds, or business investments'
                })
            
            elif cash_ratio < 1:
                recommendations.append({
                    'type': 'cash_shortage',
                    'priority': 'HIGH',
                    'action': 'Build Cash Reserves',
                    'description': 'Insufficient cash reserves for operational needs',
                    'potential_impact': 'Prevent cash flow crises and improve financial stability',
                    'timeline': '2-6 months',
                    'implementation': 'Improve collections, extend payables, secure credit facilities'
                })
        
        return recommendations
    
    def _optimize_payment_terms(self, data: Dict) -> List[Dict]:
        """Optimize payment terms for suppliers and customers"""
        recommendations = []
        
        revenue = float(data.get('totalRevenue', 0))
        payables = float(data.get('accountsPayable', 0))
        receivables = float(data.get('accountsReceivable', 0))
        
        if revenue > 0:
            # Payables optimization
            if payables > 0:
                recommendations.append({
                    'type': 'payables_optimization',
                    'priority': 'MEDIUM',
                    'action': 'Extend Payment Terms',
                    'description': 'Negotiate longer payment terms with suppliers',
                    'potential_impact': f'Free up ${payables * 0.1:,.0f} in working capital',
                    'timeline': '1-3 months',
                    'implementation': 'Renegotiate contracts, offer early payment discounts for better terms'
                })
            
            # Receivables optimization
            if receivables > 0:
                recommendations.append({
                    'type': 'receivables_optimization',
                    'priority': 'HIGH',
                    'action': 'Accelerate Customer Payments',
                    'description': 'Implement strategies to collect receivables faster',
                    'potential_impact': f'Improve cash flow by ${receivables * 0.2:,.0f}',
                    'timeline': '1-2 months',
                    'implementation': 'Offer early payment discounts, improve invoicing, credit checks'
                })
        
        return recommendations
    
    def _optimize_inventory_management(self, data: Dict) -> List[Dict]:
        """Optimize inventory management for cash flow"""
        recommendations = []
        
        cogs = float(data.get('costOfRevenue', 0))
        inventory = float(data.get('inventory', 0))
        
        if cogs > 0 and inventory > 0:
            # Calculate optimal inventory levels
            current_turnover = cogs / inventory
            target_turnover = 6  # Industry benchmark
            
            if current_turnover < target_turnover:
                optimal_inventory = cogs / target_turnover
                excess_inventory = inventory - optimal_inventory
                
                recommendations.append({
                    'type': 'inventory_reduction',
                    'priority': 'HIGH',
                    'action': 'Reduce Excess Inventory',
                    'description': f'Current inventory: ${inventory:,.0f}, Optimal: ${optimal_inventory:,.0f}',
                    'potential_impact': f'Cash release of ${excess_inventory:,.0f}',
                    'timeline': '2-4 months',
                    'implementation': 'Implement JIT, improve demand forecasting, liquidate slow-moving items'
                })
        
        return recommendations
    
    def _calculate_optimization_potential(self, data: Dict, opportunities: Dict) -> Dict:
        """Calculate total optimization potential"""
        revenue = float(data.get('totalRevenue', 0))
        
        # Estimate potential cash release
        potential_cash_release = 0
        
        # Working capital optimization
        if 'working_capital_optimization' in opportunities:
            for rec in opportunities['working_capital_optimization']:
                if 'excess_cash' in rec.get('type', ''):
                    potential_cash_release += revenue * 0.05  # 5% of revenue
        
        # Inventory optimization
        if 'inventory_optimization' in opportunities:
            for rec in opportunities['inventory_optimization']:
                if 'inventory_reduction' in rec.get('type', ''):
                    potential_cash_release += revenue * 0.03  # 3% of revenue
        
        return {
            'total_potential_cash_release': potential_cash_release,
            'optimization_score': min(100, (potential_cash_release / max(revenue, 1)) * 1000),
            'priority_actions': len([r for r in opportunities.get('immediate_cash_release', []) if r.get('priority') == 'CRITICAL']),
            'implementation_timeline': '3-6 months'
        }
    
    def generate_cash_flow_forecast(self, data: Dict, months: int = 12) -> Dict:
        """Generate cash flow forecast with optimization scenarios"""
        revenue = float(data.get('totalRevenue', 0))
        monthly_revenue = revenue / 12
        
        forecast = {
            'baseline_scenario': [],
            'optimized_scenario': [],
            'recommendations': []
        }
        
        # Generate monthly forecasts
        for month in range(1, months + 1):
            baseline_cash = monthly_revenue * 0.8  # 80% collection rate
            optimized_cash = monthly_revenue * 0.95  # 95% with optimization
            
            forecast['baseline_scenario'].append({
                'month': month,
                'cash_flow': baseline_cash,
                'cumulative': baseline_cash * month
            })
            
            forecast['optimized_scenario'].append({
                'month': month,
                'cash_flow': optimized_cash,
                'cumulative': optimized_cash * month
            })
        
        # Calculate improvement potential
        total_baseline = sum([m['cumulative'] for m in forecast['baseline_scenario']])
        total_optimized = sum([m['cumulative'] for m in forecast['optimized_scenario']])
        
        forecast['improvement_potential'] = {
            'additional_cash_flow': total_optimized - total_baseline,
            'improvement_percentage': ((total_optimized - total_baseline) / total_baseline) * 100
        }
        
        return forecast


class CostOptimizationEngine:
    """Advanced cost optimization algorithms"""
    
    def __init__(self):
        self.cost_categories = {
            'operational': self._optimize_operational_costs,
            'personnel': self._optimize_personnel_costs,
            'technology': self._optimize_technology_costs,
            'supply_chain': self._optimize_supply_chain_costs,
            'overhead': self._optimize_overhead_costs
        }
    
    def analyze_cost_optimization(self, financial_data: Dict) -> Dict:
        """Comprehensive cost optimization analysis"""
        recommendations = {
            'immediate_savings': [],
            'operational_efficiency': [],
            'technology_optimization': [],
            'supply_chain_optimization': [],
            'overhead_reduction': [],
            'total_savings_potential': {}
        }
        
        # Analyze each cost category
        for category, optimizer in self.cost_categories.items():
            try:
                result = optimizer(financial_data)
                recommendations[f'{category}_recommendations'] = result
            except Exception as e:
                logger.error(f"Error in {category} optimization: {e}")
        
        # Calculate total savings potential
        recommendations['total_savings_potential'] = self._calculate_savings_potential(
            financial_data, recommendations
        )
        
        return recommendations
    
    def _optimize_operational_costs(self, data: Dict) -> List[Dict]:
        """Optimize operational costs"""
        recommendations = []
        
        revenue = float(data.get('totalRevenue', 0))
        operating_expenses = float(data.get('totalOperatingExpenses', 0))
        
        if revenue > 0 and operating_expenses > 0:
            expense_ratio = operating_expenses / revenue
            
            if expense_ratio > 0.3:  # 30% threshold
                potential_savings = operating_expenses * 0.1  # 10% reduction
                
                recommendations.append({
                    'type': 'operational_efficiency',
                    'priority': 'HIGH',
                    'action': 'Reduce Operating Expenses',
                    'description': f'Current expense ratio: {expense_ratio:.1%}, Target: 25%',
                    'potential_savings': f'${potential_savings:,.0f} annually',
                    'timeline': '3-6 months',
                    'implementation': 'Process automation, vendor consolidation, energy efficiency'
                })
        
        return recommendations
    
    def _optimize_personnel_costs(self, data: Dict) -> List[Dict]:
        """Optimize personnel costs through efficiency"""
        recommendations = []
        
        revenue = float(data.get('totalRevenue', 0))
        
        if revenue > 0:
            # Estimate personnel costs (typically 20-40% of revenue)
            estimated_personnel_costs = revenue * 0.25
            
            recommendations.append({
                'type': 'personnel_optimization',
                'priority': 'MEDIUM',
                'action': 'Optimize Workforce Efficiency',
                'description': 'Improve productivity through training and automation',
                'potential_savings': f'${estimated_personnel_costs * 0.05:,.0f} annually',
                'timeline': '6-12 months',
                'implementation': 'Skills training, process improvement, technology adoption'
            })
        
        return recommendations
    
    def _optimize_technology_costs(self, data: Dict) -> List[Dict]:
        """Optimize technology and IT costs"""
        recommendations = []
        
        revenue = float(data.get('totalRevenue', 0))
        
        if revenue > 0:
            recommendations.append({
                'type': 'technology_optimization',
                'priority': 'MEDIUM',
                'action': 'Optimize Technology Stack',
                'description': 'Consolidate and optimize technology investments',
                'potential_savings': f'${revenue * 0.01:,.0f} annually',
                'timeline': '3-6 months',
                'implementation': 'Cloud migration, software consolidation, automation tools'
            })
        
        return recommendations
    
    def _optimize_supply_chain_costs(self, data: Dict) -> List[Dict]:
        """Optimize supply chain and procurement costs"""
        recommendations = []
        
        cogs = float(data.get('costOfRevenue', 0))
        
        if cogs > 0:
            recommendations.append({
                'type': 'supply_chain_optimization',
                'priority': 'HIGH',
                'action': 'Optimize Supply Chain',
                'description': 'Reduce procurement costs through better vendor management',
                'potential_savings': f'${cogs * 0.05:,.0f} annually',
                'timeline': '3-9 months',
                'implementation': 'Vendor consolidation, contract renegotiation, bulk purchasing'
            })
        
        return recommendations
    
    def _optimize_overhead_costs(self, data: Dict) -> List[Dict]:
        """Optimize overhead and administrative costs"""
        recommendations = []
        
        revenue = float(data.get('totalRevenue', 0))
        
        if revenue > 0:
            recommendations.append({
                'type': 'overhead_reduction',
                'priority': 'MEDIUM',
                'action': 'Reduce Administrative Overhead',
                'description': 'Streamline administrative processes and reduce overhead',
                'potential_savings': f'${revenue * 0.02:,.0f} annually',
                'timeline': '2-6 months',
                'implementation': 'Process automation, office space optimization, shared services'
            })
        
        return recommendations
    
    def _calculate_savings_potential(self, data: Dict, recommendations: Dict) -> Dict:
        """Calculate total savings potential"""
        revenue = float(data.get('totalRevenue', 0))
        total_savings = 0
        
        # Sum up all potential savings
        for category in ['operational', 'personnel', 'technology', 'supply_chain', 'overhead']:
            if f'{category}_recommendations' in recommendations:
                for rec in recommendations[f'{category}_recommendations']:
                    if 'potential_savings' in rec:
                        savings_str = rec['potential_savings'].replace('$', '').replace(',', '')
                        try:
                            savings = float(savings_str.split()[0])
                            total_savings += savings
                        except:
                            pass
        
        return {
            'total_annual_savings': total_savings,
            'savings_percentage': (total_savings / max(revenue, 1)) * 100,
            'payback_period': '6-12 months',
            'implementation_priority': 'HIGH' if total_savings > revenue * 0.05 else 'MEDIUM'
        }
