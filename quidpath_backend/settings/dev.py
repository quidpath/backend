# settings/dev.py
from .base import *
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
print("Using Development Settings")
# Development database
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': BASE_DIR / 'dev_db.sqlite3',
}
# Additional dev-specific settings can go here
