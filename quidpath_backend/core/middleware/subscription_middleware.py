"""
Subscription Verification Middleware
Ensures that only companies with active subscriptions/trials can access Quidpath
"""
from django.http import JsonResponse
from django.urls import resolve
from quidpath_backend.core.billing_client import BillingServiceClient
import logging

logger = logging.getLogger(__name__)


class SubscriptionMiddleware:
    """
    Middleware to verify that a corporate has an active subscription or trial
    before allowing access to protected endpoints
    """
    
    # Endpoints that don't require subscription check
    EXEMPT_PATHS = [
        '/admin/',
        '/api/auth/login/',
        '/api/auth/register/',
        '/api/auth/forgot-password/',
        '/api/auth/reset-password/',
        '/api/corporate/register/',
        '/api/billing/',  # Billing endpoints themselves don't need check
        '/static/',
        '/media/',
    ]
    
    # Specific view names that don't require subscription
    EXEMPT_VIEW_NAMES = [
        'admin',
        'login',
        'register',
        'corporate_register',
        'forgot_password',
        'reset_password',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.billing_client = BillingServiceClient()
    
    def __call__(self, request):
        # Check if path is exempt
        if self._is_exempt_path(request.path):
            return self.get_response(request)
        
        # Get corporate_id from request
        corporate_id = self._extract_corporate_id(request)
        
        if not corporate_id:
            # If no corporate_id, allow request (other auth middleware will handle it)
            return self.get_response(request)
        
        # Check subscription status
        try:
            access_result = self.billing_client.check_access(corporate_id)
            
            if not access_result.get('success'):
                logger.error(f"Billing service error for corporate {corporate_id}: {access_result.get('message')}")
                # Allow request on billing service error (fail open for reliability)
                return self.get_response(request)
            
            has_access = access_result.get('has_access', False)
            
            if not has_access:
                reason = access_result.get('reason', 'unknown')
                message = access_result.get('message', 'No active subscription or trial')
                
                return JsonResponse({
                    'success': False,
                    'error': 'subscription_required',
                    'message': message,
                    'reason': reason,
                    'data': {
                        'corporate_id': corporate_id,
                        'trial': access_result.get('trial'),
                        'subscription': access_result.get('subscription'),
                    }
                }, status=403)
            
            # Add subscription info to request for use in views
            request.subscription_info = {
                'has_access': True,
                'access_type': access_result.get('access_type'),
                'corporate_id': corporate_id,
                'trial': access_result.get('trial'),
                'subscription': access_result.get('subscription'),
                'unpaid_invoices_count': access_result.get('unpaid_invoices_count', 0),
                'unpaid_invoices': access_result.get('unpaid_invoices', []),
            }
            
            # Add warning header if there are unpaid invoices
            response = self.get_response(request)
            if access_result.get('unpaid_invoices_count', 0) > 0:
                response['X-Quidpath-Unpaid-Invoices'] = str(access_result['unpaid_invoices_count'])
            
            return response
            
        except Exception as e:
            logger.error(f"Error checking subscription for corporate {corporate_id}: {str(e)}")
            # Allow request on error (fail open)
            return self.get_response(request)
    
    def _is_exempt_path(self, path: str) -> bool:
        """Check if the path is exempt from subscription verification"""
        for exempt_path in self.EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return True
        
        try:
            resolved = resolve(path)
            if resolved.view_name in self.EXEMPT_VIEW_NAMES:
                return True
        except:
            pass
        
        return False
    
    def _extract_corporate_id(self, request) -> str:
        """Extract corporate_id from request"""
        # Try to get from user if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Check if user has corporate attribute (CorporateUser)
            if hasattr(request.user, 'corporateuser') and hasattr(request.user.corporateuser, 'corporate'):
                return str(request.user.corporateuser.corporate.id)
            
            # Check if user has corporate directly
            if hasattr(request.user, 'corporate') and hasattr(request.user.corporate, 'id'):
                return str(request.user.corporate.id)
        
        # Try to get from request headers
        corporate_id = request.headers.get('X-Corporate-ID')
        if corporate_id:
            return corporate_id
        
        # Try to get from request body (for POST requests)
        if request.method == 'POST' and hasattr(request, 'body'):
            try:
                import json
                data = json.loads(request.body)
                if 'corporate_id' in data:
                    return str(data['corporate_id'])
            except:
                pass
        
        # Try to get from query params
        corporate_id = request.GET.get('corporate_id')
        if corporate_id:
            return corporate_id
        
        return None


