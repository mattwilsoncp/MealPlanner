from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from inventory.models import InventoryItem
from meal_planner_app.models import MealPlan, MealType
from recipes.models import Recipe
from shopping.models import ShoppingListWeek
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


class ShoppingWeekViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Web Home")
        self.week_start = date(2026, 4, 13)
        self.user = get_user_model().objects.create_user(
            username="shopper",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def _create_recipe_with_meal(self):
        recipe = Recipe.objects.create(
            household=self.household,
            title="Pasta",
            needs_review=False,
        )
        ingredient = Ingredient.objects.create(household=self.household, name="Noodles")
        IngredientLink.objects.create(
            recipe=recipe,
            ingredient=ingredient,
            quantity=Decimal("1.00"),
            unit="box",
            order=0,
        )
        MealPlan.objects.create(
            household=self.household,
            meal_date=date(2026, 4, 14),
            meal_type=MealType.DINNER,
            recipe=recipe,
        )
        return recipe

    def test_week_view_auto_generates_when_missing(self):
        self._create_recipe_with_meal()

        response = self.client.get(
            reverse("shopping:week"),
            {"week_start": self.week_start.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        week = ShoppingListWeek.objects.get(
            household=self.household,
            week_start=self.week_start,
        )
        self.assertEqual(week.items.count(), 1)

    def test_regenerate_view_forces_rebuild_for_requested_week(self):
        self._create_recipe_with_meal()
        week = generate_week_shopping_list(self.household, self.week_start)
        self.assertEqual(week.items.count(), 1)

        InventoryItem.objects.create(
            household=self.household,
            name="Noodles",
            quantity=Decimal("1.00"),
            unit="box",
            category="pantry",
            location="pantry",
        )

        response = self.client.post(
            reverse("shopping:regenerate_week"),
            {"week_start": self.week_start.isoformat()},
        )
        self.assertEqual(response.status_code, 302)

        week.refresh_from_db()
        self.assertEqual(week.items.count(), 0)

    def test_invalid_week_start_defaults_to_current_monday(self):
        response = self.client.get(
            reverse("shopping:week"), {"week_start": "not-a-date"}
        )
        self.assertEqual(response.status_code, 200)
