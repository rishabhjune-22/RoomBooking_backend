from rest_framework.permissions import BasePermission

from .roles import is_admin, is_admin_like, is_approved, is_requester, is_superadmin


class IsApprovedUser(BasePermission):
    message = "Approved account is required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_approved(request.user))


class IsSuperAdminRole(BasePermission):
    message = "Superadmin access is required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_superadmin(request.user))


class IsAdminRole(BasePermission):
    message = "Admin access is required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_admin_like(request.user))


class IsAdminOrSuperAdminRole(IsAdminRole):
    pass


class IsRequesterRole(BasePermission):
    message = "Requester access is required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_requester(request.user))
