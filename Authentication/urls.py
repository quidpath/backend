from django.urls import path

from Authentication.views.auth import (
    login_user,
    logout_user,
    delete_user,
    verify_otp
)
from Authentication.views.register import register_user
from Authentication.views.user import refresh_token, user_profile

urlpatterns = [
    path("login/", login_user, name="login"),
    path("register/", register_user, name="register"),
    path("profile/", user_profile, name="profile"),
    path("token/refresh/", refresh_token, name="token_refresh"),
    path("logout/", logout_user, name="logout"),
    path("delete-user/", delete_user, name="delete_user"),
    path("verify-otp/", verify_otp, name="verify_otp"),
]
