# settings/stage.py – Staging environment (frontend at https://stage.quidpath.com)
import logging
import os

from corsheaders.defaults import default_headers

from .base import *

logger = logging.getLogger(__name__)
print("Using Stage Settings")

# ====================================
# SECURITY SETTINGS
# ====================================
DEBUG = False

# Load allowed hosts from environment (comma-separated)
ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS", "stage-api.quidpath.com,stage.quidpath.com,localhost,127.0.0.1,0.0.0.0"
).split(",")

# ====================================
# CSRF & CORS CONFIGURATION (stage frontend: https://stage.quidpath.com)
# ====================================
_env_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
if _env_csrf:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _env_csrf.split(",") if o.strip()]
else:
    # Only the stage frontend and API; no wildcard to avoid trusting unknown subdomains
    CSRF_TRUSTED_ORIGINS = [
        "https://stage.quidpath.com",
        "https://www.stage.quidpath.com",
        "https://stage-api.quidpath.com",
    ]

# --- CORS CONFIGURATION ---
# Allow browser requests from the stage frontend so "failed to fetch" is avoided
CORS_ALLOW_ALL_ORIGINS = False
_env_cors = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
if _env_cors:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _env_cors.split(",") if o.strip()]
else:
    CORS_ALLOWED_ORIGINS = [
        "https://stage.quidpath.com",
        "https://www.stage.quidpath.com",
    ]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = list(default_headers) + [
    "authorization",
    "content-type",
]

# ====================================
#  STATIC & MEDIA FILES
# ====================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ====================================
# BILLING SERVICE (stage container)
# ====================================
BILLING_SERVICE_URL = os.environ.get(
    "BILLING_SERVICE_URL", "http://billing-backend-stage:8000/api/billing"
)

# ====================================
# SECURITY MIDDLEWARE HEADERS
# ====================================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ====================================
# LOGGING CONFIGURATION
# ====================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
