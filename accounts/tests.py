from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from household.models import Household


class LoginFlowTests(TestCase):
    def setUp(self):
        household = Household.objects.create(name="Test Household")
        self.user = CustomUser.objects.create_user(
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
