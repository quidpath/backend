"""
Authentication verification endpoint for microservices.
Allows other services (like billing) to verify user credentials.
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from Authentication.models import CustomUser


@csrf_exempt
def verify_credentials(request):
    """
    Verify user credentials for inter-service authentication.
    
    This endpoint is used by microservices (like billing) to verify
    that a user's credentials are valid in the main backend.
    
    POST /api/internal/auth/verify/
    {
        "username": "admin",
        "password": "password123"
    }
    
    Returns:
    {
        "success": true,
        "user": {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "is_staff": true,
            "is_superuser": true,
            "is_active": true
        }
    }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body) if request.body else {}
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return JsonResponse({
                'success': False,
                'error': 'Username and password are required'
            }, status=400)
        
        # Try to get the user by username
        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid credentials'
            }, status=401)
        
        # Check if password is correct
        if not check_password(password, user.password):
            return JsonResponse({
                'success': False,
                'error': 'Invalid credentials'
            }, status=401)
        
        # Check if user is active
        if not user.is_active:
            return JsonResponse({
                'success': False,
                'error': 'User account is inactive'
            }, status=401)
        
        # User is authenticated
        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone_number': getattr(user, 'phone_number', ''),
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'is_active': user.is_active,
            }
        }, status=200)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

