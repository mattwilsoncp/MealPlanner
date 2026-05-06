from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from inventory.models import InventoryItem
from recipes.models import Recipe


class DiscoveryViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Discovery Home")
        self.user = get_user_model().objects.create_user(
            username="discoverer",
            email="discoverer@example.com",
            password="pass1234",
            household=self.household,
        )

    def _create_recipe(self, title, ingredient_names):
        recipe = Recipe.objects.create(
            household=self.household,
            title=title,
            needs_review=False,
        )
        for index, ingredient_name in enumerate(ingredient_names):
            ingredient = Ingredient.objects.create(
                household=self.household,
                name=ingredient_name,
            )
            IngredientLink.objects.create(
                recipe=recipe,
                ingredient=ingredient,
                quantity=Decimal("1.00"),
                unit="piece",
                order=index,
            )
        return recipe

    def test_discovery_view_requires_authentication(self):
        response = self.client.get(reverse("shopping:discovery"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_discovery_view_context_is_sorted_urgent_first_and_includes_template_keys(
        self,
    ):
        urgent_recipe = self._create_recipe("Urgent Soup", ["Milk", "Bread"])
        regular_recipe = self._create_recipe("Regular Pasta", ["Pasta", "Tomato Sauce"])

        InventoryItem.objects.create(
            household=self.household,
            name="Milk",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="fridge",
            expiration_date=date.today() + timedelta(days=1),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Pasta",
            quantity=Decimal("1.00"),
            unit="piece",
            category="pantry",
            location="pantry",
            expiration_date=date.today() + timedelta(days=30),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Tomato Sauce",
            quantity=Decimal("1.00"),
            unit="piece",
            category="pantry",
            location="pantry",
            expiration_date=date.today() + timedelta(days=30),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("shopping:discovery"))

        self.assertEqual(response.status_code, 200)
        matches = response.context["matches"]
        self.assertEqual(matches[0]["recipe"].id, urgent_recipe.id)
        self.assertEqual(matches[1]["recipe"].id, regular_recipe.id)

        for key in ["match_percentage", "missing_ingredients", "has_urgent_match"]:
            self.assertIn(key, matches[0])

        self.assertTrue(matches[0]["has_urgent_match"])
        self.assertFalse(matches[1]["has_urgent_match"])
        self.assertIn("Bread", matches[0]["missing_ingredients"])
