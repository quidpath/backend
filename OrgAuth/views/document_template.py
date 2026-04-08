"""
Document Template Views
API endpoints for managing document templates
"""
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from OrgAuth.models.document_template import DocumentTemplate
from quidpath_backend.core.utils.request_parser import get_clean_data
from quidpath_backend.core.utils.json_response import ResponseProvider
from quidpath_backend.core.utils.registry import ServiceRegistry


@csrf_exempt
@require_http_methods(["GET"])
def get_document_templates(request):
    """Get all document templates for the user's corporate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        
        # Get user's corporate
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user.get("id") if isinstance(user, dict) else user.id, "is_active": True},
        )
        
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        
        # Get all templates for this corporate
        templates = DocumentTemplate.objects.filter(corporate_id=corporate_id)
        
        # Serialize templates
        templates_dict = {}
        for template in templates:
            templates_dict[template.document_type] = {
                'id': str(template.id),
                'document_type': template.document_type,
                'accentColor': template.accent_color,
                'font': template.font,
                'logoAlign': template.logo_align,
                'showLogo': template.show_logo,
                'showTagline': template.show_tagline,
                'tagline': template.tagline,
                'borderStyle': template.border_style,
                'headerBg': template.header_bg,
                'footerText': template.footer_text,
                'showBankDetails': template.show_bank_details,
                'showSignatureLine': template.show_signature_line,
                'showStamp': template.show_stamp,
            }
        
        return ResponseProvider(
            data={'templates': templates_dict},
            message="Document templates retrieved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while retrieving templates: {str(e)}",
            code=500,
        ).exception()


@csrf_exempt
@require_http_methods(["POST"])
def save_document_templates(request):
    """Save document templates for the user's corporate"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        registry = ServiceRegistry()
        
        # Get user's corporate
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user.get("id") if isinstance(user, dict) else user.id, "is_active": True},
        )
        
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        corporate = registry.database(
            model_name="Corporate",
            operation="get",
            data={"id": corporate_id},
        )
        
        # Get templates data from request
        templates_data = data.get('templates', {})
        
        if not templates_data:
            return ResponseProvider(message="No templates data provided", code=400).bad_request()
        
        # Save each template
        saved_templates = {}
        for doc_type, template_data in templates_data.items():
            # Update or create template
            template, created = DocumentTemplate.objects.update_or_create(
                corporate_id=corporate_id,
                document_type=doc_type,
                defaults={
                    'accent_color': template_data.get('accentColor', '#1565C0'),
                    'font': template_data.get('font', 'Inter'),
                    'logo_align': template_data.get('logoAlign', 'left'),
                    'show_logo': template_data.get('showLogo', True),
                    'show_tagline': template_data.get('showTagline', False),
                    'tagline': template_data.get('tagline', ''),
                    'border_style': template_data.get('borderStyle', 'thin'),
                    'header_bg': template_data.get('headerBg', True),
                    'footer_text': template_data.get('footerText', 'Thank you for your business.'),
                    'show_bank_details': template_data.get('showBankDetails', True),
                    'show_signature_line': template_data.get('showSignatureLine', True),
                    'show_stamp': template_data.get('showStamp', False),
                }
            )
            
            saved_templates[doc_type] = {
                'id': str(template.id),
                'created': created,
            }
        
        return ResponseProvider(
            data={'saved_templates': saved_templates},
            message="Document templates saved successfully",
            code=200,
        ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while saving templates: {str(e)}",
            code=500,
        ).exception()


@csrf_exempt
@require_http_methods(["GET"])
def get_template_for_document(request):
    """Get template for a specific document type"""
    data, metadata = get_clean_data(request)
    user = metadata.get("user")
    
    if not user:
        return ResponseProvider(message="User not authenticated", code=401).unauthorized()
    
    try:
        document_type = data.get('document_type')
        if not document_type:
            return ResponseProvider(message="document_type is required", code=400).bad_request()
        
        registry = ServiceRegistry()
        
        # Get user's corporate
        corporate_users = registry.database(
            model_name="CorporateUser",
            operation="filter",
            data={"customuser_ptr_id": user.get("id") if isinstance(user, dict) else user.id, "is_active": True},
        )
        
        if not corporate_users:
            return ResponseProvider(message="User has no corporate association", code=400).bad_request()
        
        corporate_id = corporate_users[0]["corporate_id"]
        
        # Get template for this document type
        try:
            template = DocumentTemplate.objects.get(
                corporate_id=corporate_id,
                document_type=document_type
            )
            
            template_data = {
                'id': str(template.id),
                'document_type': template.document_type,
                'accentColor': template.accent_color,
                'font': template.font,
                'logoAlign': template.logo_align,
                'showLogo': template.show_logo,
                'showTagline': template.show_tagline,
                'tagline': template.tagline,
                'borderStyle': template.border_style,
                'headerBg': template.header_bg,
                'footerText': template.footer_text,
                'showBankDetails': template.show_bank_details,
                'showSignatureLine': template.show_signature_line,
                'showStamp': template.show_stamp,
            }
            
            return ResponseProvider(
                data={'template': template_data},
                message="Template retrieved successfully",
                code=200,
            ).success()
            
        except DocumentTemplate.DoesNotExist:
            # Return default template if none exists
            return ResponseProvider(
                data={'template': None},
                message="No template found, using defaults",
                code=200,
            ).success()
        
    except Exception as e:
        return ResponseProvider(
            message=f"An error occurred while retrieving template: {str(e)}",
            code=500,
        ).exception()
