import os
import dj_database_url

# ✅ Only set production-specific overrides here
# Don't re-import everything from settings

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

# ✅ Extend existing ALLOWED_HOSTS instead of replacing
if RENDER_EXTERNAL_HOSTNAME:
    # In production on Render
    ALLOWED_HOSTS = [
        RENDER_EXTERNAL_HOSTNAME,
        'scholar-panel.vercel.app',
        'localhost',
        '127.0.0.1',
    ]
    
    CSRF_TRUSTED_ORIGINS = [
        f'https://{RENDER_EXTERNAL_HOSTNAME}',
        'https://scholar-panel.vercel.app',
    ]
    
    CORS_ALLOWED_ORIGINS = [
        'https://scholar-panel.vercel.app',
    ]

# Force production mode
DEBUG = False

# ✅ Use environment variable for SECRET_KEY
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set in production")

# Database configuration for Render
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True,
    )
}

# Static files storage (Whitenoise for Render)
STORAGES = {
    'default': {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    }
}

# ✅ IMPORTANT: Do NOT override cookie settings here
# Let settings.py handle all cookie configurations
# The main settings.py already has correct values:
# - COOKIE_DOMAIN = None (works cross-domain)
# - COOKIE_SAMESITE = "None" (for cross-site)
# - SECURE = True (for HTTPS)