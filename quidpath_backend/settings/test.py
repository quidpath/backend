# settings/test.py
from .base import *
DEBUG = True  # Set to True for testing
ALLOWED_HOSTS = ['localhost']
# Test database
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': BASE_DIR / 'test_db.sqlite3',
}
# Additional test-specific settings can go here