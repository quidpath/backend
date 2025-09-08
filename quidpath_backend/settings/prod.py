# settings/dev.py
from .base import *
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

print("Using Production Settings")

import os
print("DATABASE_URL:", os.environ.get("DATABASE_URL"))