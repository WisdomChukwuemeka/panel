import os
import dj_database_url

# ✅ Only apply these settings if we're actually on Render
# Check for Render-specific environment variable
IS_RENDER = os.environ.get('RENDER_EXTERNAL_HOSTNAME') is not None

if IS_RENDER:
    # Production settings for Render only
    RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

    ALLOWED_HOSTS = [
        RENDER_EXTERNAL_HOSTNAME,
        'scholar-panel.vercel.app',
        'localhost',
        '127.0.0.1',
    ]
    
    CORS_ALLOW_CREDENTIALS = True
    
    CSRF_TRUSTED_ORIGINS = [
        f'https://{RENDER_EXTERNAL_HOSTNAME}',
        'https://scholar-panel.vercel.app',
    ]
    
    CORS_ALLOWED_ORIGINS = [
        'https://scholar-panel.vercel.app',
    ]

    # Force production mode
    DEBUG = False

    # Use environment variable for SECRET_KEY
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set in production")

    # Database configuration for Render (PostgreSQL)
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
else:
    # Local development - don't override anything
    # Let settings.py handle all configuration
    pass