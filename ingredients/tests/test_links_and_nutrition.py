from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from inventory.models import InventoryItem
from recipes.models import Recipe


class IngredientLinksAndNutritionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Primary Household")
        self.other_household = Household.objects.create(name="Other Household")
        self.user = user_model.objects.create_user(
            username="ingredient-user",
            email="ingredient@example.com",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Protein Oats",
            description="Quick breakfast.",
            needs_review=True,
        )
        self.ingredient = Ingredient.objects.create(
            household=self.household,
            name="Rolled Oats",
            usda_food_id="USDA-1001",
        )
        self.ingredient_link = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("1.00"),
            unit="cup",
            order=0,
        )
        self.inventory_item = InventoryItem.objects.create(
            household=self.household,
            name="Rolled Oats Bin",
            quantity=Decimal("3.00"),
            unit="cup",
            category="pantry",
            location="pantry",
        )
        self.other_household_item = InventoryItem.objects.create(
            household=self.other_household,
            name="Other Household Oats",
            quantity=Decimal("8.00"),
            unit="cup",
            category="pantry",
            location="pantry",
        )

    def test_reconciliation_save_persists_household_inventory_link(self):
        response = self.client.post(
            reverse("reviews:save_reconciliation", args=[self.recipe.id]),
            data={
                f"inventory_item_{self.ingredient_link.id}": str(self.inventory_item.id)
            },
        )

        self.assertEqual(response.status_code, 302)
        self.ingredient_link.refresh_from_db()
        self.assertEqual(self.ingredient_link.inventory_item_id, self.inventory_item.id)

    def test_reconciliation_save_rejects_cross_household_inventory_link(self):
        response = self.client.post(
            reverse("reviews:save_reconciliation", args=[self.recipe.id]),
            data={
                f"inventory_item_{self.ingredient_link.id}": str(
                    self.other_household_item.id
                )
            },
        )

        self.assertEqual(response.status_code, 302)
        self.ingredient_link.refresh_from_db()
        self.assertIsNone(self.ingredient_link.inventory_item_id)

    def test_ingredient_model_exposes_usda_nutrition_snapshot_fields(self):
        expected_fields = ["calories_kcal", "protein_g", "carbs_g", "fat_g"]
        for field_name in expected_fields:
            try:
                Ingredient._meta.get_field(field_name)
            except FieldDoesNotExist as exc:  # pragma: no cover - explicit RED failure
                self.fail(
                    f"Ingredient is missing expected nutrition field: {field_name}"
                )

    def test_recipe_detail_includes_usda_reference_and_nutrition_in_context(self):
        self.ingredient.calories_kcal = Decimal("120.0")
        self.ingredient.protein_g = Decimal("5.0")
        self.ingredient.carbs_g = Decimal("20.0")
        self.ingredient.fat_g = Decimal("3.0")
        self.ingredient.save()

        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.id])
        )

        self.assertEqual(response.status_code, 200)
        first_ingredient_link = response.context["ingredients"][0]
        self.assertEqual(first_ingredient_link.ingredient.usda_food_id, "USDA-1001")
        self.assertEqual(
            first_ingredient_link.ingredient.calories_kcal, Decimal("120.0")
        )
        nutrition_entry = response.context["ingredient_nutrition"][0]
        self.assertEqual(nutrition_entry["usda_food_id"], "USDA-1001")
        self.assertEqual(nutrition_entry["protein_g"], Decimal("5.0"))
        self.assertTrue(nutrition_entry["has_nutrition"])
