# settings/dev.py
from .base import *

if os.environ.get("DJANGO_ENV") == "dev":
    DEBUG = True
    ALLOWED_HOSTS = ["*"]
print("Using Development Settings")

import os

print("DATABASE_URL:", os.environ.get("DATABASE_URL"))
