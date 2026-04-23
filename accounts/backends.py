from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        login_value = username or kwargs.get(UserModel.USERNAME_FIELD)

        if not login_value or not password:
            return None

        try:
            if "@" in login_value:
                user = UserModel.objects.get(email__iexact=login_value)
            else:
                user = UserModel.objects.get(username__iexact=login_value)
        except UserModel.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
