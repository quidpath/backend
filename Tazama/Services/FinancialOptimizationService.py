# FinancialOptimizationService.py - Advanced Financial Optimization Service
"""
Comprehensive financial optimization service for Tazama
Integrates cash flow and cost optimization with ML predictions
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from decimal import Decimal

from Tazama.core.cash_flow_optimizer import CashFlowOptimizer, CostOptimizationEngine
from Tazama.core.TazamaCore import EnhancedFinancialOptimizer
from Tazama.models import TazamaAnalysisRequest, ProcessedFinancialData

logger = logging.getLogger(__name__)


class AdvancedFinancialOptimizationService:
    """Advanced financial optimization service combining ML and optimization algorithms"""
    
    def __init__(self):
        self.cash_optimizer = CashFlowOptimizer()
        self.cost_optimizer = CostOptimizationEngine()
        self.ml_optimizer = None  # Will be set when ML model is available
    
    def comprehensive_financial_optimization(self, financial_data: Dict, ml_predictions: Dict = None) -> Dict:
        """
        Comprehensive financial optimization analysis combining:
        - ML predictions
        - Cash flow optimization
        - Cost optimization
        - Risk assessment
        - Strategic recommendations
        """
        optimization_results = {
            'executive_summary': {},
            'cash_flow_optimization': {},
            'cost_optimization': {},
            'ml_insights': {},
            'strategic_recommendations': {},
            'implementation_roadmap': {},
            'risk_assessment': {},
            'financial_forecast': {},
            'optimization_score': 0
        }
        
        try:
            # 1. Cash Flow Optimization Analysis
            cash_opportunities = self.cash_optimizer.analyze_cash_flow_opportunities(financial_data)
            optimization_results['cash_flow_optimization'] = cash_opportunities
            
            # 2. Cost Optimization Analysis
            cost_opportunities = self.cost_optimizer.analyze_cost_optimization(financial_data)
            optimization_results['cost_optimization'] = cost_opportunities
            
            # 3. ML-Enhanced Insights
            if ml_predictions:
                ml_insights = self._generate_ml_enhanced_insights(financial_data, ml_predictions)
                optimization_results['ml_insights'] = ml_insights
            
            # 4. Strategic Recommendations
            strategic_recs = self._generate_strategic_recommendations(
                financial_data, cash_opportunities, cost_opportunities, ml_predictions
            )
            optimization_results['strategic_recommendations'] = strategic_recs
            
            # 5. Implementation Roadmap
            roadmap = self._create_implementation_roadmap(strategic_recs)
            optimization_results['implementation_roadmap'] = roadmap
            
            # 6. Risk Assessment
            risk_assessment = self._assess_optimization_risks(financial_data, strategic_recs)
            optimization_results['risk_assessment'] = risk_assessment
            
            # 7. Financial Forecast
            forecast = self._generate_optimized_forecast(financial_data, strategic_recs)
            optimization_results['financial_forecast'] = forecast
            
            # 8. Executive Summary
            optimization_results['executive_summary'] = self._generate_executive_summary(
                cash_opportunities, cost_opportunities, strategic_recs
            )
            
            # 9. Overall Optimization Score
            optimization_results['optimization_score'] = self._calculate_optimization_score(
                cash_opportunities, cost_opportunities, strategic_recs
            )
            
        except Exception as e:
            logger.error(f"Error in comprehensive optimization: {e}")
            optimization_results['error'] = str(e)
        
        return optimization_results
    
    def _generate_ml_enhanced_insights(self, financial_data: Dict, ml_predictions: Dict) -> Dict:
        """Generate ML-enhanced insights for optimization"""
        insights = {
            'prediction_confidence': {},
            'trend_analysis': {},
            'anomaly_detection': {},
            'optimization_opportunities': {}
        }
        
        # Analyze prediction confidence
        confidence_scores = ml_predictions.get('confidence_scores', {})
        insights['prediction_confidence'] = {
            'average_confidence': np.mean(list(confidence_scores.values())) if confidence_scores else 0,
            'low_confidence_metrics': [k for k, v in confidence_scores.items() if v < 0.7],
            'high_confidence_metrics': [k for k, v in confidence_scores.items() if v > 0.9]
        }
        
        # Trend analysis based on predictions
        predictions = ml_predictions.get('predictions', {})
        insights['trend_analysis'] = self._analyze_financial_trends(predictions)
        
        # Anomaly detection
        insights['anomaly_detection'] = self._detect_financial_anomalies(financial_data, predictions)
        
        # ML-driven optimization opportunities
        insights['optimization_opportunities'] = self._identify_ml_optimization_opportunities(
            financial_data, predictions
        )
        
        return insights
    
    def _analyze_financial_trends(self, predictions: Dict) -> Dict:
        """Analyze financial trends from ML predictions"""
        trends = {
            'profitability_trend': 'stable',
            'efficiency_trend': 'stable',
            'growth_potential': 'medium',
            'risk_factors': []
        }
        
        profit_margin = predictions.get('profit_margin', 0)
        operating_margin = predictions.get('operating_margin', 0)
        cost_ratio = predictions.get('cost_revenue_ratio', 0)
        
        # Profitability trend analysis
        if profit_margin > 0.15:
            trends['profitability_trend'] = 'improving'
            trends['growth_potential'] = 'high'
        elif profit_margin < 0.05:
            trends['profitability_trend'] = 'declining'
            trends['risk_factors'].append('Low profitability')
        
        # Efficiency trend analysis
        if cost_ratio < 0.6:
            trends['efficiency_trend'] = 'improving'
        elif cost_ratio > 0.8:
            trends['efficiency_trend'] = 'declining'
            trends['risk_factors'].append('High cost structure')
        
        return trends
    
    def _detect_financial_anomalies(self, financial_data: Dict, predictions: Dict) -> Dict:
        """Detect financial anomalies that require attention"""
        anomalies = {
            'detected_anomalies': [],
            'severity': 'low',
            'recommendations': []
        }
        
        revenue = float(financial_data.get('totalRevenue', 0))
        net_income = float(financial_data.get('netIncome', 0))
        
        # Revenue anomalies
        if revenue > 0:
            profit_margin = net_income / revenue
            
            if profit_margin < -0.1:  # Loss > 10% of revenue
                anomalies['detected_anomalies'].append({
                    'type': 'severe_loss',
                    'description': f'Net loss of {abs(profit_margin):.1%} of revenue',
                    'severity': 'critical'
                })
                anomalies['severity'] = 'critical'
            
            elif profit_margin < 0:
                anomalies['detected_anomalies'].append({
                    'type': 'operating_loss',
                    'description': f'Operating at a loss of {abs(profit_margin):.1%}',
                    'severity': 'high'
                })
                if anomalies['severity'] == 'low':
                    anomalies['severity'] = 'high'
        
        return anomalies
    
    def _identify_ml_optimization_opportunities(self, financial_data: Dict, predictions: Dict) -> List[Dict]:
        """Identify optimization opportunities based on ML predictions"""
        opportunities = []
        
        profit_margin = predictions.get('profit_margin', 0)
        operating_margin = predictions.get('operating_margin', 0)
        cost_ratio = predictions.get('cost_revenue_ratio', 0)
        
        # Profit margin optimization
        if profit_margin < 0.1:
            opportunities.append({
                'type': 'profitability_improvement',
                'priority': 'HIGH',
                'action': 'Enhance Profit Margins',
                'description': f'Current margin: {profit_margin:.1%}, Target: 15%+',
                'ml_insight': 'ML model predicts low profitability',
                'potential_impact': 'Increase net income by 20-30%',
                'implementation': 'Pricing optimization, cost reduction, operational efficiency'
            })
        
        # Cost structure optimization
        if cost_ratio > 0.7:
            opportunities.append({
                'type': 'cost_structure_optimization',
                'priority': 'HIGH',
                'action': 'Optimize Cost Structure',
                'description': f'Cost ratio: {cost_ratio:.1%}, Target: <60%',
                'ml_insight': 'ML model indicates high cost structure',
                'potential_impact': 'Reduce costs by 10-15%',
                'implementation': 'Supply chain optimization, process improvement, automation'
            })
        
        return opportunities
    
    def _generate_strategic_recommendations(self, financial_data: Dict, cash_ops: Dict, 
                                          cost_ops: Dict, ml_predictions: Dict = None) -> Dict:
        """Generate comprehensive strategic recommendations"""
        recommendations = {
            'immediate_actions': [],
            'short_term_initiatives': [],
            'long_term_strategies': [],
            'quick_wins': [],
            'transformation_initiatives': []
        }
        
        # Immediate actions (0-3 months)
        immediate_actions = []
        
        # Cash flow quick wins
        if 'immediate_cash_release' in cash_ops:
            for rec in cash_ops['immediate_cash_release']:
                if rec.get('priority') == 'CRITICAL':
                    immediate_actions.append(rec)
        
        # Cost reduction quick wins
        if 'immediate_savings' in cost_ops:
            immediate_actions.extend(cost_ops['immediate_savings'])
        
        recommendations['immediate_actions'] = immediate_actions
        
        # Short-term initiatives (3-12 months)
        short_term = []
        
        # Working capital optimization
        if 'working_capital_optimization' in cash_ops:
            short_term.extend(cash_ops['working_capital_optimization'])
        
        # Operational efficiency
        if 'operational_efficiency' in cost_ops:
            short_term.extend(cost_ops['operational_efficiency'])
        
        recommendations['short_term_initiatives'] = short_term
        
        # Long-term strategies (12+ months)
        long_term = []
        
        # Strategic initiatives
        if ml_predictions:
            profit_margin = ml_predictions.get('predictions', {}).get('profit_margin', 0)
            if profit_margin < 0.1:
                long_term.append({
                    'type': 'strategic_transformation',
                    'priority': 'HIGH',
                    'action': 'Business Model Optimization',
                    'description': 'Comprehensive business model review and optimization',
                    'timeline': '12-18 months',
                    'potential_impact': 'Transform profitability and competitive position'
                })
        
        recommendations['long_term_strategies'] = long_term
        
        # Quick wins (0-1 month)
        quick_wins = []
        for rec in immediate_actions:
            if rec.get('timeline', '').lower() in ['immediate', '1-2 weeks', '1 month']:
                quick_wins.append(rec)
        
        recommendations['quick_wins'] = quick_wins
        
        return recommendations
    
    def _create_implementation_roadmap(self, recommendations: Dict) -> Dict:
        """Create detailed implementation roadmap"""
        roadmap = {
            'phase_1_immediate': {
                'timeline': '0-3 months',
                'initiatives': recommendations.get('immediate_actions', []),
                'success_metrics': ['Cash flow improvement', 'Cost reduction achieved'],
                'resources_required': 'Internal team + minimal external support'
            },
            'phase_2_short_term': {
                'timeline': '3-12 months',
                'initiatives': recommendations.get('short_term_initiatives', []),
                'success_metrics': ['Working capital optimization', 'Operational efficiency gains'],
                'resources_required': 'Cross-functional teams + process consultants'
            },
            'phase_3_long_term': {
                'timeline': '12+ months',
                'initiatives': recommendations.get('long_term_strategies', []),
                'success_metrics': ['Strategic transformation', 'Sustainable competitive advantage'],
                'resources_required': 'Strategic consultants + major investments'
            }
        }
        
        return roadmap
    
    def _assess_optimization_risks(self, financial_data: Dict, recommendations: Dict) -> Dict:
        """Assess risks associated with optimization initiatives"""
        risk_assessment = {
            'implementation_risks': [],
            'financial_risks': [],
            'operational_risks': [],
            'overall_risk_level': 'LOW',
            'mitigation_strategies': []
        }
        
        # Implementation risks
        risk_assessment['implementation_risks'] = [
            {
                'risk': 'Change management resistance',
                'probability': 'MEDIUM',
                'impact': 'MEDIUM',
                'mitigation': 'Strong communication, training, and gradual implementation'
            },
            {
                'risk': 'Resource constraints',
                'probability': 'LOW',
                'impact': 'HIGH',
                'mitigation': 'Phased approach, external support, priority management'
            }
        ]
        
        # Financial risks
        risk_assessment['financial_risks'] = [
            {
                'risk': 'Cash flow disruption during implementation',
                'probability': 'LOW',
                'impact': 'HIGH',
                'mitigation': 'Maintain adequate cash reserves, gradual changes'
            }
        ]
        
        # Determine overall risk level
        high_risk_count = sum(1 for risk in risk_assessment['implementation_risks'] + risk_assessment['financial_risks'] 
                            if risk.get('probability') == 'HIGH' or risk.get('impact') == 'HIGH')
        
        if high_risk_count > 2:
            risk_assessment['overall_risk_level'] = 'HIGH'
        elif high_risk_count > 0:
            risk_assessment['overall_risk_level'] = 'MEDIUM'
        
        return risk_assessment
    
    def _generate_optimized_forecast(self, financial_data: Dict, recommendations: Dict) -> Dict:
        """Generate financial forecast with optimization scenarios"""
        revenue = float(financial_data.get('totalRevenue', 0))
        
        if revenue == 0:
            return {'error': 'Insufficient data for forecasting'}
        
        # Base case (current performance)
        base_case = {
            'revenue_growth': 0.05,  # 5% annual growth
            'profit_margin': 0.08,   # 8% profit margin
            'cost_ratio': 0.75       # 75% cost ratio
        }
        
        # Optimized case (with improvements)
        optimized_case = {
            'revenue_growth': 0.08,  # 8% annual growth
            'profit_margin': 0.15,   # 15% profit margin
            'cost_ratio': 0.65       # 65% cost ratio
        }
        
        # Generate 3-year forecast
        forecast = {
            'base_case': self._calculate_forecast_scenario(revenue, base_case, 3),
            'optimized_case': self._calculate_forecast_scenario(revenue, optimized_case, 3),
            'improvement_potential': {}
        }
        
        # Calculate improvement potential
        base_3yr_revenue = forecast['base_case']['year_3']['revenue']
        opt_3yr_revenue = forecast['optimized_case']['year_3']['revenue']
        
        forecast['improvement_potential'] = {
            'additional_revenue_3yr': opt_3yr_revenue - base_3yr_revenue,
            'additional_profit_3yr': forecast['optimized_case']['year_3']['net_income'] - forecast['base_case']['year_3']['net_income'],
            'roi_percentage': ((opt_3yr_revenue - base_3yr_revenue) / base_3yr_revenue) * 100
        }
        
        return forecast
    
    def _calculate_forecast_scenario(self, base_revenue: float, scenario: Dict, years: int) -> Dict:
        """Calculate forecast scenario"""
        forecast = {}
        
        current_revenue = base_revenue
        for year in range(1, years + 1):
            # Calculate metrics for this year
            current_revenue *= (1 + scenario['revenue_growth'])
            gross_profit = current_revenue * (1 - scenario['cost_ratio'])
            net_income = gross_profit * scenario['profit_margin']
            
            forecast[f'year_{year}'] = {
                'revenue': current_revenue,
                'gross_profit': gross_profit,
                'net_income': net_income,
                'profit_margin': scenario['profit_margin'],
                'cost_ratio': scenario['cost_ratio']
            }
        
        return forecast
    
    def _generate_executive_summary(self, cash_ops: Dict, cost_ops: Dict, strategic_recs: Dict) -> Dict:
        """Generate executive summary of optimization opportunities"""
        summary = {
            'total_optimization_potential': 0,
            'key_opportunities': [],
            'implementation_priority': 'MEDIUM',
            'expected_roi': 0,
            'timeline': '6-12 months'
        }
        
        # Calculate total potential
        cash_potential = cash_ops.get('optimization_potential', {}).get('total_potential_cash_release', 0)
        cost_potential = cost_ops.get('total_savings_potential', {}).get('total_annual_savings', 0)
        
        summary['total_optimization_potential'] = cash_potential + cost_potential
        
        # Key opportunities
        key_opportunities = []
        
        # Cash flow opportunities
        if cash_potential > 0:
            key_opportunities.append({
                'category': 'Cash Flow Optimization',
                'potential': f'${cash_potential:,.0f}',
                'description': 'Improve working capital and cash conversion cycle'
            })
        
        # Cost optimization opportunities
        if cost_potential > 0:
            key_opportunities.append({
                'category': 'Cost Optimization',
                'potential': f'${cost_potential:,.0f}',
                'description': 'Reduce operational costs and improve efficiency'
            })
        
        summary['key_opportunities'] = key_opportunities
        
        # Determine implementation priority
        total_potential = summary['total_optimization_potential']
        if total_potential > 100000:  # $100k+ potential
            summary['implementation_priority'] = 'HIGH'
        elif total_potential > 50000:  # $50k+ potential
            summary['implementation_priority'] = 'MEDIUM'
        else:
            summary['implementation_priority'] = 'LOW'
        
        # Calculate expected ROI
        if total_potential > 0:
            summary['expected_roi'] = min(300, (total_potential / 100000) * 100)  # Cap at 300%
        
        return summary
    
    def _calculate_optimization_score(self, cash_ops: Dict, cost_ops: Dict, strategic_recs: Dict) -> int:
        """Calculate overall optimization score (0-100)"""
        score = 0
        
        # Cash flow optimization score (40% weight)
        cash_score = 0
        if 'optimization_potential' in cash_ops:
            potential = cash_ops['optimization_potential'].get('optimization_score', 0)
            cash_score = min(40, potential * 0.4)
        
        # Cost optimization score (40% weight)
        cost_score = 0
        if 'total_savings_potential' in cost_ops:
            savings = cost_ops['total_savings_potential'].get('savings_percentage', 0)
            cost_score = min(40, savings * 2)  # 2x multiplier for percentage
        
        # Strategic recommendations score (20% weight)
        strategic_score = 0
        total_recommendations = sum(len(recs) for recs in strategic_recs.values() if isinstance(recs, list))
        if total_recommendations > 0:
            strategic_score = min(20, total_recommendations * 2)
        
        score = int(cash_score + cost_score + strategic_score)
        return min(100, score)
    
    def generate_optimization_report(self, optimization_results: Dict) -> str:
        """Generate comprehensive optimization report"""
        report = f"""
# TAZAMA FINANCIAL OPTIMIZATION REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## EXECUTIVE SUMMARY
Optimization Score: {optimization_results.get('optimization_score', 0)}/100
Priority Level: {optimization_results.get('executive_summary', {}).get('implementation_priority', 'MEDIUM')}
Total Potential: ${optimization_results.get('executive_summary', {}).get('total_optimization_potential', 0):,.0f}

## KEY OPPORTUNITIES
"""
        
        # Add key opportunities
        for opp in optimization_results.get('executive_summary', {}).get('key_opportunities', []):
            report += f"- {opp['category']}: {opp['potential']} - {opp['description']}\n"
        
        # Add implementation roadmap
        roadmap = optimization_results.get('implementation_roadmap', {})
        if roadmap:
            report += "\n## IMPLEMENTATION ROADMAP\n"
            for phase, details in roadmap.items():
                report += f"\n### {phase.replace('_', ' ').title()}\n"
                report += f"Timeline: {details.get('timeline', 'N/A')}\n"
                report += f"Success Metrics: {', '.join(details.get('success_metrics', []))}\n"
        
        return report
