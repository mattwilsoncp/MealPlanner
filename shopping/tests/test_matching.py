from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from inventory.models import InventoryItem
from recipes.models import Recipe
from shopping.services import build_discovery_matches


class DiscoveryMatchingServiceTests(TestCase):
    def setUp(self):
        self.as_of_date = date(2026, 4, 19)
        self.household = Household.objects.create(
            name="Matcher Home", expiring_threshold_days=3
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

    def test_build_discovery_matches_returns_missing_ingredients_and_urgency_flags(
        self,
    ):
        omelet = self._create_recipe("Omelet", ["Egg", "Milk", "Cheese"])
        smoothie = self._create_recipe("Smoothie", ["Banana", "Yogurt", "Honey", "Ice"])
        pantry = self._create_recipe(
            "Pantry Bowl", ["Rice", "Beans", "Onion", "Garlic"]
        )

        InventoryItem.objects.create(
            household=self.household,
            name="Egg",
            quantity=Decimal("2.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Milk",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
            expiration_date=self.as_of_date + timedelta(days=10),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Banana",
            quantity=Decimal("1.00"),
            unit="piece",
            category="produce",
            location="counter",
            expiration_date=self.as_of_date - timedelta(days=1),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Yogurt",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Rice",
            quantity=Decimal("1.00"),
            unit="piece",
            category="pantry",
            location="pantry",
        )

        matches = build_discovery_matches(self.household, as_of_date=self.as_of_date)
        by_title = {entry["recipe"].title: entry for entry in matches}

        omelet_match = by_title[omelet.title]
        smoothie_match = by_title[smoothie.title]
        pantry_match = by_title[pantry.title]

        for match in [omelet_match, smoothie_match, pantry_match]:
            self.assertIn("missing_ingredients", match)
            self.assertIn("urgent_items", match)
            self.assertIn("has_expired_match", match)
            self.assertIn("has_urgent_match", match)

        self.assertEqual(omelet_match["missing_ingredients"], ["Cheese"])
        self.assertEqual(smoothie_match["missing_ingredients"], ["Honey", "Ice"])
        self.assertEqual(
            pantry_match["missing_ingredients"], ["Beans", "Onion", "Garlic"]
        )

        self.assertEqual(smoothie_match["urgent_items"], ["Banana"])
        self.assertTrue(smoothie_match["has_expired_match"])
        self.assertTrue(smoothie_match["has_urgent_match"])

        self.assertFalse(omelet_match["has_expired_match"])
        self.assertFalse(omelet_match["has_urgent_match"])

    def test_build_discovery_matches_orders_urgent_first_then_match_percentage(self):
        self._create_recipe("Apple Pie", ["Apple", "Flour", "Butter"])
        self._create_recipe("Banana Toast", ["Banana", "Bread", "Honey", "Cinnamon"])
        self._create_recipe("Carrot Soup", ["Carrot", "Stock", "Cream", "Onion"])

        InventoryItem.objects.create(
            household=self.household,
            name="Apple",
            quantity=Decimal("1.00"),
            unit="piece",
            category="produce",
            location="counter",
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Flour",
            quantity=Decimal("1.00"),
            unit="piece",
            category="pantry",
            location="pantry",
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Banana",
            quantity=Decimal("1.00"),
            unit="piece",
            category="produce",
            location="counter",
            expiration_date=self.as_of_date + timedelta(days=1),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Bread",
            quantity=Decimal("1.00"),
            unit="piece",
            category="bakery",
            location="counter",
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Carrot",
            quantity=Decimal("1.00"),
            unit="piece",
            category="produce",
            location="refrigerator",
        )

        matches = build_discovery_matches(self.household, as_of_date=self.as_of_date)
        ordered_titles = [entry["recipe"].title for entry in matches]

        self.assertEqual(ordered_titles[0], "Banana Toast")
        self.assertEqual(ordered_titles[1:], ["Apple Pie", "Carrot Soup"])

    def test_build_discovery_matches_scopes_to_household(self):
        other_household = Household.objects.create(name="Other Home")
        self._create_recipe("My Recipe", ["Lime"])

        other_recipe = Recipe.objects.create(
            household=other_household,
            title="Other Household Recipe",
            needs_review=False,
        )
        other_ingredient = Ingredient.objects.create(
            household=other_household, name="Salt"
        )
        IngredientLink.objects.create(
            recipe=other_recipe,
            ingredient=other_ingredient,
            quantity=Decimal("1.00"),
            unit="piece",
            order=0,
        )
        InventoryItem.objects.create(
            household=other_household,
            name="Salt",
            quantity=Decimal("1.00"),
            unit="piece",
            category="pantry",
            location="pantry",
            expiration_date=self.as_of_date,
        )

        matches = build_discovery_matches(self.household, as_of_date=self.as_of_date)
        returned_titles = {entry["recipe"].title for entry in matches}
        self.assertEqual(returned_titles, {"My Recipe"})
