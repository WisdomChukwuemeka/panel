from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv
from corsheaders.defaults import default_headers
from decouple import config
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False") == "True"

# ✅ CRITICAL: Cookie settings must work for cross-domain (Vercel → Render)
# For production: cookies must NOT have a domain set to work across subdomains
SECURE = not DEBUG
COOKIE_SAMESITE = "None" if not DEBUG else "Lax"
COOKIE_DOMAIN = None  # ✅ CHANGED: Let browser handle domain automatically

PAYSTACK_PUBLIC_KEY = config("PAYSTACK_PUBLIC_KEY", default="")
PAYSTACK_SECRET_KEY = config("PAYSTACK_SECRET_KEY", default="")

if not PAYSTACK_SECRET_KEY or not PAYSTACK_PUBLIC_KEY:
    raise ValueError("PAYSTACK keys missing in .env")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'cloudinary_storage',
    'cloudinary',

    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',

    'accounts',
    'userprofile',
    'publications',
    'payments',
    'messagebox',
    'comments',
    'points',
    'rewardcode',
    'tasks',
    'emoji',
    'conference',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ALLOWED_HOSTS = [
    "panel-1-tlqv.onrender.com",
    "scholar-panel.vercel.app",
    "localhost",
    "127.0.0.1",
]

CSRF_TRUSTED_ORIGINS = [
    "https://panel-1-tlqv.onrender.com",
    "https://scholar-panel.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOWED_ORIGINS = [
    "https://scholar-panel.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
]

APPEND_SLASH = False

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    "Cookie",
    "authorization",
]

CORS_EXPOSE_HEADERS = ["Set-Cookie"]

# ✅ Session and CSRF cookie settings
SESSION_COOKIE_SECURE = SECURE
CSRF_COOKIE_SECURE = SECURE
SESSION_COOKIE_SAMESITE = COOKIE_SAMESITE
CSRF_COOKIE_SAMESITE = COOKIE_SAMESITE
SESSION_COOKIE_DOMAIN = COOKIE_DOMAIN
CSRF_COOKIE_DOMAIN = COOKIE_DOMAIN

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "accounts.User"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "verify-passcode": "5/hour",
    },
}

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///db.sqlite3",
        conn_max_age=600,
        ssl_require=not DEBUG,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = "api/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": os.getenv("CLOUDINARY_API_KEY"),
    "API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
    "SECURE": True,
}

DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ✅ Import deployment settings if they exist (but they shouldn't override cookie settings)
try:
    from .deployment_settings import *
except ImportError:
    pass