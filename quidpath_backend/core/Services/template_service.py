import os
from django.template.loader import render_to_string

class TemplateService:
    """
    Loads HTML templates for notifications.
    """

    def render_template(self, template_name: str, context: dict = None) -> str:
        context = context or {}
        return render_to_string(template_name, context)

    def load_raw_template(self, template_path: str) -> str:
        """Load a raw HTML template as string."""
        if not os.path.exists(template_path):
            return ""
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
