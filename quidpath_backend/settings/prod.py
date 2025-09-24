# settings/prod.py
from .base import *
import os
import dj_database_url

DEBUG = False  # Best practice: keep False in prod

# Allow Railway & Azure hosts
ALLOWED_HOSTS = ['*']

print("Using Production Settings")

# Database config
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    raise Exception("❌ DATABASE_URL not set! Cannot connect to DB.")
