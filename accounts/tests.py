from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from household.models import Household

from .backends import UsernameOrEmailBackend
from .forms import RegistrationForm


class LoginFlowTests(TestCase):
    def setUp(self):
        household = Household.objects.create(name="Test Household")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="StrongPass123!",
            household=household,
        )

    def test_login_with_username_redirects(self):
        response = self.client.post(
            reverse("login"),
            {"username": "testuser", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_login_with_email_redirects(self):
        response = self.client.post(
            reverse("login"),
            {"username": "test@example.com", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_invalid_login_shows_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": "test@example.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please enter a correct username and password.",
        )

    def test_login_with_uppercase_email_redirects(self):
        response = self.client.post(
            reverse("login"),
            {"username": "TEST@EXAMPLE.COM", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_login_with_uppercase_username_redirects(self):
        response = self.client.post(
            reverse("login"),
            {"username": "TESTUSER", "password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_login_missing_password_fails(self):
        response = self.client.post(
            reverse("login"),
            {"username": "testuser"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")

    def test_login_missing_username_fails(self):
        response = self.client.post(
            reverse("login"),
            {"password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_is_redirected_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 302)


class LogoutViewTests(TestCase):
    def setUp(self):
        household = Household.objects.create(name="Logout Household")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="logoutuser",
            email="logout@example.com",
            password="Pass1234!",
            household=household,
        )

    def test_logout_redirects_to_login(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/login/")

    def test_session_is_cleared_after_logout(self):
        self.client.force_login(self.user)
        self.client.post(reverse("logout"))
        # After logout the session is cleared — the client cannot access a
        # protected view without re-authenticating.
        response = self.client.get(reverse("recipes:recipe_list"))
        self.assertNotEqual(response.status_code, 200) or \
            self.assertIn("/accounts/login/", response.url)


class RegisterViewTests(TestCase):
    def test_register_page_renders(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "email")
        self.assertContains(response, "username")
        self.assertContains(response, "password1")
        self.assertContains(response, "password2")

    def test_register_creates_user_and_household(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "newuser@example.com",
                "username": "newuser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
                "household_name": "New User Home",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

        user_model = get_user_model()
        user = user_model.objects.get(username="newuser")
        self.assertEqual(user.email, "newuser@example.com")
        self.assertIsNotNone(user.household)
        self.assertEqual(user.household.name, "New User Home")

    def test_register_creates_default_household_when_name_not_provided(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "plainuser@example.com",
                "username": "plainuser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)

        user_model = get_user_model()
        user = user_model.objects.get(username="plainuser")
        self.assertIsNotNone(user.household)
        self.assertEqual(user.household.name, "My Household")

    def test_register_logs_user_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "autoLogin@example.com",
                "username": "autologin",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )
        # Should redirect to home and be logged in
        self.assertEqual(response.status_code, 302)
        user_model = get_user_model()
        self.assertTrue(
            self.client.session.session_key is not None
        )

    def test_register_password_mismatch_fails(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "mismatch@example.com",
                "username": "mismatch",
                "password1": "ComplexPass123!",
                "password2": "DifferentPass456!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "password")
        user_model = get_user_model()
        self.assertFalse(user_model.objects.filter(username="mismatch").exists())

    def test_register_duplicate_username_fails(self):
        Household.objects.create(name="Dup User Home")
        user_model = get_user_model()
        user_model.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="Pass1234!",
        )

        response = self.client.post(
            reverse("register"),
            {
                "email": "new@example.com",
                "username": "existinguser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "username")

    def test_register_duplicate_email_fails(self):
        # Email uniqueness is enforced at both the model level (unique=True)
        # and form level (clean_email). Registration with a duplicate email
        # should be rejected with a validation error.
        Household.objects.create(name="Dup Email Home 2")
        user_model = get_user_model()
        user_model.objects.create_user(
            username="firstuser",
            email="dupemail@example.com",
            password="Pass1234!",
        )

        response = self.client.post(
            reverse("register"),
            {
                "email": "dupemail@example.com",
                "username": "seconduser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("email", form.errors)
        self.assertEqual(form.errors["email"], ["A user with that email already exists."])
        self.assertFalse(user_model.objects.filter(username="seconduser").exists())


class RegistrationFormTests(TestCase):
    def test_form_valid_with_all_fields(self):
        form = RegistrationForm(
            data={
                "email": "formtest@example.com",
                "username": "formuser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
                "household_name": "Form Test Home",
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_valid_without_household_name(self):
        form = RegistrationForm(
            data={
                "email": "nohh@example.com",
                "username": "nohhuser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_save_creates_user_with_household(self):
        form = RegistrationForm(
            data={
                "email": "savetest@example.com",
                "username": "saveuser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
                "household_name": "Save Test Home",
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save()

        user_model = get_user_model()
        self.assertTrue(user_model.objects.filter(username="saveuser").exists())
        self.assertEqual(user.household.name, "Save Test Home")

    def test_form_save_creates_default_household(self):
        form = RegistrationForm(
            data={
                "email": "defaulthh@example.com",
                "username": "defaulthhuser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.household.name, "My Household")

    def test_form_requires_email(self):
        form = RegistrationForm(
            data={
                "username": "noemailuser",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class UsernameOrEmailBackendTests(TestCase):
    def setUp(self):
        self.backend = UsernameOrEmailBackend()
        self.household = Household.objects.create(name="Backend Household")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="backenduser",
            email="backend@example.com",
            password="BackendPass123!",
            household=self.household,
        )

    def test_authenticate_with_username(self):
        user = self.backend.authenticate(
            request=None, username="backenduser", password="BackendPass123!"
        )
        self.assertEqual(user, self.user)

    def test_authenticate_with_email(self):
        user = self.backend.authenticate(
            request=None, username="backend@example.com", password="BackendPass123!"
        )
        self.assertEqual(user, self.user)

    def test_authenticate_with_uppercase_email(self):
        user = self.backend.authenticate(
            request=None, username="BACKEND@EXAMPLE.COM", password="BackendPass123!"
        )
        self.assertEqual(user, self.user)

    def test_authenticate_with_uppercase_username(self):
        user = self.backend.authenticate(
            request=None, username="BACKENDUSER", password="BackendPass123!"
        )
        self.assertEqual(user, self.user)

    def test_authenticate_wrong_password_returns_none(self):
        user = self.backend.authenticate(
            request=None, username="backenduser", password="WrongPass!"
        )
        self.assertIsNone(user)

    def test_authenticate_unknown_username_returns_none(self):
        user = self.backend.authenticate(
            request=None, username="nonexistent", password="BackendPass123!"
        )
        self.assertIsNone(user)

    def test_authenticate_unknown_email_returns_none(self):
        user = self.backend.authenticate(
            request=None, username="nobody@example.com", password="BackendPass123!"
        )
        self.assertIsNone(user)

    def test_authenticate_no_credentials_returns_none(self):
        user = self.backend.authenticate(request=None, username=None, password=None)
        self.assertIsNone(user)

    def test_authenticate_empty_password_returns_none(self):
        user = self.backend.authenticate(request=None, username="backenduser", password="")
        self.assertIsNone(user)


class CustomUserModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Model Test Home")

    def test_custom_user_str_returns_email(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="struser",
            email="str@example.com",
            password="Pass1234!",
            household=self.household,
        )
        self.assertEqual(str(user), "str@example.com")

    def test_custom_user_str_returns_username_when_no_email(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="noemailuser",
            email="",
            password="Pass1234!",
            household=self.household,
        )
        self.assertEqual(str(user), "noemailuser")

    def test_custom_user_household_is_nullable(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="nohousehold",
            email="nohh@example.com",
            password="Pass1234!",
        )
        self.assertIsNone(user.household)
