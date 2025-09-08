from django.urls import path
from OrgAuth.views import corporate_registration, corporate_users
from OrgAuth.views.corporate_users import list_roles, get_corporate_user

urlpatterns = [
    # Corporate
    path("corporate/create", corporate_registration.create_corporate),
    path("corporate/list", corporate_registration.list_corporates),
    path("corporate/update", corporate_registration.update_corporate),
    path("corporate/delete", corporate_registration.delete_corporate),
    path("corporate/approve", corporate_registration.approve_corporate),
    path("corporate/suspend", corporate_registration.suspend_corporate),

    # Corporate Users (admin only)
    path("corporate-users/create", corporate_users.create_corporate_user),
    path("corporate-users/list", corporate_users.list_corporate_users),
    path("corporate-users/get", corporate_users.get_corporate_user),  # New endpoint
    path("corporate-users/update", corporate_users.update_corporate_user),
    path("corporate-users/delete", corporate_users.delete_corporate_user),
    path("corporate-users/suspend", corporate_users.suspend_corporate_user),
    path("corporate-users/unsuspend", corporate_users.unsuspend_corporate_user),

    path("roles/", list_roles, name="list_roles"),
]
