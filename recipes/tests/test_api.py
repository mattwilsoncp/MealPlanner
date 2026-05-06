from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import IngredientLink, Ingredient
from instructions.models import Instruction
from recipes.models import Recipe
from tags.models import Tag, RecipeTag


User = get_user_model()


class RecipeListAPITests(TestCase):
    """Tests for recipe_list_api endpoint."""

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
        self.recipe1 = Recipe.objects.create(
            household=self.household,
            title="My Recipe",
            description="Description",
            needs_review=False,
        )
        self.recipe2 = Recipe.objects.create(
            household=self.household,
            title="Other Recipe",
            needs_review=False,
        )
        self.needs_review_recipe = Recipe.objects.create(
            household=self.household,
            title="Pending Recipe",
            needs_review=True,
        )
        self.other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Not My Recipe",
            needs_review=False,
        )

    def test_list_api_unauthenticated_returns_redirect(self):
        """Unauthenticated request redirects to login page."""
        response = self.client.get(reverse("recipes:recipe_list_api"))
        self.assertEqual(response.status_code, 302)

    def test_list_api_returns_only_own_household_recipes(self):
        """Only recipes from user's household are returned."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        titles = [r["title"] for r in data["recipes"]]
        self.assertIn("My Recipe", titles)
        self.assertIn("Other Recipe", titles)
        self.assertNotIn("Not My Recipe", titles)
        self.assertNotIn("Pending Recipe", titles)

    def test_list_api_excludes_needs_review(self):
        """Recipes with needs_review=True are excluded."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list_api"))
        self.assertEqual(response.status_code, 200)
        titles = [r["title"] for r in response.json()["recipes"]]
        self.assertNotIn("Pending Recipe", titles)

    def test_list_api_returns_expected_fields(self):
        """Response includes id, title, description, rating, tags, needs_review."""
        tag = Tag.objects.create(household=self.household, name="Dinner")
        RecipeTag.objects.create(recipe=self.recipe1, tag=tag)
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list_api"))
        self.assertEqual(response.status_code, 200)
        recipe_data = response.json()["recipes"][0]
        self.assertIn("id", recipe_data)
        self.assertIn("title", recipe_data)
        self.assertIn("description", recipe_data)
        self.assertIn("needs_review", recipe_data)
        self.assertIn("tags", recipe_data)


class RecipeSearchAPITests(TestCase):
    """Tests for recipe_search_api endpoint."""

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
            title="Chocolate Cake",
            description="Rich and moist",
            needs_review=False,
        )
        self.other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Vanilla Cake",
            description="Light and fluffy",
            needs_review=False,
        )

    def test_search_api_unauthenticated_returns_redirect(self):
        """Unauthenticated request redirects to login page."""
        response = self.client.get(reverse("recipes:recipe_search_api"))
        self.assertEqual(response.status_code, 302)

    def test_search_by_title(self):
        """Search matches recipe title."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_search_api"), {"q": "Chocolate"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["recipes"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Chocolate Cake")

    def test_search_by_description(self):
        """Search matches recipe description."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_search_api"), {"q": "moist"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["recipes"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Chocolate Cake")

    def test_search_empty_query_returns_empty(self):
        """Empty q parameter returns empty list."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_search_api"), {"q": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recipes"], [])

    def test_search_only_returns_own_household(self):
        """Search does not return recipes from other households."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_search_api"), {"q": "Cake"}
        )
        self.assertEqual(response.status_code, 200)
        titles = [r["title"] for r in response.json()["recipes"]]
        self.assertIn("Chocolate Cake", titles)
        self.assertNotIn("Vanilla Cake", titles)

    def test_search_respects_limit(self):
        """Search returns at most 20 results."""
        self.client.login(username="alice", password="pass1234")
        # Create 25 recipes
        for i in range(25):
            Recipe.objects.create(
                household=self.household,
                title=f"Recipe {i}",
                needs_review=False,
            )
        response = self.client.get(
            reverse("recipes:recipe_search_api"), {"q": "Recipe"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.json()["recipes"]), 20)


class RecipeDetailAPITests(TestCase):
    """Tests for recipe_detail_api endpoint."""

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
            title="Test Recipe",
            description="A test recipe",
            needs_review=False,
        )
        self.ingredient = Ingredient.objects.create(
            household=self.household,
            name="Sugar",
        )
        IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=2,
            unit="cup",
        )
        Instruction.objects.create(
            recipe=self.recipe,
            step_number=1,
            text="Mix sugar",
        )
        Instruction.objects.create(
            recipe=self.recipe,
            step_number=2,
            text="Serve",
        )

    def test_detail_api_unauthenticated_returns_redirect(self):
        """Unauthenticated request redirects to login page."""
        url = reverse("recipes:recipe_detail_api", args=[self.recipe.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_detail_api_returns_ingredients_and_instructions(self):
        """Response includes ordered ingredients and instructions."""
        self.client.login(username="alice", password="pass1234")
        url = reverse("recipes:recipe_detail_api", args=[self.recipe.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "Test Recipe")
        self.assertEqual(len(data["ingredients"]), 1)
        self.assertEqual(data["ingredients"][0]["name"], "Sugar")
        self.assertEqual(len(data["instructions"]), 2)
        self.assertEqual(data["instructions"][0]["step"], "Mix sugar")
        self.assertEqual(data["instructions"][0]["step_number"], 1)
        self.assertEqual(data["instructions"][1]["step"], "Serve")
        self.assertEqual(data["instructions"][1]["step_number"], 2)

    def test_detail_api_other_household_returns_404(self):
        """Recipe from another household returns 404."""
        other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Bob's Recipe",
            needs_review=False,
        )
        self.client.login(username="alice", password="pass1234")
        url = reverse("recipes:recipe_detail_api", args=[other_recipe.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class RecipeToggleReviewAPITests(TestCase):
    """Tests for recipe_toggle_review endpoint."""

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
            needs_review=True,
        )

    def test_toggle_review_unauthenticated_returns_redirect(self):
        """Unauthenticated POST redirects to login page."""
        url = reverse("recipes:recipe_toggle_review", args=[self.recipe.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_toggle_review_flips_needs_review_true_to_false(self):
        """First POST flips needs_review from True to False."""
        self.assertTrue(self.recipe.needs_review)
        self.client.login(username="alice", password="pass1234")
        url = reverse("recipes:recipe_toggle_review", args=[self.recipe.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.recipe.refresh_from_db()
        self.assertFalse(self.recipe.needs_review)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["needs_review"])

    def test_toggle_review_flips_false_to_true(self):
        """Second POST flips needs_review back to True."""
        self.recipe.needs_review = False
        self.recipe.save()
        self.client.login(username="alice", password="pass1234")
        url = reverse("recipes:recipe_toggle_review", args=[self.recipe.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.recipe.refresh_from_db()
        self.assertTrue(self.recipe.needs_review)

    def test_toggle_review_other_household_returns_404(self):
        """Toggling another household's recipe returns 404."""
        other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Bob's Recipe",
            needs_review=True,
        )
        self.client.login(username="alice", password="pass1234")
        url = reverse("recipes:recipe_toggle_review", args=[other_recipe.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
