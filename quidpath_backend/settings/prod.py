from .base import *
import os
import logging

logger = logging.getLogger(__name__)
print("Using Production Settings")

# Security Settings
DEBUG = False
ALLOWED_HOSTS = [
    'api.quidpath.com',
    '13.61.244.11',  # Your EC2 IP
    'localhost',
    '127.0.0.1',
]

# IMPORTANT: Set these for admin to work
CSRF_TRUSTED_ORIGINS = [
    'https://api.quidpath.com',
    'https://www.api.quidpath.com',
    'http://13.61.244.11',
]

# Database config
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "devdb"),
        "USER": os.getenv("POSTGRES_USER", "devuser"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "devpass"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 600,
    }
}

logger.info(f"Database config: {DATABASES}")

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
SECURE_CONTENT_TYPE_NOSNIFF = True

# CORS - be more restrictive in production
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://quidpath-erp-frontend-production.up.railway.app",
    "https://app.quidpath.com",  # Add your frontend domain
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