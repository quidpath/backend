# settings/prod.py
import logging
import os

from corsheaders.defaults import default_headers

from .base import *

logger = logging.getLogger(__name__)
print("Using Production Settings")

# ====================================
# SECURITY SETTINGS
# ====================================
DEBUG = False

# Load allowed hosts from environment (comma-separated)
ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS", "api.quidpath.com,quidpath.com,www.quidpath.com"
).split(",")

# ====================================
# CSRF & CORS CONFIGURATION
# ====================================
# CSRF trusted origins must include scheme (Django 4+). Allow override via env.
_env_csrf = os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
if _env_csrf:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _env_csrf.split(",") if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        "https://quidpath.com",
        "https://www.quidpath.com",
        # wildcard subdomains (admin/api) — Django supports wildcard with scheme
        "https://*.quidpath.com",
    ]

# --- CORS CONFIGURATION ---
CORS_ALLOW_ALL_ORIGINS = False  # GOOD: Override base.py

# These are the *only* origins that can make browser requests
CORS_ALLOWED_ORIGINS = [
    "https://quidpath.com",
    "https://www.quidpath.com",
    # You might want to add your Amplify preview/dev URLs here too
]

# This is vital for sending credentials (like JWT tokens)
CORS_ALLOW_CREDENTIALS = True

# Explicitly allow the methods your frontend uses
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# Headers your frontend is allowed to send
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

# HSTS (HTTP Strict Transport Security)
# Uncomment after confirming HTTPS works properly
# SECURE_HSTS_SECONDS = 31536000  # 1 year
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True

# Redirect HTTP to HTTPS (enable after HTTPS is configured)
# SECURE_SSL_REDIRECT = True

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

# ====================================
#  DATABASE (Handled in base.py)
# ====================================
# Using dj_database_url from base.py
# No need to redefine DATABASES here

# ====================================
# EMAIL SETTINGS (Inherited from base)
# ====================================
# SMTP configs come from base.py (.env provides credentials)

# ====================================
# NOTES
# ====================================
# - Ensure your Amplify frontend uses:
#     NEXT_PUBLIC_API_BASE_URL=https://api.quidpath.com/
# - Ensure ALLOWED_HOSTS includes api.quidpath.com, quidpath.com, and www.quidpath.com
# - Restart backend after saving this file:
#     docker compose restart backend
#
# ====================================
# NGINX CONFIGURATION REQUIREMENT
# ====================================
# CRITICAL: Django admin CSRF requires the Referer header.
#
# Your Nginx config MUST use:
#   add_header Referrer-Policy "strict-origin-when-cross-origin" always;
#
# NOT:
#   add_header Referrer-Policy "no-referrer" always;  (blocks CSRF)
#
# Why: Django's CSRF protection validates the Referer header to confirm same-origin
#      requests. If Nginx sends "no-referrer", the browser omits Referer entirely,
#      causing "CSRF verification failed (no Referer header)" errors in admin.
#
# "strict-origin-when-cross-origin" provides strong privacy (doesn't leak full paths)
# while still allowing Django to receive Referer for same-origin HTTPS requests.
