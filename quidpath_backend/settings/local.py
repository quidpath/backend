# settings/dev.py
from .base import *

DEBUG = True  # Enable debug mode for development
# Allow localhost and 127.0.0.1 for local development
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
# You can add any other development-specific settings here
