# report_generator.py - Enhanced Report Generation with HTML Templates
import os
from fpdf import FPDF
import json
import pandas as pd
from datetime import datetime
from django.conf import settings
from decimal import Decimal
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import logging

logger = logging.getLogger(__name__)


class TazamaReportGenerator:
    """Generate comprehensive financial analysis reports with multiple formats"""

    def __init__(self):
        self.reports_dir = os.path.join(settings.MEDIA_ROOT, 'financial_reports')
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_report(self, analysis_request, format_type='html'):
        """Generate report in specified format"""
        if format_type == 'html':
            return self.generate_html_report(analysis_request)
        elif format_type == 'pdf':
            return self._generate_pdf_report(analysis_request)
        elif format_type == 'json':
            return self._generate_json_report(analysis_request)
        elif format_type == 'excel':
            return self._generate_excel_report(analysis_request)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def generate_html_report(self, analysis_request):
        """Generate comprehensive HTML report with professional styling and optimization insights"""

        # Generate visualizations
        charts = self._generate_charts(analysis_request)

        # Get data
        predictions = analysis_request.predictions or {}
        recommendations = analysis_request.recommendations or {}
        risk_assessment = analysis_request.risk_assessment or {}
        confidence_scores = analysis_request.confidence_scores or {}
        optimization_analysis = getattr(analysis_request, 'optimization_analysis', {})

        # Format metric values
        def format_metric(value):
            try:
                num_val = float(value)
                return f"{num_val:.2%}"
            except:
                return str(value)

        # Build predictions HTML
        predictions_html = self._build_predictions_html(predictions, confidence_scores)

        # Build recommendations HTML
        recommendations_html = self._build_recommendations_html(recommendations)

        # Build risk assessment HTML
        risk_html, risk_factors_html = self._build_risk_html(risk_assessment)
        
        # Build optimization analysis HTML
        optimization_html = self._build_optimization_html(optimization_analysis)

        # Get risk factors count
        risk_factors = risk_assessment.get('risk_factors', [])
        total_recommendations = sum(len(v) if isinstance(v, list) else 0 for v in recommendations.values())

        # Complete HTML template
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tazama Financial Analysis Report</title>
    <style>
        {self._get_report_css()}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>Tazama Financial Analysis</h1>
            <div class="subtitle">AI-Powered Financial Intelligence Report</div>
            <div class="meta">
                <span>Generated: {analysis_request.created_at.strftime('%B %d, %Y at %I:%M %p')}</span> |
                <span>Processing Time: {float(analysis_request.processing_time_seconds or 0):.2f}s</span> |
                <span>Model: {analysis_request.model_used.name if analysis_request.model_used else 'N/A'}</span>
            </div>
        </div>

        <!-- Executive Summary -->
        <div class="section">
            <h2 class="section-title">Executive Summary</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-header">
                        <h3>Overall Risk</h3>
                    </div>
                    <div class="metric-value">{risk_assessment.get('overall_risk', 'N/A')}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-header">
                        <h3>Total Recommendations</h3>
                    </div>
                    <div class="metric-value">{total_recommendations}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-header">
                        <h3>Risk Factors</h3>
                    </div>
                    <div class="metric-value">{len(risk_factors)}</div>
                </div>
            </div>
        </div>

        <!-- Financial Predictions -->
        <div class="section">
            <h2 class="section-title">Financial Predictions</h2>
            <div class="metrics-grid">
                {predictions_html}
            </div>
            {charts.get('predictions', '')}
        </div>

        <!-- Recommendations -->
        <div class="section">
            <h2 class="section-title">Strategic Recommendations</h2>
            {recommendations_html}
        </div>

        <!-- Risk Assessment -->
        <div class="section">
            <h2 class="section-title">Risk Assessment</h2>
            <div class="risk-grid">
                {risk_html}
            </div>

            {f'''
            <div class="risk-factors">
                <h4>Identified Risk Factors</h4>
                <ul>
                    {risk_factors_html}
                </ul>
            </div>
            ''' if risk_factors_html else ''}
        </div>

        <!-- Financial Optimization Analysis -->
        {optimization_html}

        <!-- Footer -->
        <div class="footer">
            <div class="logo">Tazama</div>
            <p>AI-Powered Financial Intelligence for Small Businesses</p>
            <p style="margin-top: 10px; font-size: 0.9em;">
                &copy; 2025 Tazama. All rights reserved. | Confidential Report
            </p>
        </div>
    </div>
</body>
</html>
        """

        # Save HTML report
        filename = f"financial_analysis_{analysis_request.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(self.reports_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_template)

        return filepath, 'text/html'

    def _get_report_css(self):
        """Return CSS styling for HTML report"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }

        .header .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .header .meta {
            margin-top: 20px;
            font-size: 0.95em;
            opacity: 0.8;
        }

        .section {
            padding: 40px;
            border-bottom: 1px solid #e5e7eb;
        }

        .section:last-child {
            border-bottom: none;
        }

        .section-title {
            font-size: 1.8em;
            color: #1f2937;
            margin-bottom: 25px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .metric-card {
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }

        .metric-card.good {
            border-left-color: #10b981;
            background: #f0fdf4;
        }

        .metric-card.warning {
            border-left-color: #f59e0b;
            background: #fffbeb;
        }

        .metric-card.bad {
            border-left-color: #ef4444;
            background: #fef2f2;
        }

        .metric-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .metric-header h3 {
            font-size: 1em;
            color: #374151;
            font-weight: 600;
        }

        .confidence-badge {
            background: #667eea;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
        }

        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #1f2937;
            margin-bottom: 10px;
        }

        .metric-bar {
            background: #e5e7eb;
            height: 6px;
            border-radius: 3px;
            overflow: hidden;
        }

        .metric-bar-fill {
            background: #667eea;
            height: 100%;
            transition: width 1s ease-in-out;
        }

        .recommendation-category {
            margin-bottom: 30px;
        }

        .category-title {
            font-size: 1.3em;
            color: #667eea;
            margin-bottom: 15px;
            font-weight: 600;
        }

        .recommendation-card {
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }

        .recommendation-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 12px;
        }

        .priority-badge {
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
            text-transform: uppercase;
        }

        .recommendation-header h4 {
            font-size: 1.1em;
            color: #1f2937;
            flex: 1;
        }

        .recommendation-description {
            color: #4b5563;
            margin-bottom: 12px;
            line-height: 1.5;
        }

        .recommendation-footer {
            display: flex;
            gap: 20px;
            font-size: 0.9em;
            color: #6b7280;
        }

        .risk-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }

        .risk-item {
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .risk-label {
            font-weight: 600;
            color: #374151;
        }

        .risk-badge {
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
        }

        .risk-factors {
            background: #fef2f2;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #ef4444;
        }

        .risk-factors h4 {
            color: #991b1b;
            margin-bottom: 15px;
            font-size: 1.1em;
        }

        .risk-factors ul {
            list-style: none;
        }

        .risk-factor {
            padding: 10px;
            background: white;
            margin-bottom: 8px;
            border-radius: 4px;
            color: #7f1d1d;
            border-left: 3px solid #fca5a5;
        }

        .chart-container {
            margin: 30px 0;
            text-align: center;
        }

        .chart-container img {
            max-width: 100%;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }

        .footer {
            background: #f3f4f6;
            padding: 30px;
            text-align: center;
            color: #6b7280;
        }

        .footer .logo {
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }

        @media print {
            body {
                background: white;
                padding: 0;
            }
            .container {
                box-shadow: none;
            }
        }
        """

    def _build_predictions_html(self, predictions, confidence_scores):
        """Build HTML for predictions section"""
        predictions_html = ""

        for metric, value in predictions.items():
            confidence = confidence_scores.get(metric, 0.5)
            confidence_pct = f"{confidence * 100:.0f}%"

            metric_name = metric.replace('_', ' ').title()
            try:
                formatted_value = f"{float(value):.2%}"
            except:
                formatted_value = str(value)

            # Color coding based on value and metric type
            color_class = self._get_metric_color_class(metric, value)

            predictions_html += f"""
            <div class="metric-card {color_class}">
                <div class="metric-header">
                    <h3>{metric_name}</h3>
                    <span class="confidence-badge">Confidence: {confidence_pct}</span>
                </div>
                <div class="metric-value">{formatted_value}</div>
                <div class="metric-bar">
                    <div class="metric-bar-fill" style="width: {confidence * 100}%"></div>
                </div>
            </div>
            """

        return predictions_html

    def _get_metric_color_class(self, metric, value):
        """Determine color class based on metric type and value"""
        try:
            num_value = float(value)

            if 'margin' in metric:
                if num_value > 0.15:
                    return 'good'
                elif num_value > 0:
                    return 'warning'
                else:
                    return 'bad'
            elif 'ratio' in metric:
                if num_value < 0.6:
                    return 'good'
                elif num_value < 0.85:
                    return 'warning'
                else:
                    return 'bad'
            else:
                return 'neutral'
        except:
            return 'neutral'

    def _build_recommendations_html(self, recommendations):
        """Build HTML for recommendations section"""
        recommendations_html = ""

        priority_colors = {
            'CRITICAL': '#dc2626',
            'HIGH': '#ea580c',
            'MEDIUM': '#f59e0b',
            'LOW': '#10b981'
        }

        for category, recs in recommendations.items():
            if not recs or not isinstance(recs, list):
                continue

            category_name = category.replace('_', ' ').title()
            recommendations_html += f"""
            <div class="recommendation-category">
                <h3 class="category-title">{category_name}</h3>
            """

            for rec in recs:
                if not isinstance(rec, dict):
                    continue

                priority = str(rec.get('priority', 'MEDIUM')).upper()
                action = rec.get('action', rec.get('recommendation', 'N/A'))
                description = rec.get('description', '')
                timeline = rec.get('timeline', 'Not specified')
                impact = rec.get('potential_impact', rec.get('impact', rec.get('potential_savings', 'Not specified')))

                priority_color = priority_colors.get(priority, '#6b7280')

                recommendations_html += f"""
                <div class="recommendation-card">
                    <div class="recommendation-header">
                        <span class="priority-badge" style="background-color: {priority_color}">{priority}</span>
                        <h4>{action}</h4>
                    </div>
                    <p class="recommendation-description">{description}</p>
                    <div class="recommendation-footer">
                        <span><strong>Timeline:</strong> {timeline}</span>
                        <span><strong>Impact:</strong> {impact}</span>
                    </div>
                </div>
                """

            recommendations_html += "</div>"

        return recommendations_html

    def _build_risk_html(self, risk_assessment):
        """Build HTML for risk assessment section"""
        risk_html = ""
        risk_factors_html = ""

        risk_levels = risk_assessment.copy()
        risk_factors = risk_levels.pop('risk_factors', [])

        risk_colors = {
            'LOW': '#10b981',
            'MEDIUM': '#f59e0b',
            'HIGH': '#dc2626'
        }

        for risk_type, level in risk_levels.items():
            risk_name = risk_type.replace('_', ' ').title()
            level_str = str(level).upper()
            color = risk_colors.get(level_str, '#6b7280')

            risk_html += f"""
            <div class="risk-item">
                <span class="risk-label">{risk_name}</span>
                <span class="risk-badge" style="background-color: {color}">{level_str}</span>
            </div>
            """

        # Risk factors
        if isinstance(risk_factors, list):
            for factor in risk_factors:
                risk_factors_html += f"""
                <li class="risk-factor">{factor}</li>
                """

        return risk_html, risk_factors_html

    def _build_optimization_html(self, optimization_analysis):
        """Build HTML for optimization analysis section"""
        if not optimization_analysis or optimization_analysis.get('error'):
            return ""
        
        optimization_html = """
        <div class="section">
            <h2 class="section-title">Financial Optimization Analysis</h2>
        """
        
        # Executive Summary
        exec_summary = optimization_analysis.get('executive_summary', {})
        if exec_summary:
            optimization_html += f"""
            <div class="optimization-summary">
                <h3>Optimization Summary</h3>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-header">
                            <h3>Optimization Score</h3>
                        </div>
                        <div class="metric-value">{optimization_analysis.get('optimization_score', 0)}/100</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-header">
                            <h3>Total Potential</h3>
                        </div>
                        <div class="metric-value">${exec_summary.get('total_optimization_potential', 0):,.0f}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-header">
                            <h3>Priority Level</h3>
                        </div>
                        <div class="metric-value">{exec_summary.get('implementation_priority', 'MEDIUM')}</div>
                    </div>
                </div>
            </div>
            """
        
        # Cash Flow Optimization
        cash_optimization = optimization_analysis.get('cash_flow_optimization', {})
        if cash_optimization:
            optimization_html += """
            <div class="optimization-category">
                <h3>Cash Flow Optimization</h3>
            """
            
            for category, recommendations in cash_optimization.items():
                if isinstance(recommendations, list) and recommendations:
                    optimization_html += f"""
                    <div class="recommendation-category">
                        <h4>{category.replace('_', ' ').title()}</h4>
                    """
                    
                    for rec in recommendations[:3]:  # Show top 3
                        if isinstance(rec, dict):
                            optimization_html += f"""
                            <div class="recommendation-card">
                                <div class="recommendation-header">
                                    <span class="priority-badge">{rec.get('priority', 'MEDIUM')}</span>
                                    <h4>{rec.get('action', 'N/A')}</h4>
                                </div>
                                <p class="recommendation-description">{rec.get('description', '')}</p>
                                <div class="recommendation-footer">
                                    <span><strong>Impact:</strong> {rec.get('potential_impact', 'N/A')}</span>
                                    <span><strong>Timeline:</strong> {rec.get('timeline', 'N/A')}</span>
                                </div>
                            </div>
                            """
                    
                    optimization_html += "</div>"
            
            optimization_html += "</div>"
        
        # Cost Optimization
        cost_optimization = optimization_analysis.get('cost_optimization', {})
        if cost_optimization:
            optimization_html += """
            <div class="optimization-category">
                <h3>Cost Optimization</h3>
            """
            
            savings_potential = cost_optimization.get('total_savings_potential', {})
            if savings_potential:
                optimization_html += f"""
                <div class="savings-summary">
                    <h4>Savings Potential</h4>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-header">
                                <h3>Annual Savings</h3>
                            </div>
                            <div class="metric-value">${savings_potential.get('total_annual_savings', 0):,.0f}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-header">
                                <h3>Savings %</h3>
                            </div>
                            <div class="metric-value">{savings_potential.get('savings_percentage', 0):.1f}%</div>
                        </div>
                    </div>
                </div>
                """
            
            optimization_html += "</div>"
        
        # Implementation Roadmap
        roadmap = optimization_analysis.get('implementation_roadmap', {})
        if roadmap:
            optimization_html += """
            <div class="implementation-roadmap">
                <h3>Implementation Roadmap</h3>
            """
            
            for phase, details in roadmap.items():
                if isinstance(details, dict):
                    optimization_html += f"""
                    <div class="roadmap-phase">
                        <h4>{phase.replace('_', ' ').title()}</h4>
                        <p><strong>Timeline:</strong> {details.get('timeline', 'N/A')}</p>
                        <p><strong>Success Metrics:</strong> {', '.join(details.get('success_metrics', []))}</p>
                        <p><strong>Resources Required:</strong> {details.get('resources_required', 'N/A')}</p>
                    </div>
                    """
            
            optimization_html += "</div>"
        
        optimization_html += "</div>"
        return optimization_html

    def _generate_charts(self, analysis_request):
        """Generate visualization charts"""
        charts = {}

        try:
            predictions = analysis_request.predictions or {}

            if predictions:
                # Create predictions chart
                fig, ax = plt.subplots(figsize=(10, 6))

                metrics = [m.replace('_', ' ').title() for m in predictions.keys()]
                values = [float(predictions[m]) for m in predictions.keys()]
                colors = ['#10b981' if v > 0 else '#ef4444' for v in values]

                ax.barh(metrics, values, color=colors, alpha=0.7)
                ax.set_xlabel('Value', fontsize=12)
                ax.set_title('Financial Metrics Predictions', fontsize=14, fontweight='bold')
                ax.axvline(x=0, color='black', linestyle='--', linewidth=0.8)
                ax.grid(axis='x', alpha=0.3)

                # Save to base64
                buffer = io.BytesIO()
                plt.tight_layout()
                plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
                buffer.seek(0)
                img_str = base64.b64encode(buffer.read()).decode()
                plt.close()

                charts[
                    'predictions'] = f'<div class="chart-container"><img src="data:image/png;base64,{img_str}" alt="Predictions Chart"></div>'
            else:
                charts['predictions'] = ''

        except Exception as e:
            logger.error(f"Chart generation error: {e}")
            charts['predictions'] = ''

        return charts

    def _sanitize_text(self, text):
        """Sanitize text for PDF rendering"""
        if text is None:
            return ""
        text = str(text)
        text = text.encode('latin-1', 'ignore').decode('latin-1')
        text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
        return text

    def _safe_multi_cell(self, pdf, w, h, txt, border=0, align='L', fill=False):
        """Safely render multi-cell text"""
        try:
            sanitized_text = self._sanitize_text(txt)
            if len(sanitized_text) > 0:
                pdf.multi_cell(w, h, sanitized_text, border, align, fill)
        except Exception as e:
            pdf.cell(w, h, "Error rendering text", border, 1, align)

    def _generate_pdf_report(self, analysis_request):
        """Generate PDF report"""
        filename = f"financial_analysis_{analysis_request.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(self.reports_dir, filename)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)

        # Title
        pdf.cell(0, 10, txt="Financial AI Analysis Report", ln=1, align='C')
        pdf.ln(10)

        # Executive Summary
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt="EXECUTIVE SUMMARY", ln=1)
        pdf.set_font("Arial", '', 11)

        risk_level = str(analysis_request.risk_assessment.get('overall_risk', 'UNKNOWN'))
        pdf.cell(0, 8, txt=f"Overall Risk Level: {risk_level}", ln=1)
        pdf.cell(0, 8, txt=f"Analysis Date: {analysis_request.created_at.strftime('%Y-%m-%d %H:%M')}", ln=1)

        processing_time = analysis_request.processing_time_seconds or 0
        pdf.cell(0, 8, txt=f"Processing Time: {float(processing_time):.2f} seconds", ln=1)
        pdf.ln(5)

        # Predictions Section
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt="FINANCIAL PREDICTIONS", ln=1)
        pdf.set_font("Arial", '', 11)

        predictions = analysis_request.predictions or {}
        for metric, value in predictions.items():
            display_name = self._sanitize_text(metric.replace('_', ' ').title())
            try:
                numeric_value = float(value)
                value_str = f"{numeric_value:.4f}"
            except (ValueError, TypeError):
                value_str = str(value)[:50]

            pdf.cell(0, 7, txt=f"{display_name}: {value_str}", ln=1)

        pdf.ln(5)

        # Risk Assessment
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt="RISK ASSESSMENT", ln=1)
        pdf.set_font("Arial", '', 11)

        risk_assessment = analysis_request.risk_assessment or {}
        for risk_type, level in risk_assessment.items():
            if risk_type != 'risk_factors':
                display_name = self._sanitize_text(risk_type.replace('_', ' ').title())
                level_str = self._sanitize_text(str(level))
                pdf.cell(0, 7, txt=f"{display_name}: {level_str}", ln=1)

        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, txt="Risk Factors:", ln=1)
        pdf.set_font("Arial", '', 10)

        risk_factors = risk_assessment.get('risk_factors', [])
        if isinstance(risk_factors, list):
            for factor in risk_factors[:10]:
                factor_text = self._sanitize_text(str(factor))
                if len(factor_text) > 150:
                    factor_text = factor_text[:147] + "..."
                self._safe_multi_cell(pdf, 0, 6, f"- {factor_text}")

        pdf.ln(5)

        # Recommendations Section
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt="KEY RECOMMENDATIONS", ln=1)
        pdf.set_font("Arial", '', 11)

        recommendations = analysis_request.recommendations or {}
        for category, recs in recommendations.items():
            if not recs:
                continue

            pdf.set_font("Arial", 'B', 12)
            category_name = self._sanitize_text(category.replace('_', ' ').title())
            pdf.cell(0, 8, txt=f"{category_name}:", ln=1)
            pdf.set_font("Arial", '', 10)

            for rec in recs[:3]:
                if not isinstance(rec, dict):
                    continue

                action = rec.get('action', rec.get('recommendation', 'N/A'))
                action_text = self._sanitize_text(str(action))
                if len(action_text) > 100:
                    action_text = action_text[:97] + "..."

                self._safe_multi_cell(pdf, 0, 6, f"- {action_text}")

                if 'description' in rec:
                    desc = self._sanitize_text(str(rec['description']))
                    if len(desc) > 150:
                        desc = desc[:147] + "..."
                    self._safe_multi_cell(pdf, 0, 5, f"  {desc}")

                if 'timeline' in rec:
                    timeline = self._sanitize_text(str(rec['timeline']))
                    pdf.cell(0, 5, txt=f"  Timeline: {timeline}", ln=1)

                pdf.ln(2)

        try:
            pdf.output(filepath)
        except Exception as e:
            raise Exception(f"PDF generation failed: {str(e)}")

        return filepath, 'application/pdf'

    def _generate_json_report(self, analysis_request):
        """Generate JSON report"""
        filename = f"financial_analysis_{analysis_request.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.reports_dir, filename)

        def convert_to_serializable(obj):
            if isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            elif hasattr(obj, '__float__'):
                return float(obj)
            elif hasattr(obj, '__int__'):
                return int(obj)
            else:
                return obj

        report_data = {
            'analysis_id': analysis_request.id,
            'corporate_id': analysis_request.corporate.id,
            'corporate_name': getattr(analysis_request.corporate, 'name', 'Unknown'),
            'analysis_date': analysis_request.created_at.isoformat(),
            'processing_time_seconds': float(analysis_request.processing_time_seconds or 0),
            'model_used': {
                'id': analysis_request.model_used.id,
                'name': analysis_request.model_used.name,
                'type': analysis_request.model_used.model_type,
                'version': analysis_request.model_used.version
            } if analysis_request.model_used else None,
            'input_data': convert_to_serializable(analysis_request.input_data or {}),
            'predictions': convert_to_serializable(analysis_request.predictions or {}),
            'recommendations': convert_to_serializable(analysis_request.recommendations or {}),
            'risk_assessment': convert_to_serializable(analysis_request.risk_assessment or {}),
            'confidence_scores': convert_to_serializable(analysis_request.confidence_scores or {})
        }

        with open(filepath, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        return filepath, 'application/json'

    def _generate_excel_report(self, analysis_request):
        """Generate Excel report with multiple sheets"""
        filename = f"financial_analysis_{analysis_request.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(self.reports_dir, filename)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            predictions = analysis_request.predictions or {}

            for metric, value in predictions.items():
                try:
                    numeric_value = float(value)
                except (ValueError, TypeError):
                    numeric_value = 0.0

                summary_data.append({
                    'Metric': metric.replace('_', ' ').title(),
                    'Value': numeric_value,
                    'Risk_Impact': 'High' if abs(numeric_value) > 0.5 else 'Medium' if abs(
                        numeric_value) > 0.2 else 'Low'
                })

            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)

            # Recommendations sheet
            recommendations_data = []
            recommendations = analysis_request.recommendations or {}

            for category, recs in recommendations.items():
                if not isinstance(recs, list):
                    continue

                for rec in recs:
                    if not isinstance(rec, dict):
                        continue

                    recommendations_data.append({
                        'Category': category.replace('_', ' ').title(),
                        'Priority': str(rec.get('priority', 'Medium')),
                        'Action': str(rec.get('action', rec.get('recommendation', 'N/A')))[:200],
                        'Description': str(rec.get('description', ''))[:300],
                        'Timeline': str(rec.get('timeline', ''))[:100],
                        'Potential_Impact': str(rec.get('potential_impact', rec.get('impact', '')))[:200]
                    })

            if recommendations_data:
                recommendations_df = pd.DataFrame(recommendations_data)
                recommendations_df.to_excel(writer, sheet_name='Recommendations', index=False)

            # Risk assessment sheet
            risk_data = []
            risk_assessment = analysis_request.risk_assessment or {}

            for risk_type, level in risk_assessment.items():
                if risk_type != 'risk_factors':
                    risk_data.append({
                        'Risk_Type': risk_type.replace('_', ' ').title(),
                        'Level': str(level)
                    })

            # Add risk factors
            risk_factors = risk_assessment.get('risk_factors', [])
            if isinstance(risk_factors, list):
                for factor in risk_factors:
                    risk_data.append({
                        'Risk_Type': 'Risk Factor',
                        'Level': str(factor)[:300]
                    })

            if risk_data:
                risk_df = pd.DataFrame(risk_data)
                risk_df.to_excel(writer, sheet_name='Risk_Assessment', index=False)

        return filepath, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'