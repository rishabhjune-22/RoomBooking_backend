from .models import UserProfile


ROLE_SUPERADMIN = UserProfile.ROLE_SUPERADMIN
ROLE_ADMIN = UserProfile.ROLE_ADMIN
ROLE_REQUESTER = UserProfile.ROLE_REQUESTER
APPROVAL_PENDING = UserProfile.APPROVAL_PENDING
APPROVAL_APPROVED = UserProfile.APPROVAL_APPROVED
APPROVAL_REJECTED = UserProfile.APPROVAL_REJECTED


def get_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if user and user.is_superuser and (
            profile.role != ROLE_SUPERADMIN
            or profile.approval_status != APPROVAL_APPROVED
    ):
        profile.role = ROLE_SUPERADMIN
        profile.approval_status = APPROVAL_APPROVED
        profile.rejection_reason = ""
        profile.save(update_fields=[
            "role",
            "approval_status",
            "rejection_reason",
            "updated_at",
        ])
    return profile


def get_user_role(user):
    if not user or not user.is_authenticated:
        return ""
    return get_user_profile(user).role


def set_user_role(user, role, **profile_fields):
    profile = get_user_profile(user)
    profile.role = role
    if "approval_status" not in profile_fields:
        profile.approval_status = (
            APPROVAL_APPROVED if role != ROLE_SUPERADMIN else APPROVAL_APPROVED
        )
    for field, value in profile_fields.items():
        if hasattr(profile, field):
            if isinstance(value, str):
                value = value.strip()
            setattr(profile, field, value or "")
    profile.save()
    return profile


def get_user_approval_status(user):
    if not user or not user.is_authenticated:
        return ""
    return get_user_profile(user).approval_status


def is_approved(user):
    return bool(
        user
        and user.is_authenticated
        and get_user_profile(user).approval_status == APPROVAL_APPROVED
    )


def is_superadmin(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or get_user_profile(user).role == ROLE_SUPERADMIN
        )
        and is_approved(user)
    )


def is_admin(user):
    return is_approved(user) and get_user_role(user) == ROLE_ADMIN


def is_admin_like(user):
    return is_admin(user) or is_superadmin(user)


def is_requester(user):
    return is_approved(user) and get_user_role(user) == ROLE_REQUESTER
