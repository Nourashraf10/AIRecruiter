from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Profile', {'fields': ('display_name',)}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'display_name', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'display_name')
