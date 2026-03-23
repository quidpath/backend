# settings/base.py
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from corsheaders.defaults import default_headers
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file only if it exists (for local development)
# In production (Docker), environment variables are set by docker-compose
ENV_FILE = BASE_DIR / (".env.dev" if os.environ.get("DJANGO_ENV") == "dev" else ".env")
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    # In Docker, .env might not exist, which is fine - env vars come from docker-compose
    pass

# Security & Debug
SECRET_KEY = os.environ.get("SECRET_KEY", "unsafe-dev-key")
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(
    ","
)

# Application definition
INSTALLED_APPS = [
    "daphne",  # Must be first for ASGI support
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "channels",  # WebSocket support
    "quidpath_backend.core",  # Core middleware, billing, bootstrap_data command
    "Authentication",
    "corsheaders",
    "OrgAuth",
    "Banking",
    "Accounting",
    "Payments",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "quidpath_backend.core.middleware.billing_middleware.BillingAccessMiddleware",
]

ROOT_URLCONF = "quidpath_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "quidpath_backend.wsgi.application"
ASGI_APPLICATION = "quidpath_backend.asgi.application"

# Channels Configuration for WebSocket
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT") or 6379)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

# Fallback to in-memory channel layer for development without Redis
if os.environ.get("USE_MEMORY_CHANNEL_LAYER", "false").lower() == "true":
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

# Database Configuration - PostgreSQL via DATABASE_URL
# Security Best Practice: Use DATABASE_URL instead of individual credentials
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Format: postgresql://user:password@host:port/dbname"
    )

# Parse DATABASE_URL with connection pooling
DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,  # Connection pooling (10 minutes)
        conn_health_checks=True,  # Enable connection health checks
        ssl_require=os.environ.get("DB_SSL_REQUIRE", "false").lower() == "true",
    )
}

# Production SSL enforcement
if not DEBUG and os.environ.get("DB_SSL_REQUIRE", "false").lower() == "true":
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"]["sslmode"] = "require"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# REST Framework setup
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "5/minute",
        "user": "5/minute",
        "auth": "5/minute",
    },
}

# JWT Configuration — access tokens expire in 6 hours, refresh tokens in 7 days
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=6),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": os.environ.get("JWT_SECRET_KEY", SECRET_KEY),
    "UPDATE_LAST_LOGIN": True,
}

# Email Notification Config
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_USE_TLS = True
SMTP_USE_SSL = False
DEFAULT_FROM_EMAIL = "noreply@quidpath.com"

# Cache — use Redis if available, fall back to local memory
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "quidpath-rate-limit",
    }
}
if os.environ.get("REDIS_HOST"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', 6379)}/1",
        }
    }

# Billing Service Configuration
BILLING_SERVICE_URL = os.environ.get(
    "BILLING_SERVICE_URL", "http://billing-backend-dev:8002"
)
BILLING_SERVICE_API_KEY = os.environ.get("BILLING_SERVICE_API_KEY", "")
# Shared secret for service-to-service calls (X-Service-Key header)
BILLING_SERVICE_SECRET = os.environ.get("BILLING_SERVICE_SECRET", "")
# Secret used to verify webhook signatures from billing service
BILLING_WEBHOOK_SECRET = os.environ.get("BILLING_WEBHOOK_SECRET", "")

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static & Media
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Custom User
AUTH_USER_MODEL = "Authentication.CustomUser"

# CORS
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    "https://quidpath.com",
    "https://www.quidpath.com",
    "http://localhost:3000",
    "https://quidpath-erp-frontend-production.up.railway.app",
]
CORS_ALLOW_HEADERS = list(default_headers) + [
    "authorization",
]

# JWT Configuration for Microservices
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)

# Service API Keys for Microservices
SERVICE_API_KEYS = {
    "billing-service": os.environ.get("BILLING_SERVICE_API_KEY", ""),
    "tazama-service": os.environ.get("TAZAMA_SERVICE_API_KEY", ""),
    # ERP microservices
    "inventory-service": os.environ.get("INVENTORY_SERVICE_SECRET", ""),
    "pos-service": os.environ.get("POS_SERVICE_SECRET", ""),
    "crm-service": os.environ.get("CRM_SERVICE_SECRET", ""),
    "hrm-service": os.environ.get("HRM_SERVICE_SECRET", ""),
    "projects-service": os.environ.get("PROJECTS_SERVICE_SECRET", ""),
}

# Webhook Configuration
BILLING_WEBHOOK_SECRET = os.environ.get("BILLING_WEBHOOK_SECRET", "")

# M-Pesa Daraja API Configuration
MPESA_ENVIRONMENT = os.environ.get("MPESA_ENVIRONMENT", "production")
MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY", "")
MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET", "")
MPESA_BUSINESS_SHORT_CODE = os.environ.get("MPESA_BUSINESS_SHORT_CODE", "9895960")
MPESA_TILL_NUMBER = os.environ.get("MPESA_TILL_NUMBER", "9100097")
MPESA_PASSKEY = os.environ.get("MPESA_PASSKEY", "")
MPESA_CALLBACK_URL = os.environ.get("MPESA_CALLBACK_URL", "https://api.quidpath.com/api/payments/mpesa/callback/")
