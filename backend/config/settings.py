import os
import sys
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Local `backend/.env` should win over empty or stale process env (e.g. Windows user
# variables). Without override=True, an empty LLM_PROVIDER in the environment blocks
# values from .env and disables /api/ai/* even when .env sets LLM_PROVIDER=ollama.
load_dotenv(BASE_DIR / ".env", override=True)

DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-please-change-this-to-a-long-random-value")

if not DEBUG:
    _weak = (
        not SECRET_KEY
        or len(SECRET_KEY) < 40
        or SECRET_KEY == "change-me"
        or "dev-secret-key" in SECRET_KEY
    )
    if _weak:
        raise ImproperlyConfigured(
            "Set a strong DJANGO_SECRET_KEY in the environment when DEBUG=False (at least 40 random characters)."
        )

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "apps.users",
    "apps.forms",
    "apps.llm",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.getenv("DB_ENGINE", "postgres").lower() == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "fastforms"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- CORS (ExecutionPlan S1): permissive in DEBUG; explicit origins in production ---
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    _cors = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors.split(",") if o.strip()]
    if not CORS_ALLOWED_ORIGINS:
        sys.stderr.write(
            "WARNING: CORS_ALLOWED_ORIGINS is empty while DEBUG=False. "
            "Set CORS_ALLOWED_ORIGINS to comma-separated frontend URLs (e.g. https://app.example.com).\n"
        )

# --- HTTPS / cookies when not in DEBUG (ExecutionPlan S5) ---
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True").lower() == "true"
    SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "False").lower() == "true"
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "auth": "30/hour",
        "ai": "60/hour",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "True").lower() == "true"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@fastforms.local")

# Base URL for password-reset links emailed to users (ExecutionPlan PR1)
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")

# Google Sign-In (Web client ID from Google Cloud Console OAuth 2.0)
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()

# --- LLM (Ollama OpenAI-compatible API) — see Docs/Ollama_AI_Integration_Plan.md ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
# Use "auto" to pick a general chat model from `GET /api/tags` (prefers qwen/phi/llama over code models).
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "auto").strip()
# Read timeout for Ollama chat completion (seconds); CPU / large models often need 300s+.
_raw_ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT", "300"))
OLLAMA_TIMEOUT = max(60, min(_raw_ollama_timeout, 7200))
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()

# Privacy: set AI_LOG_VERBOSE=1 only on locked-down dev machines — logs AI prompt previews and draft titles.
AI_LOG_VERBOSE = os.getenv("AI_LOG_VERBOSE", "").strip().lower() in ("1", "true", "yes")

# Optional: delete Response+Answer rows older than N days (0 = disabled). Run: python manage.py purge_old_responses
RESPONSE_RETENTION_DAYS = int(os.getenv("RESPONSE_RETENTION_DAYS", "0"))

# Billing: free tier caps owned forms; Pro via Stripe (see .env.example)
FREE_TIER_MAX_FORMS = int(os.getenv("FREE_TIER_MAX_FORMS", "5"))
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_PRO_MONTHLY = os.getenv("STRIPE_PRICE_PRO_MONTHLY", "").strip()

# AI/Ollama lines use a tagged formatter; keep django.server so runserver request lines still appear.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "ai_console": {
            "format": "[%(levelname)s] %(asctime)s %(name)s | %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "ai_console": {
            "class": "logging.StreamHandler",
            "formatter": "ai_console",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps.llm": {
            "handlers": ["ai_console"],
            # INFO in dev without flooding DEBUG unless diagnosing; production stays WARNING.
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
        "apps.forms": {
            "handlers": ["console"],
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
    },
}
