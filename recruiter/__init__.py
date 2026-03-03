# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
# If celery is not installed, app runs without background tasks.
try:
    from .celery_app import app as celery_app
except ImportError:
    celery_app = None

__all__ = ("celery_app",)