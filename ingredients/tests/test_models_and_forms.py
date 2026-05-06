from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from ingredients.forms import IngredientNutritionForm, IngredientLinkReconciliationForm
from inventory.models import InventoryItem
from recipes.models import Recipe


class IngredientModelTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.household = Household.objects.create(name="Ingredient Test Home")
        self.other_household = Household.objects.create(name="Other Home")
        self.user = self.user_model.objects.create_user(
            username="inguser",
            email="ing@example.com",
            password="Pass1234!",
            household=self.household,
        )

    def test_create_ingredient(self):
        ing = Ingredient.objects.create(
            household=self.household,
            name="Rolled Oats",
            usda_food_id="USDA-1001",
        )
        self.assertEqual(ing.name, "Rolled Oats")
        self.assertEqual(ing.household, self.household)
        self.assertEqual(str(ing), "Rolled Oats")

    def test_ingredient_name_unique_within_household(self):
        Ingredient.objects.create(
            household=self.household,
            name="Flour",
        )
        dup = Ingredient(
            household=self.household,
            name="Flour",
        )
        with self.assertRaises(ValidationError):
            dup.full_clean()

    def test_same_ingredient_name_allowed_in_different_household(self):
        Ingredient.objects.create(
            household=self.household,
            name="Salt",
        )
        other = Ingredient(
            household=self.other_household,
            name="Salt",
        )
        other.full_clean()  # should not raise

    def test_ingredient_requires_household(self):
        ing = Ingredient(name="Orphan")
        with self.assertRaises(ValidationError):
            ing.full_clean()

    def test_ingredient_delete_cascades_from_household(self):
        ing = Ingredient.objects.create(
            household=self.household,
            name="Cascades",
        )
        ing_id = ing.id
        self.household.delete()
        self.assertFalse(Ingredient.objects.filter(id=ing_id).exists())


class IngredientLinkModelTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.household = Household.objects.create(name="Link Test Home")
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )
        self.ingredient = Ingredient.objects.create(
            household=self.household,
            name="Egg",
        )

    def test_create_ingredient_link(self):
        link = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("2.0"),
            unit="piece",
            order=0,
        )
        self.assertEqual(link.quantity, Decimal("2.0"))
        self.assertEqual(link.unit, "piece")
        self.assertEqual(link.order, 0)

    def test_ingredient_link_str(self):
        link = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("1.5"),
            unit="cup",
            order=0,
        )
        self.assertEqual(str(link), "1.5 cup Egg")

    def test_ingredient_link_delete_cascades_from_recipe(self):
        link = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("1.0"),
            unit="piece",
            order=0,
        )
        link_id = link.id
        self.recipe.delete()
        self.assertFalse(IngredientLink.objects.filter(id=link_id).exists())

    def test_ingredient_link_delete_cascades_from_ingredient(self):
        link = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("1.0"),
            unit="piece",
            order=0,
        )
        link_id = link.id
        self.ingredient.delete()
        self.assertFalse(IngredientLink.objects.filter(id=link_id).exists())

    def test_ingredient_link_optional_inventory_item(self):
        link = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("1.0"),
            unit="piece",
            order=0,
        )
        self.assertIsNone(link.inventory_item)

    def test_ingredient_link_ordering(self):
        link1 = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("1.0"),
            unit="piece",
            order=2,
        )
        link2 = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("2.0"),
            unit="piece",
            order=1,
        )
        links = list(self.recipe.ingredients.all())
        self.assertEqual(links[0].order, 1)
        self.assertEqual(links[1].order, 2)


class IngredientNutritionFormTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Form Test Home")

    def test_valid_nutrition_data(self):
        form = IngredientNutritionForm(
            data={
                "usda_food_id": "USDA-12345",
                "calories_kcal": "150.0",
                "protein_g": "5.0",
                "carbs_g": "20.0",
                "fat_g": "3.0",
            }
        )
        self.assertTrue(form.is_valid())

    def test_nutrition_fields_all_optional(self):
        form = IngredientNutritionForm(data={"usda_food_id": ""})
        self.assertTrue(form.is_valid())

    def test_usda_food_id_too_long_rejected(self):
        form = IngredientNutritionForm(
            data={"usda_food_id": "X" * 21}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("usda_food_id", form.errors)

    def test_usda_food_id_at_max_length_accepted(self):
        form = IngredientNutritionForm(
            data={"usda_food_id": "X" * 20}
        )
        self.assertTrue(form.is_valid())

    def test_calories_upper_bound_enforced(self):
        form = IngredientNutritionForm(
            data={"calories_kcal": "6000"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("calories_kcal", form.errors)

    def test_negative_calories_rejected(self):
        form = IngredientNutritionForm(
            data={"calories_kcal": "-10"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("calories_kcal", form.errors)


class IngredientLinkReconciliationFormTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Reconcile Test Home")
        self.other_household = Household.objects.create(name="Other Reconcile Home")
        self.inventory_item = InventoryItem.objects.create(
            household=self.household,
            name="Test Item",
            quantity=Decimal("1.0"),
            unit="piece",
        )
        self.other_item = InventoryItem.objects.create(
            household=self.other_household,
            name="Other Item",
            quantity=Decimal("1.0"),
            unit="piece",
        )

    def test_valid_inventory_item(self):
        form = IngredientLinkReconciliationForm(
            data={"inventory_item_id": str(self.inventory_item.id)},
            household=self.household,
        )
        self.assertTrue(form.is_valid())

    def test_empty_inventory_item_returns_none(self):
        form = IngredientLinkReconciliationForm(
            data={"inventory_item_id": ""},
            household=self.household,
        )
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data["inventory_item_id"])

    def test_none_string_returns_none(self):
        form = IngredientLinkReconciliationForm(
            data={"inventory_item_id": "none"},
            household=self.household,
        )
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data["inventory_item_id"])

    def test_cross_household_item_rejected(self):
        form = IngredientLinkReconciliationForm(
            data={"inventory_item_id": str(self.other_item.id)},
            household=self.household,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("inventory_item_id", form.errors)

    def test_invalid_id_rejected(self):
        form = IngredientLinkReconciliationForm(
            data={"inventory_item_id": "99999"},
            household=self.household,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("inventory_item_id", form.errors)
