from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from recipes.models import Recipe


class ReviewQueueTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Primary")
        self.other_household = Household.objects.create(name="Other")
        self.user = user_model.objects.create_user(
            username="review-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def test_review_queue_is_household_scoped_and_only_needs_review(self):
        primary_needs_review = Recipe.objects.create(
            household=self.household,
            title="Primary Needs Review",
            needs_review=True,
        )
        Recipe.objects.create(
            household=self.household,
            title="Primary Ready",
            needs_review=False,
        )
        Recipe.objects.create(
            household=self.other_household,
            title="Other Needs Review",
            needs_review=True,
        )

        response = self.client.get(reverse("reviews:review_queue"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("needs_review", response.context)
        queued_recipes = list(response.context["needs_review"])
        self.assertEqual(queued_recipes, [primary_needs_review])
