# template_manager.py - Template Management Engine for Tazama Reports
import os
from django.conf import settings
from django.template.loader import render_to_string
from django.template import Context, Template
import logging

logger = logging.getLogger(__name__)


class TazamaTemplateManager:
    """Template management engine for generating structured PDF/HTML reports"""
    
    def __init__(self):
        # Get the Tazama app directory
        current_dir = os.path.dirname(__file__)
        app_dir = os.path.dirname(current_dir)
        self.templates_dir = os.path.join(app_dir, 'templates')
        self.styles_path = os.path.join(self.templates_dir, 'report_styles.css')
        
    def load_template(self, template_name):
        """Load a template file"""
        template_path = os.path.join(self.templates_dir, template_name)
        if not os.path.exists(template_path):
            logger.error(f"Template not found: {template_path}")
            return None
        
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def load_styles(self):
        """Load CSS styles"""
        if not os.path.exists(self.styles_path):
            logger.warning(f"Styles file not found: {self.styles_path}")
            return ""
        
        with open(self.styles_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def prepare_context(self, analysis_request):
        """Prepare comprehensive context data for templates"""
        from datetime import datetime
        
        predictions = analysis_request.predictions or {}
        recommendations = analysis_request.recommendations or {}
        risk_assessment = analysis_request.risk_assessment or {}
        confidence_scores = analysis_request.confidence_scores or {}
        input_data = analysis_request.input_data or {}
        
        # Format dates
        generated_date = analysis_request.created_at.strftime('%B %d, %Y at %I:%M %p')
        current_year = datetime.now().year
        
        # Model information
        model_name = analysis_request.model_used.name if analysis_request.model_used else 'N/A'
        processing_time = f"{float(analysis_request.processing_time_seconds or 0):.2f}"
        
        # Corporate information
        corporate_name = None
        if hasattr(analysis_request, 'corporate') and analysis_request.corporate:
            corporate_name = getattr(analysis_request.corporate, 'name', None)
        
        # Risk information
        overall_risk = risk_assessment.get('overall_risk', 'UNKNOWN')
        risk_factors = risk_assessment.get('risk_factors', [])
        risk_factors_count = len(risk_factors) if isinstance(risk_factors, list) else 0
        
        # Recommendations count
        total_recommendations = 0
        if isinstance(recommendations, dict):
            for rec_list in recommendations.values():
                if isinstance(rec_list, list):
                    total_recommendations += len(rec_list)
        
        # Generate HTML sections
        predictions_html = self._build_predictions_html(predictions, confidence_scores)
        recommendations_html = self._build_recommendations_html(recommendations)
        risk_html, risk_factors_html = self._build_risk_html(risk_assessment)
        optimization_html = self._build_optimization_html(
            getattr(analysis_request, 'optimization_analysis', {})
        )
        input_data_html = self._build_input_data_html(input_data)
        
        # Summary texts
        risk_summary = self._get_risk_summary(overall_risk, risk_factors_count)
        recommendations_summary = self._get_recommendations_summary(total_recommendations)
        factors_summary = self._get_factors_summary(risk_factors_count)
        
        context = {
            'generated_date': generated_date,
            'processing_time': processing_time,
            'model_name': model_name,
            'corporate_name': corporate_name,
            'analysis_id': str(analysis_request.id)[:8],
            'current_year': current_year,
            'overall_risk': overall_risk,
            'risk_summary': risk_summary,
            'total_recommendations': total_recommendations,
            'recommendations_summary': recommendations_summary,
            'risk_factors_count': risk_factors_count,
            'factors_summary': factors_summary,
            'predictions_html': predictions_html,
            'recommendations_html': recommendations_html,
            'risk_html': risk_html,
            'risk_factors_html': risk_factors_html,
            'optimization_html': optimization_html,
            'input_data_html': input_data_html,
            'charts': {'predictions': ''},  # Will be populated by report generator
            'css_styles': self.load_styles(),
        }
        
        return context
    
    def render_report(self, analysis_request, charts=None):
        """Render the complete report using templates"""
        context = self.prepare_context(analysis_request)
        
        # Add charts if provided
        if charts:
            context['charts'].update(charts)
        
        # Load base template
        template_content = self.load_template('report_base.html')
        if not template_content:
            raise ValueError("Could not load report template")
        
        # Render template
        template = Template(template_content)
        rendered_html = template.render(Context(context))
        
        return rendered_html
    
    def _build_predictions_html(self, predictions, confidence_scores):
        """Build HTML for predictions section"""
        html = ""
        
        for metric, value in predictions.items():
            confidence = confidence_scores.get(metric, 0.5)
            confidence_pct = f"{confidence * 100:.0f}%"
            
            metric_name = metric.replace('_', ' ').title()
            try:
                formatted_value = f"{float(value):.2%}"
            except:
                formatted_value = str(value)
            
            color_class = self._get_metric_color_class(metric, value)
            
            html += f"""
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
        
        return html
    
    def _build_recommendations_html(self, recommendations):
        """Build HTML for recommendations section"""
        html = ""
        
        priority_colors = {
            'CRITICAL': '#dc2626',
            'HIGH': '#ea580c',
            'MEDIUM': '#f59e0b',
            'LOW': '#10b981'
        }
        
        if not isinstance(recommendations, dict):
            return html
        
        for category, recs in recommendations.items():
            if not recs or not isinstance(recs, list):
                continue
            
            category_name = category.replace('_', ' ').title()
            html += f"""
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
                
                html += f"""
                <div class="recommendation-card">
                    <div class="recommendation-header">
                        <span class="priority-badge" style="background-color: {priority_color}">{priority}</span>
                        <h4>{self._escape_html(action)}</h4>
                    </div>
                    <p class="recommendation-description">{self._escape_html(description)}</p>
                    <div class="recommendation-footer">
                        <span><strong>Timeline:</strong> {self._escape_html(timeline)}</span>
                        <span><strong>Impact:</strong> {self._escape_html(str(impact))}</span>
                    </div>
                </div>
                """
            
            html += "</div>"
        
        return html
    
    def _build_risk_html(self, risk_assessment):
        """Build HTML for risk assessment section"""
        risk_html = ""
        risk_factors_html = ""
        
        if not isinstance(risk_assessment, dict):
            return risk_html, risk_factors_html
        
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
                <li class="risk-factor">{self._escape_html(str(factor))}</li>
                """
        
        return risk_html, risk_factors_html
    
    def _build_optimization_html(self, optimization_analysis):
        """Build HTML for optimization analysis section"""
        if not optimization_analysis or optimization_analysis.get('error'):
            return ""
        
        html = """
        <div class="optimization-section">
        """
        
        # Executive Summary
        exec_summary = optimization_analysis.get('executive_summary', {})
        if exec_summary:
            html += f"""
            <div class="optimization-summary">
                <h3 class="subsection-title">Optimization Summary</h3>
                <div class="summary-grid">
                    <div class="summary-card">
                        <div class="card-header">
                            <h3>Optimization Score</h3>
                        </div>
                        <div class="card-content">
                            <div class="metric-value">{optimization_analysis.get('optimization_score', 0)}/100</div>
                        </div>
                    </div>
                    <div class="summary-card">
                        <div class="card-header">
                            <h3>Total Potential</h3>
                        </div>
                        <div class="card-content">
                            <div class="metric-value">${exec_summary.get('total_optimization_potential', 0):,.0f}</div>
                        </div>
                    </div>
                    <div class="summary-card">
                        <div class="card-header">
                            <h3>Priority Level</h3>
                        </div>
                        <div class="card-content">
                            <div class="metric-value">{exec_summary.get('implementation_priority', 'MEDIUM')}</div>
                        </div>
                    </div>
                </div>
            </div>
            """
        
        html += "</div>"
        return html
    
    def _build_input_data_html(self, input_data):
        """Build HTML for input data summary"""
        if not input_data or not isinstance(input_data, dict):
            return ""
        
        html = '<div class="input-data-grid">'
        
        # Key financial metrics
        key_fields = {
            'totalRevenue': 'Total Revenue',
            'netIncome': 'Net Income',
            'operatingIncome': 'Operating Income',
            'grossProfit': 'Gross Profit',
            'costOfRevenue': 'Cost of Revenue',
            'totalOperatingExpenses': 'Operating Expenses'
        }
        
        for field_key, field_label in key_fields.items():
            value = input_data.get(field_key, 0)
            if value:
                try:
                    formatted_value = f"${float(value):,.2f}"
                except:
                    formatted_value = str(value)
                
                html += f"""
                <div class="input-data-item">
                    <div class="input-data-label">{field_label}</div>
                    <div class="input-data-value">{formatted_value}</div>
                </div>
                """
        
        html += '</div>'
        return html
    
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
                return ''
        except:
            return ''
    
    def _get_risk_summary(self, risk_level, factors_count):
        """Get risk summary text"""
        if risk_level.upper() == 'LOW':
            return "Your financial position shows low risk indicators."
        elif risk_level.upper() == 'MEDIUM':
            return "Some risk factors require attention and monitoring."
        else:
            return "Significant risk factors identified requiring immediate action."
    
    def _get_recommendations_summary(self, count):
        """Get recommendations summary text"""
        if count == 0:
            return "No specific recommendations at this time."
        elif count == 1:
            return "One strategic recommendation provided."
        else:
            return f"{count} strategic recommendations to improve financial performance."
    
    def _get_factors_summary(self, count):
        """Get factors summary text"""
        if count == 0:
            return "No significant risk factors identified."
        elif count == 1:
            return "One risk factor requires monitoring."
        else:
            return f"{count} risk factors identified for review."
    
    def _escape_html(self, text):
        """Escape HTML special characters"""
        if not text:
            return ""
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')
        return text

