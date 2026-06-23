from django.contrib.auth import get_user_model
from django.contrib import admin as django_admin
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile
from accounts.roles import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    ROLE_ADMIN,
    ROLE_REQUESTER,
    ROLE_SUPERADMIN,
    get_user_profile,
    set_user_role,
)
User = get_user_model()


@override_settings(ADMIN_SIGNUP_CODE="test-admin-code")
class AuthApiTests(TestCase):
    def test_signup_success_returns_pending_user_without_tokens(self):
        response = self.client.post(
            reverse("auth-signup"),
            data={
                "name": "Rishabh Kumar",
                "email": "rishabh@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "test-admin-code",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIn("superadmin approval", body["message"].lower())
        self.assertEqual(body["data"]["user"]["name"], "Rishabh Kumar")
        self.assertEqual(body["data"]["user"]["email"], "rishabh@example.com")
        self.assertEqual(body["data"]["user"]["role"], "admin")
        self.assertEqual(body["data"]["user"]["approval_status"], APPROVAL_PENDING)
        self.assertEqual(body["data"]["user"]["remarks"], "")
        self.assertNotIn("rejection_reason", body["data"]["user"])
        self.assertNotIn("access", body["data"])
        self.assertNotIn("refresh", body["data"])
        self.assertTrue(User.objects.filter(email="rishabh@example.com").exists())

    def test_admin_signup_wrong_code_rejected(self):
        response = self.client.post(
            reverse("auth-admin-signup"),
            data={
                "name": "Rishabh Kumar",
                "email": "rishabh@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "wrong",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("admin_code", response.json()["errors"])

    def test_requester_signup_success(self):
        response = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "Requester One",
                "email": "requester@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "department": "CSE",
                "designation": "Student",
                "mobile": "9876543210",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user_data = response.json()["data"]["user"]
        self.assertEqual(user_data["role"], "requester")
        self.assertEqual(user_data["approval_status"], APPROVAL_PENDING)
        self.assertEqual(user_data["remarks"], "")
        self.assertNotIn("rejection_reason", user_data)
        self.assertEqual(user_data["department"], "CSE")

    def test_signup_duplicate_email_rejected(self):
        existing = User.objects.create_user(
            username="rishabh@example.com",
            email="rishabh@example.com",
            password="StrongPass123",
        )
        set_user_role(existing, ROLE_ADMIN, approval_status=APPROVAL_APPROVED)

        response = self.client.post(
            reverse("auth-signup"),
            data={
                "name": "Rishabh Kumar",
                "email": "RISHABH@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "test-admin-code",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("email", response.json()["errors"])

    def test_admin_signup_with_rejected_existing_account_is_rejected_as_duplicate(self):
        legacy = User.objects.create_user(
            username="rejected-admin@example.com",
            email="rejected-admin@example.com",
            password="StrongPass123",
            first_name="Rejected Admin",
        )
        set_user_role(legacy, ROLE_ADMIN, approval_status=APPROVAL_REJECTED)

        response = self.client.post(
            reverse("auth-admin-signup"),
            data={
                "name": "New Admin",
                "email": "rejected-admin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "test-admin-code",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(id=legacy.id).exists())
        self.assertIn("email", response.json()["errors"])

    def test_requester_signup_with_rejected_existing_account_is_rejected_as_duplicate(self):
        legacy = User.objects.create_user(
            username="rejected-requester@example.com",
            email="rejected-requester@example.com",
            password="StrongPass123",
            first_name="Rejected Requester",
        )
        set_user_role(legacy, ROLE_REQUESTER, approval_status=APPROVAL_REJECTED)

        response = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "New Requester",
                "email": "rejected-requester@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "department": "CSE",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(id=legacy.id).exists())
        self.assertIn("email", response.json()["errors"])

    def test_signup_with_orphan_account_is_rejected_as_duplicate(self):
        orphan = User.objects.create_user(
            username="orphan@example.com",
            email="orphan@example.com",
            password="StrongPass123",
        )
        self.assertFalse(UserProfile.objects.filter(user=orphan).exists())

        response = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "Recovered User",
                "email": "orphan@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(id=orphan.id).exists())
        self.assertIn("email", response.json()["errors"])

    def test_login_success_returns_user_and_tokens(self):
        user = User.objects.create_user(
            username="rishabh@example.com",
            email="rishabh@example.com",
            password="StrongPass123",
            first_name="Rishabh Kumar",
        )
        set_user_role(user, ROLE_ADMIN)

        response = self.client.post(
            reverse("auth-login"),
            data={
                "email": "rishabh@example.com",
                "password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["message"], "Login successful.")
        self.assertEqual(body["data"]["user"]["name"], "Rishabh Kumar")
        self.assertEqual(body["data"]["user"]["role"], "admin")
        self.assertEqual(body["data"]["user"]["approval_status"], APPROVAL_APPROVED)
        self.assertEqual(body["data"]["user"]["remarks"], "")
        self.assertNotIn("rejection_reason", body["data"]["user"])
        self.assertIn("access", body["data"])
        self.assertIn("refresh", body["data"])

    def test_pending_admin_cannot_login(self):
        signup = self.client.post(
            reverse("auth-admin-signup"),
            data={
                "name": "Admin Pending",
                "email": "pending-admin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "test-admin-code",
            },
            content_type="application/json",
        )
        self.assertEqual(signup.status_code, status.HTTP_201_CREATED)

        response = self.client.post(
            reverse("auth-admin-login"),
            data={
                "email": "pending-admin@example.com",
                "password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pending approval", response.json()["message"])

    def test_rejected_requester_cannot_login_and_reason_is_returned(self):
        user = User.objects.create_user(
            username="rejected@example.com",
            email="rejected@example.com",
            password="StrongPass123",
            first_name="Rejected User",
        )
        profile = set_user_role(user, ROLE_REQUESTER, approval_status=APPROVAL_REJECTED)
        profile.rejection_reason = "Invalid department."
        profile.save(update_fields=["rejection_reason"])

        response = self.client.post(
            reverse("auth-requester-login"),
            data={
                "email": "rejected@example.com",
                "password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("rejected", response.json()["message"])
        self.assertIn("Remarks:", response.json()["message"])
        self.assertNotIn("Reason:", response.json()["message"])
        self.assertIn("Invalid department", response.json()["message"])

    def test_inactive_rejected_user_cannot_login_with_rejected_message(self):
        user = User.objects.create_user(
            username="inactive-rejected@example.com",
            email="inactive-rejected@example.com",
            password="StrongPass123",
            first_name="Rejected User",
            is_active=False,
        )
        set_user_role(user, ROLE_ADMIN, approval_status=APPROVAL_REJECTED)

        response = self.client.post(
            reverse("auth-admin-login"),
            data={
                "email": "inactive-rejected@example.com",
                "password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("account is rejected", response.json()["message"].lower())

    def test_login_wrong_password_rejected(self):
        User.objects.create_user(
            username="rishabh@example.com",
            email="rishabh@example.com",
            password="StrongPass123",
        )

        response = self.client.post(
            reverse("auth-login"),
            data={
                "email": "rishabh@example.com",
                "password": "WrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["message"], "Invalid email or password.")

    def test_me_requires_token_and_returns_user(self):
        unauthenticated = self.client.get(reverse("auth-me"))
        self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)

        user = User.objects.create_user(
            username="rishabh@example.com",
            email="rishabh@example.com",
            password="StrongPass123",
            first_name="Rishabh Kumar",
        )
        set_user_role(user, ROLE_ADMIN)
        token = str(RefreshToken.for_user(user).access_token)

        authenticated = self.client.get(
            reverse("auth-me"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(authenticated.status_code, status.HTTP_200_OK)
        self.assertEqual(authenticated.json()["data"]["email"], "rishabh@example.com")
        self.assertEqual(authenticated.json()["data"]["role"], "admin")
        self.assertEqual(authenticated.json()["data"]["approval_status"], APPROVAL_APPROVED)
        self.assertEqual(authenticated.json()["data"]["remarks"], "")
        self.assertNotIn("rejection_reason", authenticated.json()["data"])

    def test_role_specific_login_rejects_mismatch(self):
        requester_signup = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "Requester One",
                "email": "requester@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )
        self.assertEqual(requester_signup.status_code, status.HTTP_201_CREATED)

        response = self.client.post(
            reverse("auth-admin-login"),
            data={
                "email": "requester@example.com",
                "password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not an admin", response.json()["message"])

        admin_signup = self.client.post(
            reverse("auth-admin-signup"),
            data={
                "name": "Admin One",
                "email": "admin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "test-admin-code",
            },
            content_type="application/json",
        )
        self.assertEqual(admin_signup.status_code, status.HTTP_201_CREATED)

        requester_login = self.client.post(
            reverse("auth-requester-login"),
            data={
                "email": "admin@example.com",
                "password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(requester_login.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not a requester", requester_login.json()["message"])


@override_settings(ADMIN_SIGNUP_CODE="test-admin-code")
class AccountApprovalApiTests(TestCase):
    def bearer(self, user):
        return f"Bearer {RefreshToken.for_user(user).access_token}"

    def create_superadmin(self):
        user = User.objects.create_superuser(
            username="super@example.com",
            email="super@example.com",
            password="StrongPass123",
            first_name="Super Admin",
        )
        profile = get_user_profile(user)
        self.assertEqual(profile.role, ROLE_SUPERADMIN)
        self.assertEqual(profile.approval_status, APPROVAL_APPROVED)
        return user

    def create_approved_admin(self, email="admin@example.com"):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="StrongPass123",
            first_name="Admin User",
        )
        set_user_role(user, ROLE_ADMIN)
        return user

    def create_pending_requester(self, email="requester@example.com"):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="StrongPass123",
            first_name="Requester User",
        )
        set_user_role(user, ROLE_REQUESTER, approval_status=APPROVAL_PENDING)
        return user

    def test_superuser_profile_becomes_superadmin_approved(self):
        superadmin = self.create_superadmin()

        self.assertTrue(superadmin.is_staff)
        self.assertTrue(superadmin.is_superuser)
        profile = get_user_profile(superadmin)
        self.assertEqual(profile.role, ROLE_SUPERADMIN)
        self.assertEqual(profile.approval_status, APPROVAL_APPROVED)

    def test_admin_signup_creates_pending_account(self):
        response = self.client.post(
            reverse("auth-admin-signup"),
            data={
                "name": "Pending Admin",
                "email": "pending-admin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "test-admin-code",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="pending-admin@example.com")
        self.assertEqual(get_user_profile(user).approval_status, APPROVAL_PENDING)

    def test_superadmin_can_approve_admin_then_admin_can_login(self):
        superadmin = self.create_superadmin()
        pending_admin = User.objects.create_user(
            username="pending-admin@example.com",
            email="pending-admin@example.com",
            password="StrongPass123",
            first_name="Pending Admin",
        )
        profile = set_user_role(
            pending_admin,
            ROLE_ADMIN,
            approval_status=APPROVAL_PENDING,
        )

        login_before = self.client.post(
            reverse("auth-admin-login"),
            data={"email": pending_admin.email, "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_before.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.defaults["HTTP_AUTHORIZATION"] = self.bearer(superadmin)
        response = self.client.post(
            reverse("superadmin-account-request-approve", kwargs={"pk": profile.pk}),
            data={},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("remarks", response.json()["data"])
        self.assertNotIn("rejection_reason", response.json()["data"])
        profile.refresh_from_db()
        pending_admin.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_APPROVED)
        self.assertFalse(pending_admin.is_staff)
        self.assertFalse(pending_admin.is_superuser)

        self.client.defaults.pop("HTTP_AUTHORIZATION")
        login_after = self.client.post(
            reverse("auth-admin-login"),
            data={"email": pending_admin.email, "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_after.status_code, status.HTTP_200_OK)

    def test_superadmin_can_reject_admin(self):
        superadmin = self.create_superadmin()
        pending_admin = User.objects.create_user(
            username="reject-admin@example.com",
            email="reject-admin@example.com",
            password="StrongPass123",
            first_name="Reject Admin",
        )
        profile = set_user_role(
            pending_admin,
            ROLE_ADMIN,
            approval_status=APPROVAL_PENDING,
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = self.bearer(superadmin)

        response = self.client.post(
            reverse("superadmin-account-request-reject", kwargs={"pk": profile.pk}),
            data={"remarks": "No approval."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["message"],
            "Account rejected successfully.",
        )
        profile.refresh_from_db()
        pending_admin.refresh_from_db()
        self.assertTrue(User.objects.filter(pk=pending_admin.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=profile.pk).exists())
        self.assertEqual(profile.approval_status, APPROVAL_REJECTED)
        self.assertEqual(profile.rejection_reason, "No approval.")
        self.assertFalse(pending_admin.is_active)

        login_after_reject = self.client.post(
            reverse("auth-admin-login"),
            data={"email": "reject-admin@example.com", "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_after_reject.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("account is rejected", login_after_reject.json()["message"].lower())

        signup_again = self.client.post(
            reverse("auth-admin-signup"),
            data={
                "name": "Reject Admin",
                "email": "reject-admin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "test-admin-code",
            },
            content_type="application/json",
        )
        self.assertEqual(signup_again.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", signup_again.json()["errors"])

    def test_admin_can_approve_and_reject_requesters_only(self):
        admin = self.create_approved_admin()
        requester = self.create_pending_requester()
        requester_profile = get_user_profile(requester)
        other_admin = User.objects.create_user(
            username="other-admin@example.com",
            email="other-admin@example.com",
            password="StrongPass123",
            first_name="Other Admin",
        )
        other_admin_profile = set_user_role(
            other_admin,
            ROLE_ADMIN,
            approval_status=APPROVAL_PENDING,
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = self.bearer(admin)

        approve_response = self.client.post(
            reverse("admin-requester-account-approve", kwargs={"pk": requester_profile.pk}),
            data={},
            content_type="application/json",
        )
        admin_response = self.client.post(
            reverse("admin-requester-account-approve", kwargs={"pk": other_admin_profile.pk}),
            data={},
            content_type="application/json",
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertIn("remarks", approve_response.json()["data"])
        self.assertNotIn("rejection_reason", approve_response.json()["data"])
        requester_profile.refresh_from_db()
        self.assertEqual(requester_profile.approval_status, APPROVAL_APPROVED)
        self.assertEqual(admin_response.status_code, status.HTTP_404_NOT_FOUND)

        rejected = self.create_pending_requester(email="reject-requester@example.com")
        rejected_profile = get_user_profile(rejected)
        reject_response = self.client.post(
            reverse("admin-requester-account-reject", kwargs={"pk": rejected_profile.pk}),
            data={"remarks": "Incomplete details."},
            content_type="application/json",
        )
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        rejected_profile.refresh_from_db()
        rejected.refresh_from_db()
        self.assertTrue(User.objects.filter(pk=rejected.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=rejected_profile.pk).exists())
        self.assertEqual(rejected_profile.approval_status, APPROVAL_REJECTED)
        self.assertEqual(rejected_profile.rejection_reason, "Incomplete details.")
        self.assertFalse(rejected.is_active)

        login_after_reject = self.client.post(
            reverse("auth-requester-login"),
            data={"email": "reject-requester@example.com", "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_after_reject.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("account is rejected", login_after_reject.json()["message"].lower())

        signup_again = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "Requester User",
                "email": "reject-requester@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )
        self.assertEqual(signup_again.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", signup_again.json()["errors"])

    def test_reject_approved_accounts_marks_rejected_and_deactivates(self):
        superadmin = self.create_superadmin()
        approved_admin = User.objects.create_user(
            username="approved-admin@example.com",
            email="approved-admin@example.com",
            password="StrongPass123",
            first_name="Approved Admin",
        )
        approved_admin_profile = set_user_role(
            approved_admin,
            ROLE_ADMIN,
            approval_status=APPROVAL_APPROVED,
        )
        approved_requester = User.objects.create_user(
            username="approved-requester@example.com",
            email="approved-requester@example.com",
            password="StrongPass123",
            first_name="Approved Requester",
        )
        approved_requester_profile = set_user_role(
            approved_requester,
            ROLE_REQUESTER,
            approval_status=APPROVAL_APPROVED,
        )

        self.client.defaults["HTTP_AUTHORIZATION"] = self.bearer(superadmin)
        admin_response = self.client.post(
            reverse("superadmin-account-request-reject", kwargs={"pk": approved_admin_profile.pk}),
            data={"remarks": "Do not reject approved."},
            content_type="application/json",
        )
        requester_response = self.client.post(
            reverse("admin-requester-account-reject", kwargs={"pk": approved_requester_profile.pk}),
            data={"remarks": "Do not reject approved."},
            content_type="application/json",
        )

        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(requester_response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(pk=approved_admin.pk).exists())
        self.assertTrue(User.objects.filter(pk=approved_requester.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=approved_admin_profile.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=approved_requester_profile.pk).exists())
        approved_admin_profile.refresh_from_db()
        approved_requester_profile.refresh_from_db()
        approved_admin.refresh_from_db()
        approved_requester.refresh_from_db()
        self.assertEqual(approved_admin_profile.approval_status, APPROVAL_REJECTED)
        self.assertEqual(approved_requester_profile.approval_status, APPROVAL_REJECTED)
        self.assertFalse(approved_admin.is_active)
        self.assertFalse(approved_requester.is_active)

    def test_superadmin_reject_is_not_allowed_for_superadmin_account(self):
        superadmin = self.create_superadmin()
        target_superadmin = User.objects.create_superuser(
            username="target-super@example.com",
            email="target-super@example.com",
            password="StrongPass123",
        )
        target_profile = get_user_profile(target_superadmin)

        self.client.defaults["HTTP_AUTHORIZATION"] = self.bearer(superadmin)
        response = self.client.post(
            reverse("superadmin-account-request-reject", kwargs={"pk": target_profile.pk}),
            data={"remarks": "Never delete superadmin."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(User.objects.filter(pk=target_superadmin.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=target_profile.pk).exists())

    def test_account_lists_include_rejected_accounts(self):
        admin = self.create_approved_admin()
        rejected_requester = self.create_pending_requester(email="legacy-rejected@example.com")
        requester_profile = get_user_profile(rejected_requester)
        requester_profile.approval_status = APPROVAL_REJECTED
        requester_profile.save(update_fields=["approval_status"])
        approved_requester = self.create_pending_requester(email="visible-requester@example.com")
        approved_requester_profile = get_user_profile(approved_requester)
        approved_requester_profile.approval_status = APPROVAL_APPROVED
        approved_requester_profile.save(update_fields=["approval_status"])

        self.client.defaults["HTTP_AUTHORIZATION"] = self.bearer(admin)
        response = self.client.get(reverse("admin-requester-account-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["data"])
        self.assertIn("remarks", response.json()["data"][0])
        self.assertNotIn("rejection_reason", response.json()["data"][0])
        emails = [item["email"] for item in response.json()["data"]]
        self.assertIn("visible-requester@example.com", emails)
        self.assertIn("legacy-rejected@example.com", emails)

    def test_requester_signup_creates_pending_account(self):
        response = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "Pending Requester",
                "email": "pending-requester@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        requester = User.objects.get(email="pending-requester@example.com")
        self.assertEqual(get_user_profile(requester).approval_status, APPROVAL_PENDING)

    def test_requester_cannot_approve_accounts_and_pending_cannot_access_protected_api(self):
        requester = self.create_pending_requester()
        self.client.defaults["HTTP_AUTHORIZATION"] = self.bearer(requester)

        approval_response = self.client.get(reverse("admin-requester-account-list"))
        protected_response = self.client.get(reverse("requester-availability"))

        self.assertEqual(approval_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(protected_response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(ADMIN_SIGNUP_CODE="test-admin-code")
class AccountApprovalAdminUxTests(TestCase):
    def create_superadmin(self):
        user = User.objects.create_superuser(
            username="superadmin@example.com",
            email="superadmin@example.com",
            password="StrongPass123",
            first_name="Super Admin",
        )
        get_user_profile(user)
        return user

    def create_user_with_profile(self, email, role, approval_status=APPROVAL_PENDING):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="StrongPass123",
            first_name=email.split("@")[0],
        )
        profile = set_user_role(
            user,
            role,
            approval_status=approval_status,
            designation="Tester",
            department="CSE",
            mobile="9999999999",
        )
        return user, profile

    def login_superadmin(self):
        superadmin = self.create_superadmin()
        self.client.force_login(superadmin)
        return superadmin

    def test_admin_account_list_shows_all_admin_statuses_with_friendly_row_links(self):
        self.login_superadmin()
        _, pending_profile = self.create_user_with_profile("pending-admin@example.com", ROLE_ADMIN)
        _, approved_profile = self.create_user_with_profile(
            "approved-admin@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_APPROVED,
        )
        _, rejected_profile = self.create_user_with_profile(
            "rejected-admin@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_REJECTED,
        )
        self.create_user_with_profile("pending-requester@example.com", ROLE_REQUESTER)

        response = self.client.get(reverse("admin:accounts_admin_approvals"))

        self.assertEqual(response.status_code, 200)
        for header in ["ID", "User", "Role", "Approval Status", "Approval"]:
            self.assertContains(response, f"<th>{header}</th>", html=True)
        for removed_header in [
            "<th>Email</th>",
            "<th>Approved By</th>",
            "<th>Approved At</th>",
            "<th>Department</th>",
            "<th>Designation</th>",
            "<th>Mobile</th>",
        ]:
            self.assertNotContains(response, removed_header, html=True)
        for user_display in [
            "pending-admin",
            "approved-admin",
            "rejected-admin",
        ]:
            self.assertContains(response, user_display)
        self.assertNotContains(response, "pending-requester")
        for profile in [pending_profile, approved_profile, rejected_profile]:
            self.assertContains(
                response,
                f'data-href="{reverse("admin:accounts_admin_approval_detail", kwargs={"profile_id": profile.pk})}"',
            )
            self.assertContains(response, "Open admin account")
            self.assertNotContains(
                response,
                reverse("admin:accounts_userprofile_change", args=[profile.pk]),
            )

    def test_admin_account_list_filters_by_status(self):
        self.login_superadmin()
        self.create_user_with_profile("pending-admin@example.com", ROLE_ADMIN)
        self.create_user_with_profile(
            "approved-admin@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_APPROVED,
        )

        response = self.client.get(
            reverse("admin:accounts_admin_approvals"),
            {"status": APPROVAL_APPROVED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "approved-admin")
        self.assertNotContains(response, "pending-admin")

    def test_requester_account_list_shows_all_requester_statuses_with_friendly_row_links(self):
        self.login_superadmin()
        _, pending_profile = self.create_user_with_profile("pending-requester@example.com", ROLE_REQUESTER)
        _, approved_profile = self.create_user_with_profile(
            "approved-requester@example.com",
            ROLE_REQUESTER,
            approval_status=APPROVAL_APPROVED,
        )
        _, rejected_profile = self.create_user_with_profile(
            "rejected-requester@example.com",
            ROLE_REQUESTER,
            approval_status=APPROVAL_REJECTED,
        )
        self.create_user_with_profile("pending-admin@example.com", ROLE_ADMIN)

        response = self.client.get(reverse("admin:accounts_requester_approvals"))

        self.assertEqual(response.status_code, 200)
        for header in ["ID", "User", "Role", "Approval Status", "Approval"]:
            self.assertContains(response, f"<th>{header}</th>", html=True)
        for removed_header in [
            "<th>Email</th>",
            "<th>Approved By</th>",
            "<th>Approved At</th>",
            "<th>Department</th>",
            "<th>Designation</th>",
            "<th>Mobile</th>",
        ]:
            self.assertNotContains(response, removed_header, html=True)
        for user_display in [
            "pending-requester",
            "approved-requester",
            "rejected-requester",
        ]:
            self.assertContains(response, user_display)
        self.assertNotContains(response, "pending-admin")
        for profile in [pending_profile, approved_profile, rejected_profile]:
            self.assertContains(
                response,
                f'data-href="{reverse("admin:accounts_requester_approval_detail", kwargs={"profile_id": profile.pk})}"',
            )
            self.assertContains(response, "Open requester account")
            self.assertNotContains(
                response,
                reverse("admin:accounts_userprofile_change", args=[profile.pk]),
            )

    def test_pending_detail_shows_approve_reject_only_without_raw_save_buttons(self):
        self.login_superadmin()
        _, profile = self.create_user_with_profile("pending-admin@example.com", ROLE_ADMIN)

        response = self.client.get(
            reverse("admin:accounts_admin_approval_detail", kwargs={"profile_id": profile.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account Details")
        self.assertContains(response, "Approve")
        self.assertContains(response, "Reject")
        self.assertContains(response, "Remarks, optional")
        self.assertNotContains(response, "Rejection reason")
        self.assertNotContains(response, "Block Access")
        self.assertNotContains(response, "Delete Account")
        self.assertNotContains(response, 'name="user"')
        self.assertNotContains(response, 'name="approved_by"')
        self.assertNotContains(response, 'name="_save"')
        self.assertNotContains(response, "Save and add another")
        self.assertNotContains(response, "Save and continue editing")

    def test_approved_detail_shows_reject_action(self):
        self.login_superadmin()
        _, profile = self.create_user_with_profile(
            "approved-admin@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_APPROVED,
        )

        response = self.client.get(
            reverse("admin:accounts_admin_approval_detail", kwargs={"profile_id": profile.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approved")
        self.assertContains(response, "Reject")
        self.assertContains(response, "Remarks, optional")
        self.assertNotContains(response, "Block Access")
        self.assertNotContains(response, "Delete Account")
        self.assertNotContains(response, "Approve</button>")

    def test_rejected_detail_shows_approve_again_and_delete_only(self):
        self.login_superadmin()
        _, profile = self.create_user_with_profile(
            "rejected-admin@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_REJECTED,
        )
        profile.rejection_reason = "Incomplete request."
        profile.save(update_fields=["rejection_reason"])

        response = self.client.get(
            reverse("admin:accounts_admin_approval_detail", kwargs={"profile_id": profile.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rejected")
        self.assertContains(response, "Incomplete request.")
        self.assertContains(response, "Remarks")
        self.assertNotContains(response, "Rejection Reason")
        self.assertContains(response, "Approve Again")
        self.assertNotContains(response, "Delete Account")
        self.assertNotContains(response, "Reject</button>")

    def test_superadmin_can_approve_pending_admin_from_admin_page(self):
        superadmin = self.login_superadmin()
        admin_user, profile = self.create_user_with_profile("pending-admin@example.com", ROLE_ADMIN)

        response = self.client.post(
            reverse("admin:accounts_admin_approval_detail", kwargs={"profile_id": profile.pk}),
            data={"action": "accept"},
        )

        self.assertRedirects(response, reverse("admin:accounts_admin_approvals"))
        profile.refresh_from_db()
        admin_user.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_APPROVED)
        self.assertEqual(profile.approved_by, superadmin)
        self.assertIsNotNone(profile.approved_at)
        self.assertEqual(profile.rejection_reason, "")
        self.assertTrue(admin_user.is_active)
        self.assertFalse(admin_user.is_staff)
        self.assertFalse(admin_user.is_superuser)

    def test_superadmin_can_reject_pending_admin_from_admin_page(self):
        self.login_superadmin()
        admin_user, profile = self.create_user_with_profile("reject-admin@example.com", ROLE_ADMIN)
        user_id = admin_user.id
        profile_id = profile.id

        response = self.client.post(
            reverse("admin:accounts_admin_approval_detail", kwargs={"profile_id": profile.pk}),
            data={"action": "reject", "remarks": "Invite no longer valid."},
        )

        self.assertRedirects(response, reverse("admin:accounts_admin_approvals"))
        self.assertTrue(User.objects.filter(pk=user_id).exists())
        self.assertTrue(UserProfile.objects.filter(pk=profile_id).exists())
        profile.refresh_from_db()
        admin_user.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_REJECTED)
        self.assertEqual(profile.rejection_reason, "Invite no longer valid.")
        self.assertFalse(admin_user.is_active)

    def test_superadmin_can_approve_again_from_rejected_state(self):
        superadmin = self.login_superadmin()
        admin_user, profile = self.create_user_with_profile(
            "rejected-admin@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_REJECTED,
        )
        admin_user.is_active = False
        admin_user.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("admin:accounts_admin_approval_detail", kwargs={"profile_id": profile.pk}),
            data={"action": "accept"},
        )

        self.assertRedirects(response, reverse("admin:accounts_admin_approvals"))
        profile.refresh_from_db()
        admin_user.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_APPROVED)
        self.assertEqual(profile.approved_by, superadmin)
        self.assertTrue(admin_user.is_active)

    def test_superadmin_can_reject_approved_admin_and_login_is_rejected(self):
        superadmin = self.login_superadmin()
        admin_user, profile = self.create_user_with_profile(
            "approved-admin@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_APPROVED,
        )

        response = self.client.post(
            reverse("admin:accounts_admin_approval_detail", kwargs={"profile_id": profile.pk}),
            data={"action": "reject", "remarks": "Access revoked."},
        )

        self.assertRedirects(response, reverse("admin:accounts_admin_approvals"))
        profile.refresh_from_db()
        admin_user.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_REJECTED)
        self.assertEqual(profile.approved_by, superadmin)
        self.assertEqual(profile.rejection_reason, "Access revoked.")
        self.assertFalse(admin_user.is_active)

        self.client.logout()
        login_response = self.client.post(
            reverse("auth-admin-login"),
            data={"email": admin_user.email, "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("account is rejected", login_response.json()["message"].lower())

    def test_superadmin_can_approve_and_reject_requesters_from_admin_pages(self):
        superadmin = self.login_superadmin()
        requester_user, requester_profile = self.create_user_with_profile(
            "pending-requester@example.com",
            ROLE_REQUESTER,
        )
        rejected_user, rejected_profile = self.create_user_with_profile(
            "reject-requester@example.com",
            ROLE_REQUESTER,
        )
        approve_response = self.client.post(
            reverse("admin:accounts_requester_approval_detail", kwargs={"profile_id": requester_profile.pk}),
            data={"action": "accept"},
        )
        reject_response = self.client.post(
            reverse("admin:accounts_requester_approval_detail", kwargs={"profile_id": rejected_profile.pk}),
            data={"action": "reject", "remarks": ""},
        )

        self.assertRedirects(approve_response, reverse("admin:accounts_requester_approvals"))
        self.assertRedirects(reject_response, reverse("admin:accounts_requester_approvals"))
        requester_profile.refresh_from_db()
        rejected_profile.refresh_from_db()
        rejected_user.refresh_from_db()
        self.assertEqual(requester_profile.approval_status, APPROVAL_APPROVED)
        self.assertEqual(requester_profile.approved_by, superadmin)
        self.assertEqual(rejected_profile.approval_status, APPROVAL_REJECTED)
        self.assertFalse(rejected_user.is_active)

    def test_approval_pages_reject_non_superadmin_users(self):
        self.create_superadmin()
        admin_user, _ = self.create_user_with_profile(
            "admin@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_APPROVED,
        )
        requester_user, _ = self.create_user_with_profile(
            "requester@example.com",
            ROLE_REQUESTER,
            approval_status=APPROVAL_APPROVED,
        )

        self.client.force_login(admin_user)
        admin_response = self.client.get(reverse("admin:accounts_admin_approvals"))
        requester_list_response = self.client.get(reverse("admin:accounts_requester_approvals"))
        self.assertNotEqual(admin_response.status_code, 200)
        self.assertNotEqual(requester_list_response.status_code, 200)

        self.client.force_login(requester_user)
        requester_response = self.client.get(reverse("admin:accounts_requester_approvals"))
        self.assertNotEqual(requester_response.status_code, 200)

    def test_userprofile_admin_uses_default_changelist_action_ui(self):
        superadmin = self.login_superadmin()
        _, profile = self.create_user_with_profile("requester@example.com", ROLE_REQUESTER)
        superadmin_profile = get_user_profile(superadmin)
        model_admin = django_admin.site._registry[UserProfile]

        response = self.client.get(reverse("admin:accounts_userprofile_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(model_admin.change_list_template)
        self.assertEqual(model_admin.list_display, (
            "id",
            "user",
            "role",
            "approval_status",
            "created_at",
            "updated_at",
        ))
        self.assertContains(response, 'name="action"')
        self.assertContains(response, 'class="action-select"')
        self.assertContains(response, f'name="_selected_action" value="{profile.pk}"')
        self.assertNotContains(response, f'name="_selected_action" value="{superadmin_profile.pk}"')
        self.assertNotContains(response, "superadmin@example.com")
        self.assertContains(response, "Delete selected user profiles")
        self.assertNotContains(response, "Delete selected accounts")
        self.assertNotContains(response, "Open requester account")

    def test_userprofile_single_delete_deletes_linked_requester_user_and_allows_signup_again(self):
        self.login_superadmin()
        user, profile = self.create_user_with_profile("single-delete-requester@example.com", ROLE_REQUESTER)
        user_id = user.pk
        profile_id = profile.pk

        confirmation = self.client.get(reverse("admin:accounts_userprofile_delete", args=[profile.pk]))

        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Are you sure")
        self.assertTrue(UserProfile.objects.filter(pk=profile_id).exists())
        self.assertTrue(User.objects.filter(pk=user_id).exists())

        delete_response = self.client.post(
            reverse("admin:accounts_userprofile_delete", args=[profile.pk]),
            data={"post": "yes"},
            follow=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(UserProfile.objects.filter(pk=profile_id).exists())
        self.assertFalse(User.objects.filter(pk=user_id).exists())

        signup_again = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "Single Delete Requester",
                "email": "single-delete-requester@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )
        self.assertEqual(signup_again.status_code, status.HTTP_201_CREATED)

    def test_userprofile_default_delete_selected_deletes_linked_users(self):
        self.login_superadmin()
        requester_user, requester_profile = self.create_user_with_profile("bulk-requester@example.com", ROLE_REQUESTER)
        admin_user, admin_profile = self.create_user_with_profile("bulk-admin@example.com", ROLE_ADMIN)
        requester_user_id = requester_user.pk
        admin_user_id = admin_user.pk
        requester_profile_id = requester_profile.pk
        admin_profile_id = admin_profile.pk

        confirmation = self.client.post(
            reverse("admin:accounts_userprofile_changelist"),
            data={
                "action": "delete_selected",
                "_selected_action": [requester_profile.pk, admin_profile.pk],
                "index": "0",
            },
        )

        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Are you sure")
        self.assertContains(confirmation, "User profiles: 2")
        self.assertContains(confirmation, "User profile:")
        self.assertContains(confirmation, f'name="_selected_action" value="{requester_profile.pk}"')
        self.assertContains(confirmation, f'name="_selected_action" value="{admin_profile.pk}"')
        self.assertTrue(UserProfile.objects.filter(pk=requester_profile_id).exists())
        self.assertTrue(UserProfile.objects.filter(pk=admin_profile_id).exists())

        delete_response = self.client.post(
            reverse("admin:accounts_userprofile_changelist"),
            data={
                "action": "delete_selected",
                "_selected_action": [requester_profile_id, admin_profile_id],
                "post": "yes",
            },
            follow=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(UserProfile.objects.filter(pk=requester_profile_id).exists())
        self.assertFalse(UserProfile.objects.filter(pk=admin_profile_id).exists())
        self.assertFalse(User.objects.filter(pk=requester_user_id).exists())
        self.assertFalse(User.objects.filter(pk=admin_user_id).exists())

        requester_signup_again = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "Bulk Requester",
                "email": "bulk-requester@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
            },
            content_type="application/json",
        )
        admin_signup_again = self.client.post(
            reverse("auth-admin-signup"),
            data={
                "name": "Bulk Admin",
                "email": "bulk-admin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "test-admin-code",
            },
            content_type="application/json",
        )
        self.assertEqual(requester_signup_again.status_code, status.HTTP_201_CREATED)
        self.assertEqual(admin_signup_again.status_code, status.HTTP_201_CREATED)

    def test_userprofile_delete_selected_skips_superadmin_and_current_user(self):
        superadmin = self.login_superadmin()
        superadmin_profile = get_user_profile(superadmin)
        user_id = superadmin.pk
        profile_id = superadmin_profile.pk

        changelist = self.client.get(reverse("admin:accounts_userprofile_changelist"))
        self.assertEqual(changelist.status_code, 200)
        self.assertNotContains(changelist, f'name="_selected_action" value="{profile_id}"')
        self.assertNotContains(changelist, "superadmin@example.com")

        delete_response = self.client.post(
            reverse("admin:accounts_userprofile_changelist"),
            data={
                "action": "delete_selected",
                "_selected_action": [profile_id],
                "post": "yes",
            },
            follow=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=user_id).exists())
        self.assertTrue(UserProfile.objects.filter(pk=profile_id).exists())

        direct_delete_response = self.client.get(
            reverse("admin:accounts_userprofile_delete", args=[profile_id])
        )
        self.assertNotEqual(direct_delete_response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=user_id).exists())
        self.assertTrue(UserProfile.objects.filter(pk=profile_id).exists())

    def test_userprofile_change_form_uses_default_django_save_buttons(self):
        self.login_superadmin()
        _, profile = self.create_user_with_profile("requester@example.com", ROLE_REQUESTER)

        response = self.client.get(reverse("admin:accounts_userprofile_change", args=[profile.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Remarks")
        self.assertContains(response, "Approved by")
        self.assertContains(response, "requester@example.com")
        self.assertNotContains(response, 'name="user"')
        self.assertNotContains(response, 'name="approved_by"')
        self.assertNotContains(response, ">Rejection reason<")
        self.assertContains(response, 'name="_save"')
        self.assertContains(response, "Save and add another")
        self.assertContains(response, "Save and continue editing")

    def test_userprofile_admin_auto_sets_approved_by_when_approved(self):
        superadmin = self.login_superadmin()
        manual_approver = User.objects.create_superuser(
            username="manual-approver@example.com",
            email="manual-approver@example.com",
            password="StrongPass123",
        )
        _, profile = self.create_user_with_profile("approve-raw@example.com", ROLE_ADMIN)

        response = self.client.post(
            reverse("admin:accounts_userprofile_change", args=[profile.pk]),
            data={
                "role": ROLE_ADMIN,
                "approval_status": APPROVAL_APPROVED,
                "approved_by": manual_approver.pk,
                "rejection_reason": "",
                "designation": "Tester",
                "department": "CSE",
                "mobile": "9999999999",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_APPROVED)
        self.assertEqual(profile.approved_by, superadmin)
        self.assertIsNotNone(profile.approved_at)

    def test_userprofile_admin_cannot_move_approved_account_back_to_pending(self):
        superadmin = self.login_superadmin()
        user, profile = self.create_user_with_profile(
            "approved-no-pending@example.com",
            ROLE_ADMIN,
            approval_status=APPROVAL_APPROVED,
        )
        profile.approved_by = superadmin
        profile.approved_at = timezone.now()
        profile.save(update_fields=["approved_by", "approved_at"])
        user.is_active = True
        user.save(update_fields=["is_active"])

        form_response = self.client.get(reverse("admin:accounts_userprofile_change", args=[profile.pk]))
        self.assertEqual(form_response.status_code, 200)
        self.assertNotContains(
            form_response,
            '<option value="pending">Pending</option>',
            html=True,
        )

        response = self.client.post(
            reverse("admin:accounts_userprofile_change", args=[profile.pk]),
            data={
                "role": ROLE_ADMIN,
                "approval_status": APPROVAL_PENDING,
                "rejection_reason": "",
                "designation": "Tester",
                "department": "CSE",
                "mobile": "9999999999",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_APPROVED)
        self.assertEqual(profile.approved_by, superadmin)
        self.assertIsNotNone(profile.approved_at)
        self.assertTrue(user.is_active)
        self.assertContains(response, "Select a valid choice. pending is not one of the available choices.")

        login_response = self.client.post(
            reverse("auth-admin-login"),
            data={"email": "approved-no-pending@example.com", "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_userprofile_admin_cannot_move_rejected_account_back_to_pending(self):
        self.login_superadmin()
        user, profile = self.create_user_with_profile(
            "rejected-no-pending@example.com",
            ROLE_REQUESTER,
            approval_status=APPROVAL_REJECTED,
        )
        profile.rejection_reason = "Not eligible."
        profile.save(update_fields=["rejection_reason"])
        user.is_active = False
        user.save(update_fields=["is_active"])

        form_response = self.client.get(reverse("admin:accounts_userprofile_change", args=[profile.pk]))
        self.assertEqual(form_response.status_code, 200)
        self.assertNotContains(
            form_response,
            '<option value="pending">Pending</option>',
            html=True,
        )

        response = self.client.post(
            reverse("admin:accounts_userprofile_change", args=[profile.pk]),
            data={
                "role": ROLE_REQUESTER,
                "approval_status": APPROVAL_PENDING,
                "rejection_reason": "",
                "designation": "Tester",
                "department": "CSE",
                "mobile": "9999999999",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_REJECTED)
        self.assertEqual(profile.rejection_reason, "Not eligible.")
        self.assertFalse(user.is_active)
        self.assertContains(response, "Select a valid choice. pending is not one of the available choices.")

    def test_userprofile_admin_rejects_and_deactivates_account(self):
        self.login_superadmin()
        manual_approver = User.objects.create_superuser(
            username="manual-rejecter@example.com",
            email="manual-rejecter@example.com",
            password="StrongPass123",
        )
        user, profile = self.create_user_with_profile("reject-raw@example.com", ROLE_REQUESTER)

        response = self.client.post(
            reverse("admin:accounts_userprofile_change", args=[profile.pk]),
            data={
                "role": ROLE_REQUESTER,
                "approval_status": APPROVAL_REJECTED,
                "approved_by": manual_approver.pk,
                "rejection_reason": "Not eligible.",
                "designation": "Tester",
                "department": "CSE",
                "mobile": "9999999999",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(profile.approval_status, APPROVAL_REJECTED)
        self.assertEqual(profile.approved_by.email, "superadmin@example.com")
        self.assertIsNotNone(profile.approved_at)
        self.assertEqual(profile.rejection_reason, "Not eligible.")
        self.assertFalse(user.is_active)
        self.assertContains(response, "Account rejected. The user can no longer login.")
