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
from Authentication.views.user import refresh_token
from Authentication.views.UserProfile import corporateuser_update_profile

urlpatterns = [
    path("login/", login_user, name="login"),
    path("register/", register_user, name="register"),
    path("get_profile/", get_profile, name="profile"),
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
]
