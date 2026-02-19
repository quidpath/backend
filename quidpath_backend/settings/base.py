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
    "quidpath_backend.core.middleware.subscription_middleware.SubscriptionMiddleware",
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

# Database (PostgreSQL via DATABASE_URL)
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    # Use DATABASE_URL if provided
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
        )
    }
else:
    # Fallback to individual environment variables
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "quidpath_db"),
            "USER": os.environ.get("DB_USER", "quidpath_user"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "db"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

# Validate database configuration
if not DATABASES.get("default") or not DATABASES["default"].get("ENGINE"):
    import sys
    print("ERROR: Database configuration is invalid!", file=sys.stderr)
    print(f"DATABASE_URL: {DATABASE_URL}", file=sys.stderr)
    print(f"DB_NAME: {os.environ.get('DB_NAME')}", file=sys.stderr)
    print(f"DB_USER: {os.environ.get('DB_USER')}", file=sys.stderr)
    print(f"DB_HOST: {os.environ.get('DB_HOST')}", file=sys.stderr)
    print(f"DATABASES config: {DATABASES}", file=sys.stderr)
    sys.exit(1)

# Optional: enforce SSL for production
if os.environ.get("REQUIRE_DB_SSL", "false").lower() == "true":
    DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}

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
}

# JWT Configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Email Notification Config
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASSWORD")
SMTP_USE_TLS = True
SMTP_USE_SSL = False
DEFAULT_FROM_EMAIL = "noreply@quidpath.com"

# Billing Service Configuration
BILLING_SERVICE_URL = os.environ.get(
    "BILLING_SERVICE_URL", "http://localhost:8002/api/billing"
)

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
}

# Webhook Configuration
BILLING_WEBHOOK_SECRET = os.environ.get("BILLING_WEBHOOK_SECRET", "")
