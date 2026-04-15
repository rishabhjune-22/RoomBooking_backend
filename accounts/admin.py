from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


class CustomUserAdmin(BaseUserAdmin):

    # 👉 Add custom fields in existing sections (IMPORTANT)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "phone")}),
        ("🔐 Encryption", {"fields": ("encrypted_dek", "dek_wrap_nonce", "kdf_metadata")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    # 👉 For user creation form
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "phone", "password1", "password2"),
        }),
    )

    # 👉 Show in list view
    list_display = ("username", "email", "phone", "is_staff", )

    search_fields = ("username", "email", "phone")

    ordering = ("username",)


admin.site.register(User, CustomUserAdmin)