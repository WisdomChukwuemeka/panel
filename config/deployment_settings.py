import os
import dj_database_url
from .settings import *
from .settings import BASE_DIR

# Only override what actually needs to change on Render
DEBUG = False

# Keep everything from settings.py and just ADD the Render host
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Make sure Vercel is still allowed (critical!)
if 'scholar-panel.vercel.app' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('scholar-panel.vercel.app')
if 'https://scholar-panel.vercel.app' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append('https://scholar-panel.vercel.app')

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR}/db.sqlite3'),
        conn_max_age=600,
    )
}

# Static files
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}