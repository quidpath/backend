# settings/prod.py
from .base import *
import os
import logging
from corsheaders.defaults import default_headers

logger = logging.getLogger(__name__)
print("Using Production Settings")

# ====================================
# 🔒 SECURITY SETTINGS
# ====================================
DEBUG = False

# Load allowed hosts from environment (comma-separated)
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "api.quidpath.com").split(",")

# ====================================
# 🧩 CSRF & CORS CONFIGURATION
# ====================================
CSRF_TRUSTED_ORIGINS = [
    "https://quidpath.com",
    "https://www.quidpath.com",
]

# --- CORS CONFIGURATION ---
CORS_ALLOW_ALL_ORIGINS = False  # GOOD: Override base.py

# These are the *only* origins that can make browser requests
CORS_ALLOWED_ORIGINS = [
    "https://quidpath.com",
    "https://www.quidpath.com",
    "https://quidpath-erp-frontend-production.up.railway.app",
    "http://localhost:3000",
    "http://localhost:3001",
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
    "x-requested-with",
    "accept",
    "origin",
    "access-control-request-method",
    "access-control-request-headers",
]

# ====================================
# ⚙️ STATIC & MEDIA FILES
# ====================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ====================================
# 🧱 SECURITY MIDDLEWARE HEADERS
# ====================================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ====================================
# 📜 LOGGING CONFIGURATION
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
# 💾 DATABASE (Handled in base.py)
# ====================================
# Using dj_database_url from base.py
# No need to redefine DATABASES here

# ====================================
# 📧 EMAIL SETTINGS (Inherited from base)
# ====================================
# SMTP configs come from base.py (.env provides credentials)

# ====================================
# ✅ NOTES
# ====================================
# - Ensure your Amplify frontend uses:
#     NEXT_PUBLIC_API_BASE_URL=https://api.quidpath.com/
# - Ensure ALLOWED_HOSTS includes api.quidpath.com, quidpath.com, and www.quidpath.com
# - Restart backend after saving this file:
#     docker compose restart backend