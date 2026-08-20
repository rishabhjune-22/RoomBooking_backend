from django.urls import path

from .views import (
    AdminRequesterAccountApproveView,
    AdminRequesterAccountDetailView,
    AdminRequesterAccountListView,
    AdminRequesterAccountRejectView,
    SuperadminAccountRequestApproveView,
    SuperadminAccountRequestDeleteView,
    SuperadminAccountRequestDetailView,
    SuperadminAccountRequestListView,
    SuperadminAccountRequestRejectView,
    WorkflowNotificationCountView,
)


urlpatterns = [
    path(
        "workflow-notification-counts/",
        WorkflowNotificationCountView.as_view(),
        name="workflow-notification-counts",
    ),
    path(
        "superadmin/account-requests/",
        SuperadminAccountRequestListView.as_view(),
        name="superadmin-account-request-list",
    ),
    path(
        "superadmin/account-requests/<int:pk>/",
        SuperadminAccountRequestDetailView.as_view(),
        name="superadmin-account-request-detail",
    ),
    path(
        "superadmin/account-requests/<int:pk>/approve/",
        SuperadminAccountRequestApproveView.as_view(),
        name="superadmin-account-request-approve",
    ),
    path(
        "superadmin/account-requests/<int:pk>/reject/",
        SuperadminAccountRequestRejectView.as_view(),
        name="superadmin-account-request-reject",
    ),
    path(
        "superadmin/account-requests/<int:pk>/delete/",
        SuperadminAccountRequestDeleteView.as_view(),
        name="superadmin-account-request-delete",
    ),
    path(
        "admin/requester-accounts/",
        AdminRequesterAccountListView.as_view(),
        name="admin-requester-account-list",
    ),
    path(
        "admin/requester-accounts/<int:pk>/",
        AdminRequesterAccountDetailView.as_view(),
        name="admin-requester-account-detail",
    ),
    path(
        "admin/requester-accounts/<int:pk>/approve/",
        AdminRequesterAccountApproveView.as_view(),
        name="admin-requester-account-approve",
    ),
    path(
        "admin/requester-accounts/<int:pk>/reject/",
        AdminRequesterAccountRejectView.as_view(),
        name="admin-requester-account-reject",
    ),
]
