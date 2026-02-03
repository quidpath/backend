# authentication/services/user_service.py
from Authentication.models.user import CustomUser


def create_user(username, email, password):
    user = CustomUser(username=username, email=email)
    user.set_password(password)
    user.save()
    return user
