# comms/models.py
from django.db import models

class OutgoingEmail(models.Model):
    to_address = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True)
    meta = models.JSONField(null=True, blank=True)  # provider metadata, message-id, etc.
    created_at = models.DateTimeField(auto_now_add=True)

class IncomingEmail(models.Model):
    from_address = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    meta = models.JSONField(null=True, blank=True)
