import os
import dj_database_url
from .settings import *
from .settings import BASE_DIR

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

ALLOWED_HOSTS = []
CSRF_TRUSTED_ORIGINS = []

if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append('https://' + RENDER_EXTERNAL_HOSTNAME)
else:
    # Fallback for development / debugging
    ALLOWED_HOSTS += ['localhost', '127.0.0.1', 'base-panel-3.onrender.com']
    CSRF_TRUSTED_ORIGINS += ['https://base-panel-3.onrender.com', 'https://scholar-ra71.vercel.app']



DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-CHANGE-THIS-DEV-KEY')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # keep here
    'corsheaders.middleware.CorsMiddleware',        # move up here
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


CORS_ALLOWED_ORIGINS = [
    "https://scholar-ra71.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3001",
]

STORAGES = {
    'default': {
        'BACKEND': "django.core.files.storage.FileSystemStorage",  
    },
    'staticfiles': {
        "BACKEND" : "whitenoise.storage.CompressedStaticFilesStorage",
    }
}


DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3'),
        conn_max_age=600,
    )
}

