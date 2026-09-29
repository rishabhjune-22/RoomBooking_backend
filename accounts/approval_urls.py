from django.urls import path

from .views import (
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
]
