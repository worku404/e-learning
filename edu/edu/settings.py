"""
Settings for the edu project.
"""

import os
from pathlib import Path  # Standard library: build OS-safe filesystem paths
from django.urls import reverse_lazy  # Django utility: resolve URL names lazily at runtime
from dotenv import load_dotenv
from decouple import config
import dj_database_url


# Core project paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from either project root or settings directory.
for _env_path in (BASE_DIR / ".env", BASE_DIR / "edu" / ".env"):
    if _env_path.exists():
        load_dotenv(_env_path)

# Authentication behavior
# Redirect authenticated users to the student course list after login.
LOGIN_REDIRECT_URL = reverse_lazy("student_course_list")


# Security and runtime mode
SECRET_KEY = config("SECRET_KEY")  # set in environment for production
# DEBUG = True
# ALLOWED_HOSTS = []
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*").split(",")


# Application registration
INSTALLED_APPS = [
    'daphne',
    # Project apps (keep this app first as requested for auth monitoring/dependency order)
    "courses.apps.CoursesConfig",

    # Django built-in apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Project apps
    "students.apps.StudentsConfig",
    'assistant.apps.AssistantConfig',
    'chat.apps.ChatConfig',
    

    # Third-party apps
    "embed_video",   # Embed and render video content in templates/models
    "debug_toolbar", # Development-time request/SQL/debug inspection
    "redisboard",    # Redis monitoring dashboard
    'rest_framework', # To build an API
    'rest_framework.authtoken', # DRF token authentication model
    'storages',

]


# Middleware pipeline (request/response processing order matters)
MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",          # Third-party middleware
    "django.middleware.security.SecurityMiddleware",            # Built-in: security headers and protections
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",     # Built-in: session support

    # Enable these only if full-site cache middleware is needed:
    # "django.middleware.cache.UpdateCacheMiddleware",          # Built-in: stores cache for responses

    "django.middleware.common.CommonMiddleware",                # Built-in: URL rewriting, ETags, etc.

    # "django.middleware.cache.FetchFromCacheMiddleware",       # Built-in: serves cached responses

    "django.middleware.csrf.CsrfViewMiddleware",                # Built-in: CSRF protection
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # Built-in: attaches authenticated user
    "django.contrib.messages.middleware.MessageMiddleware",     # Built-in: one-time message framework
    "django.middleware.clickjacking.XFrameOptionsMiddleware",   # Built-in: clickjacking protection
]


CSRF_TRUSTED_ORIGINS = [
    'https://e-learning-aae0.onrender.com',
]
# URL and template configuration
ROOT_URLCONF = "edu.urls"

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
                "assistant.context_processors.llm_widget",
                'students.context_processors.global_progress',
            ],
        },
    },
]

WSGI_APPLICATION = "edu.wsgi.application"


# Database
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

DATABASE_URL = config("DATABASE_URL", default="").strip()
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=True,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Localization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static and media files
STATIC_URL = "static/"
MEDIA_URL = "media/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = Path(config("MEDIA_ROOT", default=str(BASE_DIR / "media")))
# STATIC_FILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

USE_B2 = config("USE_B2", default=False, cast=bool)

if USE_B2:
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME")
    AWS_S3_ENDPOINT_URL = config("AWS_S3_ENDPOINT_URL")

    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = True  # private bucket
    AWS_QUERYSTRING_EXPIRE = 3600

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }
else:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }


# Security headers
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"


# Cache configuration (Redis)
# CACHES = {
import os

# Use environment variable REDIS_URL if available (Render), 
# otherwise fallback to Local Memory for development.
REDIS_URL = os.getenv("REDIS_URL")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }

from urllib.parse import urlparse

# Get the Redis URL from the environment or use a default value
redis_url = config('REDIS_URL', default='redis://127.0.0.1:6379/0')

# Parse the Redis URL
url = urlparse(redis_url)

# Extract Redis connection details
REDIS_HOST = url.hostname or '127.0.0.1'
REDIS_PORT = url.port or 6379
REDIS_DB = int(url.path[1:]) if url.path[1:].isdigit() else 0
REDIS_PASSWORD = url.password or None
# Development local IPs (used by debug-toolbar)
INTERNAL_IPS = ["127.0.0.1"]

# Cache middleware settings
CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 60 * 15  # 15 minutes
CACHE_MIDDLEWARE_KEY_PREFIX = "educa"


# GEMINI API
API1_KEY = os.getenv("API1_KEY")
API2_KEY = os.getenv("API2_KEY")
API3_KEY = os.getenv("API3_KEY")
API4_KEY = os.getenv("API4_KEY")

# API
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
    ]
}
ASGI_APPLICATION = 'edu.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
        },
    },
}
