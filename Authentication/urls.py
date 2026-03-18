from django.urls import path

from Authentication.views.auth import (delete_user, login_user, logout_user,
                                       verify_otp)
from Authentication.views.change_password import change_password
from Authentication.views.corpprofile import corporate_update_profile
from Authentication.views.ForgotPassword import (forgot_password,
                                                 reset_password,
                                                 verify_pass_otp)
from Authentication.views.login_profile import get_profile
from Authentication.views.microservice_api import (batch_get_corporates,
                                                   batch_get_users,
                                                   get_corporate_details,
                                                   get_user_details)
from Authentication.views.register import register_user
from Authentication.views.individual_registration import register_individual_user
from Authentication.views.email_activation import (
    register_individual_with_email_activation,
    activate_account,
    resend_activation_email,
)
from Authentication.views.logo_settings import (
    upload_corporate_logo,
    get_corporate_logo,
    delete_corporate_logo,
)
from Authentication.views.user import refresh_token
from Authentication.views.UserProfile import corporateuser_update_profile
from Authentication.views.notifications import (
    get_notifications,
    mark_notification_read,
    mark_all_notifications_read,
    get_unread_count,
)
from Authentication.views.activity import (
    get_recent_activity,
    get_activity_stats,
)
from Authentication.views.plans import (
    get_subscription_plans,
    initiate_subscription_payment,
    check_subscription_status,
)
from Authentication.views.health import health_check
from Authentication.views.menu import get_menu
from Authentication.views.settings import (
    get_system_settings,
    update_system_settings,
    check_user_permissions,
)

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("login/", login_user, name="login"),
    path("register/", register_user, name="register"),
    path("register-individual/", register_individual_user, name="register-individual"),
    path("register-individual-email/", register_individual_with_email_activation, name="register-individual-email"),
    path("activate-account/", activate_account, name="activate-account"),
    path("resend-activation/", resend_activation_email, name="resend-activation"),
    path("get_profile/", get_profile, name="profile"),
    path("menu/", get_menu, name="menu"),
    path("token/refresh/", refresh_token, name="token_refresh"),
    path("logout/", logout_user, name="logout"),
    path("delete-user/", delete_user, name="delete_user"),
    path("verify-otp/", verify_otp, name="verify_otp"),
    path("password-forgot/", forgot_password, name="username_check"),
    path("verify-pass-otp/", verify_pass_otp, name="verify_pass_otp"),
    path("reset-password/", reset_password, name="reset_password"),
    path("user-profile-update/", corporateuser_update_profile, name="user-profile"),
    path("corp-user-update/", corporate_update_profile, name="corp-profile"),
    path("change-password/", change_password, name="change_password"),
    # Logo settings endpoints
    path("logo/upload/", upload_corporate_logo, name="upload-logo"),
    path("logo/get/", get_corporate_logo, name="get-logo"),
    path("logo/delete/", delete_corporate_logo, name="delete-logo"),
    # Settings and permissions
    path("settings/", get_system_settings, name="get-settings"),
    path("settings/update/", update_system_settings, name="update-settings"),
    path("permissions/", check_user_permissions, name="check-permissions"),
    # Microservice API endpoints
    path("users/<uuid:user_id>/", get_user_details, name="microservice-user-details"),
    path(
        "corporates/<uuid:corporate_id>/",
        get_corporate_details,
        name="microservice-corporate-details",
    ),
    path("users/batch/", batch_get_users, name="microservice-batch-users"),
    path(
        "corporates/batch/",
        batch_get_corporates,
        name="microservice-batch-corporates",
    ),
    # Notification endpoints
    path("notifications/", get_notifications, name="get-notifications"),
    path(
        "notifications/<uuid:notification_id>/mark-read/",
        mark_notification_read,
        name="mark-notification-read",
    ),
    path(
        "notifications/mark-all-read/",
        mark_all_notifications_read,
        name="mark-all-notifications-read",
    ),
    path(
        "notifications/unread-count/",
        get_unread_count,
        name="get-unread-count",
    ),
    # Activity feed endpoints
    path("activity/recent/", get_recent_activity, name="get-recent-activity"),
    path("activity/stats/", get_activity_stats, name="get-activity-stats"),
    # Subscription plan endpoints
    path("plans/", get_subscription_plans, name="get-subscription-plans"),
    path("payments/initiate/", initiate_subscription_payment, name="initiate-subscription-payment"),
    path("subscription/status/", check_subscription_status, name="check-subscription-status"),
]
