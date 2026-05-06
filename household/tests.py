from django.core.exceptions import ValidationError
from django.test import TestCase

from household.models import Household


class HouseholdModelTests(TestCase):
    def test_expiring_threshold_defaults_to_seven(self):
        household = Household(name="Test Household")
        self.assertEqual(household.expiring_threshold_days, 7)

    def test_expiring_threshold_requires_positive_value(self):
        household = Household(name="Test Household", expiring_threshold_days=0)
        with self.assertRaises(ValidationError):
            household.full_clean()

    def test_name_max_length_is_enforced(self):
        household = Household(name="A" * 101)
        with self.assertRaises(ValidationError):
            household.full_clean()

    def test_name_at_max_length_is_valid(self):
        household = Household(name="A" * 100)
        household.full_clean()  # should not raise

    def test_str_returns_name(self):
        household = Household(name="My Home")
        self.assertEqual(str(household), "My Home")

    def test_delete_cascades_to_recipes(self):
        from recipes.models import Recipe
        household = Household.objects.create(name="Cascade Test Home")
        recipe = Recipe.objects.create(
            household=household,
            title="Test Recipe",
            needs_review=False,
        )
        recipe_id = recipe.id
        household.delete()
        self.assertFalse(Recipe.objects.filter(id=recipe_id).exists())

    def test_delete_cascades_to_ingredients(self):
        from ingredients.models import Ingredient
        household = Household.objects.create(name="Cascade Test Home 2")
        ingredient = Ingredient.objects.create(
            household=household,
            name="Flour",
            usda_food_id="0001",
        )
        ingredient_id = ingredient.id
        household.delete()
        self.assertFalse(Ingredient.objects.filter(id=ingredient_id).exists())

    def test_delete_cascades_to_inventory_items(self):
        from inventory.models import InventoryItem
        household = Household.objects.create(name="Cascade Test Home 3")
        item = InventoryItem.objects.create(
            household=household,
            name="Milk",
            quantity=1,
        )
        item_id = item.id
        household.delete()
        self.assertFalse(InventoryItem.objects.filter(id=item_id).exists())

    def test_delete_cascades_to_tags(self):
        from tags.models import Tag
        household = Household.objects.create(name="Cascade Test Home 4")
        tag = Tag.objects.create(
            household=household,
            name="Dinner",
        )
        tag_id = tag.id
        household.delete()
        self.assertFalse(Tag.objects.filter(id=tag_id).exists())

    def test_delete_sets_null_on_custom_user_household(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        household = Household.objects.create(name="Cascade Test Home 5")
        user = User.objects.create_user(
            username="cascadeuser",
            email="cascade@example.com",
            password="Pass1234!",
            household=household,
        )
        user_id = user.id
        household.delete()
        user.refresh_from_db()
        self.assertEqual(user.household, None)
