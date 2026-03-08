import importlib.util
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name, default):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a number.")


DJANGO_ENV = (os.getenv("DJANGO_ENV") or "").strip().lower()
DEBUG = _env_bool("DJANGO_DEBUG", DJANGO_ENV != "production")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        secret_key_file = BASE_DIR / ".django_secret_key"
        if secret_key_file.exists():
            SECRET_KEY = secret_key_file.read_text(encoding="utf-8").strip()
        else:
            SECRET_KEY = get_random_secret_key()
            secret_key_file.write_text(SECRET_KEY, encoding="utf-8")
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")

ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be configured in production.")

CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "salon",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "salon.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "saloon_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "salon.context_processors.reminder_popup_context",
            ],
        },
    },
]

WSGI_APPLICATION = "saloon_project.wsgi.application"
ASGI_APPLICATION = "saloon_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.ScryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
if importlib.util.find_spec("argon2") is not None:
    PASSWORD_HASHERS.insert(0, "django.contrib.auth.hashers.Argon2PasswordHasher")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/owner/"
LOGOUT_REDIRECT_URL = "/"
PASSWORD_RESET_TIMEOUT = int(os.getenv("SALOON_PASSWORD_RESET_TIMEOUT", "86400"))

EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@saloonhub.local")

SECURE_SSL_REDIRECT = _env_bool("SALOON_SECURE_SSL_REDIRECT", not DEBUG)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.getenv("SALOON_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0 and not DEBUG
SECURE_HSTS_PRELOAD = SECURE_HSTS_INCLUDE_SUBDOMAINS

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

LOGIN_MAX_ATTEMPTS = int(os.getenv("SALOON_LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("SALOON_LOGIN_LOCKOUT_SECONDS", "900"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
WHATSAPP_DEFAULT_COUNTRY_CODE = os.getenv("WHATSAPP_DEFAULT_COUNTRY_CODE", "91").lstrip("+")
WHATSAPP_RATE_LIMIT_SECONDS = _env_float("WHATSAPP_RATE_LIMIT_SECONDS", 0.5)
WHATSAPP_TIMEOUT_SECONDS = _env_float("WHATSAPP_TIMEOUT_SECONDS", 10.0)
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v17.0")

OPENAI_STYLE_ADVISOR_MODEL = os.getenv("OPENAI_STYLE_ADVISOR_MODEL", "gpt-4.1-mini")

MSG91_AUTH_KEY = os.getenv("MSG91_AUTH_KEY", "")
MSG91_SMS_TEMPLATE_ID = os.getenv("MSG91_SMS_TEMPLATE_ID", "")
MSG91_WHATSAPP_TEMPLATE_ID = os.getenv("MSG91_WHATSAPP_TEMPLATE_ID", "")
MSG91_COUNTRY_CODE = os.getenv("MSG91_COUNTRY_CODE", "91")
MSG91_TIMEOUT_SECONDS = _env_float("MSG91_TIMEOUT_SECONDS", 10.0)

SALOON_OTP_TTL_SECONDS = int(os.getenv("SALOON_OTP_TTL_SECONDS", "300"))
SALOON_OTP_MAX_ATTEMPTS = int(os.getenv("SALOON_OTP_MAX_ATTEMPTS", "5"))
SALOON_OTP_LOG_ENABLED = _env_bool("SALOON_OTP_LOG_ENABLED", DEBUG)
SALOON_SHOW_OTP_PROVIDER_ID = _env_bool("SALOON_SHOW_OTP_PROVIDER_ID", DEBUG)
