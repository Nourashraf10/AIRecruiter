from django.contrib import admin
from .models import IncomingEmail, OutgoingEmail


@admin.register(IncomingEmail)
class IncomingEmailAdmin(admin.ModelAdmin):
    list_display = ("id", "from_address", "subject", "received_at", "processed")
    list_filter = ("processed",)
    search_fields = ("from_address", "subject")


@admin.register(OutgoingEmail)
class OutgoingEmailAdmin(admin.ModelAdmin):
    list_display = ("id", "to_address", "subject", "sent_at")
    search_fields = ("to_address", "subject")
