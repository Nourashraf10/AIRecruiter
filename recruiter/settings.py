"""
Django settings for recruiter project.
"""

from pathlib import Path
import os
from decouple import config


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-7&vnfarytwk)30m+&w#-34*1&d7n0^6fl(8aj8xbikp2y)=3=h",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'django_celery_beat',

    # Local apps
    'core',
    'vacancies',
    'candidates',
    'interviews',
    'comms',
    'ai',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'recruiter.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'recruiter.wsgi.application'


# Database
if os.environ.get('USE_SQLITE', '0') == '1':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('POSTGRES_DB', cast=str),
            'USER': config('POSTGRES_USER', cast=str),
            'PASSWORD': config('POSTGRES_PASSWORD', cast=str),
            'HOST': config('POSTGRES_HOST', cast=str),  # matches docker-compose service name
            'PORT': config('POSTGRES_PORT', cast=str),
        }
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TIME_ZONE', 'Africa/Cairo')  # Egypt timezone (UTC+3)
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

# Serve static files in development
if DEBUG:
    STATICFILES_DIRS = [
        BASE_DIR / "static",
    ]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'core.User'

# DRF config
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),

    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT')
EMAIL_USE_TLS = config('EMAIL_USE_TLS')
EMAIL_USE_SSL = config('EMAIL_USE_SSL')
EMAIL_HOST_USER = config('EMAIL_HOST_USER', 'fahmy@bit68.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', 'A2kK1rYB2Ns3')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', 'fahmy@bit68.com')

##you'll have working endpoints:
#http://localhost:8040/api/users/
#http://localhost:8040/api/vacancies/
#http://localhost:8040/api/candidates/
# OAuth endpoints removed (switching to CalDAV-only read path)

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = os.environ.get('CELERY_TIMEZONE', 'Africa/Cairo')  # Egypt timezone (UTC+3)
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery Beat Schedule
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "daily_interview_scheduling": {
        "task": "comms.tasks.daily_interview_scheduling_task",
        "schedule": crontab(hour=4, minute=10),  # 10:00 AM daily
    },
    "check_feedback_requests": {
        "task": "interviews.tasks.check_and_send_feedback_requests",
        "schedule": crontab(minute='*'),  # Every minute
    },
    "check_linkedin_inbox_every_6h": {
        "task": "comms.tasks.check_linkedin_inbox",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "process_questionnaire_reply_emails": {
        "task": "interviews.tasks.process_questionnaire_reply_emails",
        "schedule": crontab(minute='*/10'),  # Every 10 minutes
    },
}