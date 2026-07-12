"""Tests for the backup/export system including all user data."""

import io
import json
import zipfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from household.models import Household
from ingredients.models import Ingredient
from instructions.models import Instruction
from inventory.models import InventoryCategory, InventoryItem, Store
from meal_planner_app.models import AISettings, MealPlan, MealPreferences, SideDish
from recipes.models import Recipe, RecipeWatchSegment, RecipeWatchSession
from shopping.models import ShoppingListItem, ShoppingListWeek
from tags.models import Tag


User = get_user_model()


def _tiny_jpeg():
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x09\x09\x08"
        b"\x0a\x0c\x14\x0d\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d"
        b"\x1a\x1c\x1c\x20\x24\x2e\x27\x20\x22\x2c\x23\x1c\x1c\x28\x37\x29\x2c\x30"
        b"\x31\x34\x34\x34\x1f\x27\x39\x3d\x38\x32\x3c\x2e\x33\x34\x32\xff\xc0\x00"
        b"\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05"
        b"\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04"
        b"\x05\x06\x07\x08\x09\x0a\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02"
        b"\x04\x03\x05\x05\x04\x04\x00\x00\x01\x7d\x01\x02\x03\x00\x04\x11\x05\x12"
        b"\x21\x31\x41\x06\x13\x51\x61\x07\x22\x71\x14\x32\x81\x91\xa1\x08\x23\x42"
        b"\xb1\xc1\x15\x52\xd1\xf0\x24\x33\x62\x72\x82\x09\x0a\x16\x17\x18\x19\x1a"
        b"\x25\x26\x27\x28\x29\x2a\x34\x35\x36\x37\x38\x39\x3a\x43\x44\x45\x46\x47"
        b"\x48\x49\x4a\x53\x54\x55\x56\x57\x58\x59\x5a\x63\x64\x65\x66\x67\x68\x69"
        b"\x6a\x73\x74\x75\x76\x77\x78\x79\x7a\x83\x84\x85\x86\x87\x88\x89\x8a\x92"
        b"\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2"
        b"\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2"
        b"\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea"
        b"\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc4\x00\x1f\x01\x00\x03\x01"
        b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04"
        b"\x05\x06\x07\x08\x09\x0a\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04"
        b"\x03\x04\x07\x05\x04\x04\x00\x01\x02\x77\x00\x01\x02\x03\x11\x04\x05\x21"
        b"\x31\x06\x12\x41\x51\x07\x61\x71\x13\x22\x32\x81\x08\x14\x42\x91\xa1\xb1"
        b"\xc1\x09\x23\x33\x52\xf0\x15\x62\x72\xd1\x0a\x16\x24\x34\xe1\x25\xf1\x17"
        b"\x18\x19\x1a\x26\x27\x28\x29\x2a\x35\x36\x37\x38\x39\x3a\x43\x44\x45\x46"
        b"\x47\x48\x49\x4a\x53\x54\x55\x56\x57\x58\x59\x5a\x63\x64\x65\x66\x67\x68"
        b"\x69\x6a\x73\x74\x75\x76\x77\x78\x79\x7a\x82\x83\x84\x85\x86\x87\x88\x89"
        b"\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9"
        b"\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9"
        b"\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9"
        b"\xea\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00"
        b"\x3f\x00\x37\x07\xff\xd9"
    )


class BackupRoundTripTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Backup Household")
        self.user = User.objects.create_user(
            username="backup-user",
            email="backup@example.com",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

        self.store = Store.objects.create(
            household=self.household, name="Costco", notes="Warehouse"
        )
        InventoryCategory.add("bulk", "Bulk Goods", sort_order=10)
        InventoryCategory.add("spices", "Spices", sort_order=20)

        self.ingredient = Ingredient.objects.create(
            household=self.household,
            name="All-Purpose Flour",
            usda_food_id="123456",
            calories_kcal=Decimal("364.0"),
            protein_g=Decimal("10.3"),
            carbs_g=Decimal("76.3"),
            fat_g=Decimal("1.0"),
        )

        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Backup Watch Recipe",
            video_url="https://www.youtube.com/watch?v=abcdefghijk",
            transcript_log="logs/transcripts/20260101_test.txt",
        )
        self.recipe.photo.save("photo.jpg", io.BytesIO(_tiny_jpeg()), save=True)

        from ingredients.models import IngredientLink

        IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=Decimal("2.00"),
            unit="cup",
            order=1,
        )

        Instruction.objects.create(
            recipe=self.recipe, step_number=1, text="Mix dry ingredients"
        )
        self.instruction = Instruction.objects.create(
            recipe=self.recipe, step_number=2, text="Knead dough"
        )
        self.instruction.image.save("step.jpg", io.BytesIO(_tiny_jpeg()), save=True)

        tag = Tag.objects.create(household=self.household, name="Baking", color="#6B7280")
        self.recipe.recipetag_set.create(tag=tag)

        self.session = RecipeWatchSession.objects.create(
            recipe=self.recipe,
            status=RecipeWatchSession.Status.READY,
            error_message="",
        )
        self.segment = RecipeWatchSegment.objects.create(
            session=self.session,
            start_time=Decimal("5.000"),
            end_time=Decimal("10.000"),
            text="Mix the ingredients",
            step_number=1,
        )
        self.segment.image.save("frame.jpg", io.BytesIO(_tiny_jpeg()), save=True)

        self.inventory_item = InventoryItem.objects.create(
            household=self.household,
            name="Organic Flour",
            quantity=Decimal("5.00"),
            unit="lb",
            category="bulk",
            location="pantry",
            price=Decimal("12.99"),
            store=self.store,
            barcode="123456789012",
        )
        self.inventory_item.image.save("inv.jpg", io.BytesIO(_tiny_jpeg()), save=True)

        MealPreferences.objects.create(
            household=self.household,
            cuisine_preferences=["italian", "mexican"],
            dietary_restrictions=["vegetarian"],
            cooking_effort="moderate",
            servings_per_meal=4,
            excluded_ingredients=["cilantro"],
        )
        AISettings.objects.create(
            household=self.household,
            model_bindings={"recipe_import_text": {"model_id": "test-model"}},
            openrouter_api_key_override="sk-or-test",
            usda_fdc_api_key_override="DEMO_KEY",
        )

        self.meal_plan = MealPlan.objects.create(
            household=self.household,
            meal_date=timezone.localdate(),
            meal_type="dinner",
            recipe=self.recipe,
            notes="Test meal",
        )
        SideDish.objects.create(
            meal_plan=self.meal_plan, recipe=self.recipe, order=1, notes="side"
        )

        week = ShoppingListWeek.objects.create(
            household=self.household, week_start=timezone.localdate()
        )
        ShoppingListItem.objects.create(
            shopping_week=week,
            name="Flour",
            quantity=Decimal("2"),
            unit="lb",
            category="bulk",
            source_recipe=self.recipe,
        )

        from ratings.models import Rating

        Rating.objects.create(recipe=self.recipe, user=self.user, score=5, notes="Great")

    def tearDown(self):
        for attr in ("segment", "instruction", "inventory_item", "recipe"):
            obj = getattr(self, attr, None)
            if obj and getattr(obj, "image", None):
                obj.image.delete(save=False)
            if obj and getattr(obj, "photo", None):
                obj.photo.delete(save=False)

    def _export_and_parse(self):
        response = self.client.get(reverse("backup_export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        data = json.loads(zf.read("backup.json").decode("utf-8"))
        return data, zf, response.content

    def _import_into_new_household(self, backup_bytes):
        new_household = Household.objects.create(name="Import Household")
        new_user = User.objects.create_user(
            username="import-user",
            email="import@example.com",
            password="pass1234",
            household=new_household,
        )
        self.client.force_login(new_user)
        import_file = io.BytesIO(backup_bytes)
        import_file.name = "backup.zip"
        response = self.client.post(
            reverse("backup_import"),
            {"backup_file": import_file},
        )
        self.assertEqual(response.status_code, 200)
        return response.json(), new_household

    def test_backup_version(self):
        data, _zf, _bytes = self._export_and_parse()
        self.assertEqual(data["version"], 6)

    def test_watch_session_round_trip(self):
        data, zf, backup_bytes = self._export_and_parse()
        recipe_data = data["recipes"][0]
        self.assertIn("watch_session", recipe_data)
        segment_data = recipe_data["watch_session"]["segments"][0]
        frame_path = segment_data["frame_path"]
        self.assertTrue(frame_path.startswith(f"watch_frames/{self.recipe.pk}/"))
        self.assertIn(frame_path, zf.namelist())
        frame_bytes = zf.read(frame_path)

        body, new_household = self._import_into_new_household(backup_bytes)
        self.assertEqual(body["stats"]["recipes_imported"], 1)

        recipe = Recipe.objects.get(household=new_household, title="Backup Watch Recipe")
        segment = recipe.watch_session.segments.first()
        segment.image.open("rb")
        imported_bytes = segment.image.read()
        segment.image.close()
        self.assertEqual(imported_bytes, frame_bytes)

    def test_inventory_category_round_trip(self):
        data, _zf, backup_bytes = self._export_and_parse()
        self.assertTrue(
            any(c["slug"] == "bulk" and c["name"] == "Bulk Goods" for c in data["inventory_categories"])
        )

        InventoryCategory.objects.filter(slug__in=["bulk", "spices"]).delete()
        body, _new_household = self._import_into_new_household(backup_bytes)
        self.assertTrue(body["ok"])
        bulk = InventoryCategory.objects.get(slug="bulk")
        self.assertEqual(bulk.name, "Bulk Goods")
        self.assertEqual(bulk.sort_order, 10)

    def test_store_and_inventory_round_trip(self):
        data, zf, backup_bytes = self._export_and_parse()
        self.assertTrue(any(s["name"] == "Costco" for s in data["stores"]))
        item_data = data["inventory"][0]
        self.assertEqual(item_data["store_name"], "Costco")
        self.assertEqual(item_data["price"], "12.99")
        image_path = item_data["image_path"]
        image_bytes = zf.read(image_path)

        body, new_household = self._import_into_new_household(backup_bytes)
        self.assertEqual(body["stats"]["inventory_imported"], 1)

        item = InventoryItem.objects.get(household=new_household, name="Organic Flour")
        self.assertEqual(item.store.name, "Costco")
        self.assertEqual(item.price, Decimal("12.99"))
        self.assertEqual(item.barcode, "123456789012")
        item.image.open("rb")
        self.assertEqual(item.image.read(), image_bytes)
        item.image.close()

    def test_ingredient_metadata_round_trip(self):
        data, _zf, backup_bytes = self._export_and_parse()
        ing_data = next(i for i in data["ingredients"] if i["name"] == "All-Purpose Flour")
        self.assertEqual(ing_data["usda_food_id"], "123456")
        self.assertEqual(ing_data["protein_g"], "10.30")

        body, new_household = self._import_into_new_household(backup_bytes)
        self.assertTrue(body["ok"])
        ingredient = Ingredient.objects.get(household=new_household, name="All-Purpose Flour")
        self.assertEqual(ingredient.usda_food_id, "123456")
        self.assertEqual(ingredient.protein_g, Decimal("10.30"))

    def test_instruction_image_round_trip(self):
        data, zf, backup_bytes = self._export_and_parse()
        recipe_data = data["recipes"][0]
        inst_data = next(i for i in recipe_data["instructions"] if i["step_number"] == 2)
        image_path = inst_data["image_path"]
        image_bytes = zf.read(image_path)

        body, new_household = self._import_into_new_household(backup_bytes)
        self.assertTrue(body["ok"])
        instruction = Instruction.objects.get(
            recipe__household=new_household, step_number=2, text="Knead dough"
        )
        instruction.image.open("rb")
        self.assertEqual(instruction.image.read(), image_bytes)
        instruction.image.close()

    def test_meal_preferences_and_ai_settings_round_trip(self):
        data, _zf, backup_bytes = self._export_and_parse()
        self.assertEqual(data["meal_preferences"]["servings_per_meal"], 4)
        self.assertEqual(data["ai_settings"]["openrouter_api_key_override"], "sk-or-test")

        body, new_household = self._import_into_new_household(backup_bytes)
        self.assertTrue(body["ok"])
        prefs = new_household.meal_preferences
        self.assertEqual(prefs.servings_per_meal, 4)
        self.assertEqual(prefs.cuisine_preferences, ["italian", "mexican"])
        settings = new_household.ai_settings
        self.assertEqual(settings.model_bindings["recipe_import_text"]["model_id"], "test-model")
        self.assertEqual(settings.openrouter_api_key_override, "sk-or-test")

    def test_meal_plan_and_side_dish_round_trip(self):
        data, _zf, backup_bytes = self._export_and_parse()
        plan_data = data["meal_plans"][0]
        self.assertEqual(plan_data["recipe_title"], "Backup Watch Recipe")
        self.assertEqual(len(plan_data["side_dishes"]), 1)

        body, new_household = self._import_into_new_household(backup_bytes)
        self.assertEqual(body["stats"]["meal_plans_imported"], 1)
        plan = MealPlan.objects.get(household=new_household, meal_type="dinner")
        self.assertEqual(plan.recipe.title, "Backup Watch Recipe")
        self.assertEqual(plan.side_dishes.count(), 1)

    def test_shopping_list_round_trip(self):
        data, _zf, backup_bytes = self._export_and_parse()
        week_data = data["shopping_lists"][0]
        item_data = week_data["items"][0]
        self.assertEqual(item_data["recipe_title"], "Backup Watch Recipe")

        body, new_household = self._import_into_new_household(backup_bytes)
        self.assertEqual(body["stats"]["shopping_lists_imported"], 1)
        week = ShoppingListWeek.objects.get(household=new_household)
        item = week.items.first()
        self.assertEqual(item.source_recipe.title, "Backup Watch Recipe")

    def test_ratings_round_trip(self):
        data, _zf, backup_bytes = self._export_and_parse()
        rating_data = data["ratings"][0]
        self.assertEqual(rating_data["recipe_title"], "Backup Watch Recipe")
        self.assertEqual(rating_data["score"], 5)

        body, new_household = self._import_into_new_household(backup_bytes)
        self.assertEqual(body["stats"]["ratings_imported"], 1)
        from ratings.models import Rating

        rating = Rating.objects.get(recipe__household=new_household, user__username="import-user")
        self.assertEqual(rating.score, 5)
        self.assertEqual(rating.notes, "Great")
