from .base import *
import os
import logging

logger = logging.getLogger(__name__)
print("Using Production Settings")

# Security Settings
# This correctly uses the ALLOWED_HOSTS variable from your .env file
DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

# IMPORTANT: Set these for admin to work
CSRF_TRUSTED_ORIGINS = [
    'https://api.quidpath.com',
    'https://www.api.quidpath.com',
    'http://13.61.244.11',
]

# The DATABASES block has been removed to avoid conflict with base.py

# Static files (CRITICAL for admin CSS/JS)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Security settings for production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIF = True

# CORS - be more restrictive in production
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://quidpath.com",
    "https://www.quidpath.com",
    "http://localhost:3000",
    "https://quidpath-erp-frontend-production.up.railway.app"
# Add your frontend domain
]
CORS_ALLOW_CREDENTIALS = True

# Logging for debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}