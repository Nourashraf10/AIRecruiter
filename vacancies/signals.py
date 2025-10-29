import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Vacancy
from comms.simple_automation_service import SimpleAutomationService

logger = logging.getLogger(__name__)

# Signal removed - automation now runs on daily schedule instead of status change