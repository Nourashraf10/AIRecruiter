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
IS_PRODUCTION = config("IS_PRODUCTION", default=False, cast=bool)

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

STATIC_URL = '/static/'
MEDIA_URL = '/media/'

if IS_PRODUCTION:
    STATIC_ROOT = "/var/www/html/recruiter/static"
    MEDIA_ROOT = "/var/www/html/recruiter/media"
else:
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"
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

CSRF_TRUSTED_ORIGINS = [
    "https://recruiter.staging-bit68.com",
]

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', config('EMAIL_HOST', default='smtppro.zoho.com'))
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', config('EMAIL_PORT', default='465')))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', config('EMAIL_USE_TLS', default='False')) in ['True', 'true', '1']
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', config('EMAIL_USE_SSL', default='True')) in ['True', 'true', '1']
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER') or config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD') or config('EMAIL_HOST_PASSWORD')

# Company email addresses (loaded from environment)
DEFAULT_MANAGER_EMAIL = os.environ.get('DEFAULT_MANAGER_EMAIL') or config('DEFAULT_MANAGER_EMAIL', default='')
AI_RECRUITER_EMAIL = os.environ.get('AI_RECRUITER_EMAIL') or config('AI_RECRUITER_EMAIL', default='')
APPLICATION_EMAIL = os.environ.get('APPLICATION_EMAIL') or config('APPLICATION_EMAIL', default='')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', config('DEFAULT_FROM_EMAIL', default=None)) or EMAIL_HOST_USER

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
    "check_linkedin_inbox_every_minute": {
        "task": "comms.tasks.check_linkedin_inbox",
        "schedule": crontab(minute="*"),
    },
    "process_questionnaire_reply_emails": {
        "task": "interviews.tasks.process_questionnaire_reply_emails",
        "schedule": crontab(minute='*'),  # Every minute
    },
    "process_manager_feedback_emails": {
        "task": "interviews.tasks.process_manager_feedback_emails",
        "schedule": crontab(minute='*'),  # Every minute
    },
}