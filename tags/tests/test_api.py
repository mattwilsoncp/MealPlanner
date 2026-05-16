from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from tags.models import Tag


User = get_user_model()


class TagListAPITests(TestCase):
    """Tests for tag_list_api endpoint."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.other_household = Household.objects.create(name="Other Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.other_user = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="pass1234",
            household=self.other_household,
        )

    def test_list_api_unauthenticated_returns_redirect(self):
        """Unauthenticated request redirects to login page."""
        response = self.client.get(reverse("tags:tag_list_api"))
        self.assertEqual(response.status_code, 302)

    def test_list_api_returns_only_own_household_tags(self):
        """Only tags from user's household are returned."""
        Tag.objects.create(household=self.household, name="Dinner", color="#ff0000")
        Tag.objects.create(household=self.household, name="Lunch", color="#00ff00")
        Tag.objects.create(household=self.other_household, name="Breakfast", color="#0000ff")
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("tags:tag_list_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        tag_names = [t["name"] for t in data["tags"]]
        self.assertIn("Dinner", tag_names)
        self.assertIn("Lunch", tag_names)
        self.assertNotIn("Breakfast", tag_names)

    def test_list_api_returns_expected_fields(self):
        """Response includes id, name, color for each tag."""
        tag = Tag.objects.create(household=self.household, name="Dinner", color="#ff0000")
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("tags:tag_list_api"))
        self.assertEqual(response.status_code, 200)
        tag_data = response.json()["tags"][0]
        self.assertIn("id", tag_data)
        self.assertIn("name", tag_data)
        self.assertIn("color", tag_data)
        self.assertEqual(tag_data["name"], "Dinner")
        self.assertEqual(tag_data["color"], "#ff0000")

    def test_list_api_returns_tags_sorted_by_name(self):
        """Tags are returned sorted alphabetically by name."""
        Tag.objects.create(household=self.household, name="Zebra")
        Tag.objects.create(household=self.household, name="Apple")
        Tag.objects.create(household=self.household, name="Mango")
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("tags:tag_list_api"))
        self.assertEqual(response.status_code, 200)
        tag_names = [t["name"] for t in response.json()["tags"]]
        self.assertEqual(tag_names, ["Apple", "Mango", "Zebra"])

    def test_list_api_empty_for_new_household(self):
        """New household with no tags returns empty list."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("tags:tag_list_api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tags"], [])


class TagCreateAPITests(TestCase):
    """Tests for tag_create_api endpoint."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.other_household = Household.objects.create(name="Other Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.other_user = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="pass1234",
            household=self.other_household,
        )

    def test_create_api_unauthenticated_returns_redirect(self):
        """Unauthenticated POST redirects to login page."""
        response = self.client.post(reverse("tags:tag_create_api"))
        self.assertEqual(response.status_code, 302)

    def test_create_api_get_method_not_allowed(self):
        """GET request to create endpoint returns 405."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("tags:tag_create_api"))
        self.assertEqual(response.status_code, 405)

    def test_create_api_success(self):
        """Valid POST creates a new tag."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("tags:tag_create_api"),
            data='{"name": "Dinner", "color": "#ff0000"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["created"])
        self.assertEqual(data["name"], "Dinner")
        self.assertEqual(data["color"], "#ff0000")
        self.assertIn("id", data)
        tag = Tag.objects.get(id=data["id"])
        self.assertEqual(tag.name, "Dinner")
        self.assertEqual(tag.color, "#ff0000")
        self.assertEqual(tag.household, self.household)

    def test_create_api_default_color(self):
        """Tag created without color uses default #6b7280."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("tags:tag_create_api"),
            data='{"name": "Lunch"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["color"], "#6b7280")
        tag = Tag.objects.get(id=data["id"])
        self.assertEqual(tag.color, "#6b7280")

    def test_create_api_missing_name_returns_400(self):
        """POST without name returns 400 error."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("tags:tag_create_api"),
            data='{"color": "#ff0000"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertEqual(response.json()["error"], "Name is required")

    def test_create_api_empty_name_returns_400(self):
        """POST with empty name returns 400 error."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("tags:tag_create_api"),
            data='{"name": "   ", "color": "#ff0000"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Name is required")

    def test_create_api_duplicate_name_returns_existing(self):
        """Creating tag with existing name returns existing tag."""
        existing = Tag.objects.create(
            household=self.household, name="Dinner", color="#ff0000"
        )
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("tags:tag_create_api"),
            data='{"name": "dinner", "color": "#00ff00"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["exists"])
        self.assertEqual(data["id"], existing.id)
        self.assertEqual(data["name"], "Dinner")
        self.assertEqual(data["color"], "#ff0000")
        # Ensure no duplicate was created
        self.assertEqual(Tag.objects.filter(household=self.household).count(), 1)

    def test_create_api_case_insensitive_duplicate_check(self):
        """Duplicate check is case-insensitive."""
        Tag.objects.create(household=self.household, name="Dinner", color="#ff0000")
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("tags:tag_create_api"),
            data='{"name": "DINNER", "color": "#00ff00"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["exists"])

    def test_create_api_invalid_json_returns_400(self):
        """Invalid JSON body returns 400 error."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("tags:tag_create_api"),
            data="not valid json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON")