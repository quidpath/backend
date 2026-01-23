"""
Internal API URLs for inter-service communication.
These endpoints are used by microservices to communicate with the main backend.
"""
from django.urls import path
from quidpath_backend.core.views import auth_verify

urlpatterns = [
    path('auth/verify/', auth_verify.verify_credentials, name='verify_credentials'),
]

