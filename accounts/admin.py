from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .models import UserProfile


def ensure_superadmin(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        raise PermissionDenied


def account_queryset(role):
    return (
        UserProfile.objects
        .select_related("user", "approved_by")
        .filter(role=role)
        .order_by("-created_at", "-id")
    )


def filtered_account_queryset(request, role):
    queryset = account_queryset(role)
    status_filter = request.GET.get("status", "").strip()
    valid_statuses = {choice[0] for choice in UserProfile.APPROVAL_STATUS_CHOICES}
    if status_filter in valid_statuses:
        queryset = queryset.filter(approval_status=status_filter)
    return queryset


def approve_profile(profile, approver):
    profile.approval_status = UserProfile.APPROVAL_APPROVED
    profile.approved_by = approver
    profile.approved_at = timezone.now()
    profile.rejection_reason = ""
    profile.user.is_active = True
    profile.user.is_staff = False
    profile.user.is_superuser = False
    profile.user.save(update_fields=["is_active", "is_staff", "is_superuser"])
    profile.save(update_fields=[
        "approval_status",
        "approved_by",
        "approved_at",
        "rejection_reason",
        "updated_at",
    ])


def reject_profile(profile, approver, reason):
    profile.approval_status = UserProfile.APPROVAL_REJECTED
    profile.approved_by = approver
    profile.approved_at = timezone.now()
    profile.rejection_reason = (reason or "").strip()
    profile.user.is_active = False
    profile.user.is_staff = False
    profile.user.is_superuser = False
    profile.user.save(update_fields=["is_active", "is_staff", "is_superuser"])
    profile.save(update_fields=[
        "approval_status",
        "approved_by",
        "approved_at",
        "rejection_reason",
        "updated_at",
    ])


def is_delete_protected_profile(profile, acting_user):
    return (
        profile.role == UserProfile.ROLE_SUPERADMIN
        or profile.user_id == acting_user.id
        or profile.user.is_superuser
    )


def delete_profile_linked_user(profile):
    user = profile.user
    user.delete()


def account_approval_list_view(request, role):
    ensure_superadmin(request)
    is_admin_role = role == UserProfile.ROLE_ADMIN
    status_filter = request.GET.get("status", "").strip()
    profiles = filtered_account_queryset(request, role)
    context = {
        **admin.site.each_context(request),
        "title": "Admin Accounts" if is_admin_role else "Requester Accounts",
        "profiles": profiles,
        "role": role,
        "is_admin_role": is_admin_role,
        "status_choices": UserProfile.APPROVAL_STATUS_CHOICES,
        "status_filter": status_filter,
        "opts": UserProfile._meta,
    }
    return TemplateResponse(request, "admin/accounts/account_approval_list.html", context)


@transaction.atomic
def account_approval_detail_view(request, profile_id, role):
    ensure_superadmin(request)
    is_admin_role = role == UserProfile.ROLE_ADMIN
    profile = get_object_or_404(account_queryset(role).select_for_update(), pk=profile_id)
    list_url = (
        "admin:accounts_admin_approvals"
        if is_admin_role
        else "admin:accounts_requester_approvals"
    )
    if profile.role == UserProfile.ROLE_SUPERADMIN or profile.user_id == request.user.id:
        messages.error(request, "This account cannot be managed from this page.")
        return redirect(reverse(list_url))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "accept":
            approve_profile(profile, request.user)
            messages.success(
                request,
                "Admin account approved successfully."
                if is_admin_role
                else "Requester account approved successfully.",
            )
            return redirect(reverse(list_url))
        if action == "reject":
            reject_profile(profile, request.user, request.POST.get("remarks", ""))
            messages.success(
                request,
                "Admin account rejected."
                if is_admin_role
                else "Requester account rejected.",
            )
            return redirect(reverse(list_url))
        messages.error(request, "Choose a valid account action.")

    context = {
        **admin.site.each_context(request),
        "title": "Admin Account Details" if is_admin_role else "Requester Account Details",
        "profile": profile,
        "role": role,
        "is_admin_role": is_admin_role,
        "opts": UserProfile._meta,
        "back_url": reverse(list_url),
    }
    return TemplateResponse(request, "admin/accounts/account_approval_detail.html", context)


def admin_account_approvals(request):
    return account_approval_list_view(request, UserProfile.ROLE_ADMIN)


def admin_account_approval_detail(request, profile_id):
    return account_approval_detail_view(request, profile_id, UserProfile.ROLE_ADMIN)


def requester_account_approvals(request):
    return account_approval_list_view(request, UserProfile.ROLE_REQUESTER)


def requester_account_approval_detail(request, profile_id):
    return account_approval_detail_view(request, profile_id, UserProfile.ROLE_REQUESTER)


def install_account_approval_admin_urls():
    original_get_urls = admin.site.get_urls
    if getattr(admin.site, "_account_approval_urls_installed", False):
        return

    def get_urls():
        custom_urls = [
            path(
                "accounts/admin-approvals/",
                admin.site.admin_view(admin_account_approvals),
                name="accounts_admin_approvals",
            ),
            path(
                "accounts/admin-approvals/<int:profile_id>/",
                admin.site.admin_view(admin_account_approval_detail),
                name="accounts_admin_approval_detail",
            ),
            path(
                "accounts/requester-approvals/",
                admin.site.admin_view(requester_account_approvals),
                name="accounts_requester_approvals",
            ),
            path(
                "accounts/requester-approvals/<int:profile_id>/",
                admin.site.admin_view(requester_account_approval_detail),
                name="accounts_requester_approval_detail",
            ),
        ]
        return custom_urls + original_get_urls()

    admin.site.get_urls = get_urls
    admin.site._account_approval_urls_installed = True


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "role",
        "approval_status",
        "created_at",
        "updated_at",
    )
    list_filter = ("role", "approval_status")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "department",
        "mobile",
    )
    readonly_fields = (
        "user",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    )
    fields = (
        "user",
        "role",
        "approval_status",
        "approved_by",
        "approved_at",
        "rejection_reason",
        "designation",
        "department",
        "mobile",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .exclude(role=UserProfile.ROLE_SUPERADMIN)
        )

    def has_module_permission(self, request):
        return bool(request.user and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "rejection_reason" and formfield is not None:
            formfield.label = "Remarks"
        return formfield

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.approval_status in {
            UserProfile.APPROVAL_APPROVED,
            UserProfile.APPROVAL_REJECTED,
        }:
            approval_field = form.base_fields.get("approval_status")
            if approval_field is not None:
                approval_field.choices = [
                    choice for choice in approval_field.choices
                    if choice[0] != UserProfile.APPROVAL_PENDING
                ]
        return form

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                UserProfile.objects
                .filter(pk=obj.pk)
                .values_list("approval_status", flat=True)
                .first()
            )

        if (
            previous_status in {
                UserProfile.APPROVAL_APPROVED,
                UserProfile.APPROVAL_REJECTED,
            }
            and obj.approval_status == UserProfile.APPROVAL_PENDING
        ):
            obj.approval_status = previous_status
            self.message_user(
                request,
                "Approved or rejected accounts cannot be moved back to pending.",
                level=messages.ERROR,
            )
            return

        if (
            obj.approval_status == UserProfile.APPROVAL_REJECTED
            and obj.approval_status != previous_status
        ):
            if is_delete_protected_profile(obj, request.user):
                self.message_user(
                    request,
                    "Protected account was skipped.",
                    level=messages.WARNING,
                )
                return
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
            obj.user.is_active = False
            obj.user.is_staff = False
            obj.user.is_superuser = False
            obj.user.save(update_fields=["is_active", "is_staff", "is_superuser"])
            self.message_user(
                request,
                "Account rejected. The user can no longer login.",
                level=messages.SUCCESS,
            )

        if (
            obj.approval_status == UserProfile.APPROVAL_APPROVED
            and obj.approval_status != previous_status
        ):
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
            obj.rejection_reason = ""
            obj.user.is_active = True
            obj.user.is_staff = False
            obj.user.is_superuser = False
            obj.user.save(update_fields=["is_active", "is_staff", "is_superuser"])

        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        if is_delete_protected_profile(obj, request.user):
            self.message_user(
                request,
                "Protected account was skipped.",
                level=messages.WARNING,
            )
            return
        try:
            delete_profile_linked_user(obj)
        except ProtectedError as exc:
            self.message_user(
                request,
                f"Could not delete account because related protected data exists: {exc}",
                level=messages.ERROR,
            )

    def delete_queryset(self, request, queryset):
        deleted_count = 0
        skipped_count = 0
        protected_error_count = 0
        profiles = list(queryset.select_related("user"))

        with transaction.atomic():
            for profile in profiles:
                if is_delete_protected_profile(profile, request.user):
                    skipped_count += 1
                    continue
                try:
                    delete_profile_linked_user(profile)
                except ProtectedError:
                    protected_error_count += 1
                    continue
                deleted_count += 1

        if deleted_count:
            self.message_user(
                request,
                f"{deleted_count} linked user account(s) deleted.",
                level=messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} protected account(s) skipped.",
                level=messages.WARNING,
            )
        if protected_error_count:
            self.message_user(
                request,
                (
                    f"{protected_error_count} account(s) could not be deleted because "
                    "related protected data exists."
                ),
                level=messages.ERROR,
            )


install_account_approval_admin_urls()
