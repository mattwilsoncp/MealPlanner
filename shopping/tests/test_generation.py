from datetime import date
from decimal import Decimal

from django.test import TestCase

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from inventory.models import InventoryItem
from meal_planner_app.models import MealPlan, MealType
from recipes.models import Recipe
from shopping.services import compute_meal_match, generate_week_shopping_list


class ShoppingGenerationServiceTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Test Home")
        self.week_start = date(2026, 4, 13)

    def _create_recipe_with_ingredients(self, title, ingredients):
        recipe = Recipe.objects.create(
            household=self.household,
            title=title,
            needs_review=False,
        )

        for index, (name, quantity, unit) in enumerate(ingredients):
            ingredient = Ingredient.objects.create(household=self.household, name=name)
            IngredientLink.objects.create(
                recipe=recipe,
                ingredient=ingredient,
                quantity=Decimal(quantity),
                unit=unit,
                order=index,
            )

        return recipe

    def test_generate_week_shopping_list_creates_items_from_meal_plans(self):
        recipe = self._create_recipe_with_ingredients(
            "Pancakes",
            [("Flour", "2.00", "cup"), ("Milk", "1.00", "cup")],
        )
        MealPlan.objects.create(
            household=self.household,
            meal_date=date(2026, 4, 15),
            meal_type=MealType.DINNER,
            recipe=recipe,
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Flour",
            quantity=Decimal("1.00"),
            unit="cup",
            category="pantry",
            location="pantry",
        )

        shopping_week = generate_week_shopping_list(self.household, self.week_start)

        items = {item.name: item for item in shopping_week.items.all()}
        self.assertEqual(set(items.keys()), {"Flour", "Milk"})
        self.assertEqual(items["Flour"].quantity, Decimal("1.00"))
        self.assertEqual(items["Milk"].quantity, Decimal("1.00"))

    def test_regenerate_rebuilds_items_for_week(self):
        recipe = self._create_recipe_with_ingredients(
            "Egg Toast",
            [("Egg", "2.00", "piece")],
        )
        MealPlan.objects.create(
            household=self.household,
            meal_date=date(2026, 4, 14),
            meal_type=MealType.BREAKFAST,
            recipe=recipe,
        )

        shopping_week = generate_week_shopping_list(self.household, self.week_start)
        self.assertEqual(shopping_week.items.count(), 1)
        self.assertEqual(shopping_week.items.first().quantity, Decimal("2.00"))

        InventoryItem.objects.create(
            household=self.household,
            name="Egg",
            quantity=Decimal("2.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
        )

        same_week = generate_week_shopping_list(
            self.household, self.week_start, regenerate=False
        )
        self.assertEqual(same_week.id, shopping_week.id)
        self.assertEqual(same_week.items.count(), 1)

        regenerated = generate_week_shopping_list(
            self.household, self.week_start, regenerate=True
        )
        self.assertEqual(regenerated.items.count(), 0)

    def test_compute_meal_match_returns_percentage_from_available_and_total(self):
        recipe = self._create_recipe_with_ingredients(
            "Salad",
            [
                ("Lettuce", "1.00", "piece"),
                ("Tomato", "1.00", "piece"),
                ("Cucumber", "1.00", "piece"),
            ],
        )
        inventory_items = [
            InventoryItem(
                household=self.household,
                name="Lettuce",
                quantity=Decimal("1.00"),
                unit="piece",
                category="produce",
                location="refrigerator",
            ),
            InventoryItem(
                household=self.household,
                name="Tomato",
                quantity=Decimal("2.00"),
                unit="piece",
                category="produce",
                location="refrigerator",
            ),
        ]

        stats = compute_meal_match(recipe, inventory_items)

        self.assertEqual(stats["available_count"], 2)
        self.assertEqual(stats["total_count"], 3)
        self.assertAlmostEqual(stats["match_percentage"], 66.67, places=2)
