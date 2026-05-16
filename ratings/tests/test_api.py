"""Tests for ratings/api.py endpoints."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ratings.models import Rating
from recipes.models import Recipe


User = get_user_model()


class RatingGetAPITests(TestCase):
    """Tests for rating_get_api endpoint."""

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
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="My Recipe",
            description="Description",
            needs_review=False,
        )
        self.other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Bob's Recipe",
            needs_review=False,
        )

    def test_get_unauthenticated_returns_redirect(self):
        """Unauthenticated request redirects to login page."""
        url = reverse("ratings:rating_get", args=[self.recipe.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_get_returns_rating_when_exists(self):
        """Response includes rating data when user has rated the recipe."""
        Rating.objects.create(
            recipe=self.recipe,
            user=self.user,
            score=5,
            notes="Delicious!",
        )
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_get", args=[self.recipe.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["score"], 5)
        self.assertEqual(data["notes"], "Delicious!")

    def test_get_returns_null_when_no_rating(self):
        """Response returns {"rating": None} when no rating exists."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_get", args=[self.recipe.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("rating", data)
        self.assertIsNone(data["rating"])

    def test_get_other_household_recipe_returns_404(self):
        """Recipe from another household returns 404."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_get", args=[self.other_recipe.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class RatingCreateAPITests(TestCase):
    """Tests for rating_create_api endpoint."""

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
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="My Recipe",
            description="Description",
            needs_review=False,
        )
        self.other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Bob's Recipe",
            needs_review=False,
        )

    def test_create_unauthenticated_returns_redirect(self):
        """Unauthenticated POST redirects to login page."""
        url = reverse("ratings:rating_create", args=[self.recipe.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_create_new_rating(self):
        """POST creates a new rating and returns rating data."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_create", args=[self.recipe.pk])
        response = self.client.post(
            url,
            data={"score": 4, "notes": "Good recipe"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["score"], 4)
        self.assertEqual(data["notes"], "Good recipe")
        # Verify created in database
        rating = Rating.objects.get(recipe=self.recipe, user=self.user)
        self.assertEqual(rating.score, 4)

    def test_create_updates_existing_rating(self):
        """POST updates existing rating (upsert) instead of creating new."""
        Rating.objects.create(
            recipe=self.recipe,
            user=self.user,
            score=3,
            notes="Original notes",
        )
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_create", args=[self.recipe.pk])
        response = self.client.post(
            url,
            data={"score": 5, "notes": "Updated notes"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["score"], 5)
        self.assertEqual(data["notes"], "Updated notes")
        # Verify only one rating exists
        self.assertEqual(
            Rating.objects.filter(recipe=self.recipe, user=self.user).count(), 1
        )

    def test_create_invalid_score_zero_returns_400(self):
        """Score of 0 returns 400 error."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_create", args=[self.recipe.pk])
        response = self.client.post(
            url,
            data={"score": 0},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_create_invalid_score_six_returns_400(self):
        """Score of 6 returns 400 error."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_create", args=[self.recipe.pk])
        response = self.client.post(
            url,
            data={"score": 6},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_create_missing_score_returns_400(self):
        """Missing score returns 400 error."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_create", args=[self.recipe.pk])
        response = self.client.post(
            url,
            data={"notes": "No score"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_create_invalid_json_returns_400(self):
        """Invalid JSON body returns 400 error."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_create", args=[self.recipe.pk])
        response = self.client.post(
            url,
            data="not valid json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_create_other_household_recipe_returns_404(self):
        """Rating another household's recipe returns 404."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("ratings:rating_create", args=[self.other_recipe.pk])
        response = self.client.post(
            url,
            data={"score": 5},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)