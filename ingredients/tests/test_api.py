"""Tests for ingredients/api.py endpoints."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import Ingredient


User = get_user_model()


class IngredientListAPITests(TestCase):
    """Tests for ingredient_list_api endpoint."""

    def setUp(self):
        self.household = Household.objects.create(name="Ingredient List Household")
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
        self.ingredient1 = Ingredient.objects.create(
            household=self.household,
            name="Flour",
            usda_food_id="USDA-12345",
        )
        self.ingredient2 = Ingredient.objects.create(
            household=self.household,
            name="Sugar",
        )
        self.other_ingredient = Ingredient.objects.create(
            household=self.other_household,
            name="Salt",
        )

    def test_list_api_unauthenticated_returns_redirect(self):
        """Unauthenticated request redirects to login page."""
        response = self.client.get(reverse("ingredients:ingredient_list_api"))
        self.assertEqual(response.status_code, 302)

    def test_list_api_returns_only_own_household_ingredients(self):
        """Only ingredients from user's household are returned."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("ingredients:ingredient_list_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        names = [i["name"] for i in data["ingredients"]]
        self.assertIn("Flour", names)
        self.assertIn("Sugar", names)
        self.assertNotIn("Salt", names)

    def test_list_api_ingredients_ordered_by_name(self):
        """Ingredients are returned ordered by name."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("ingredients:ingredient_list_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        names = [i["name"] for i in data["ingredients"]]
        self.assertEqual(names, sorted(names))

    def test_list_api_returns_expected_fields(self):
        """Response includes id and name."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("ingredients:ingredient_list_api"))
        self.assertEqual(response.status_code, 200)
        ingredient_data = response.json()["ingredients"][0]
        self.assertIn("id", ingredient_data)
        self.assertIn("name", ingredient_data)

    def test_list_api_empty_for_new_household(self):
        """Empty list returned when household has no ingredients."""
        new_household = Household.objects.create(name="Empty Household")
        new_user = User.objects.create_user(
            username="empty",
            email="empty@example.com",
            password="pass1234",
            household=new_household,
        )
        self.client.login(username="empty", password="pass1234")
        response = self.client.get(reverse("ingredients:ingredient_list_api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ingredients"], [])

    def test_list_api_rejects_non_get_methods(self):
        """Non-GET requests are rejected (405 Method Not Allowed)."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(reverse("ingredients:ingredient_list_api"))
        self.assertEqual(response.status_code, 405)
        response = self.client.put(reverse("ingredients:ingredient_list_api"))
        self.assertEqual(response.status_code, 405)
        response = self.client.delete(reverse("ingredients:ingredient_list_api"))
        self.assertEqual(response.status_code, 405)


class IngredientSearchAPITests(TestCase):
    """Tests for ingredient_search_api endpoint."""

    def setUp(self):
        self.household = Household.objects.create(name="Ingredient Search Household")
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
        self.ingredient1 = Ingredient.objects.create(
            household=self.household,
            name="Chocolate Chips",
            usda_food_id="USDA-20001",
        )
        self.ingredient2 = Ingredient.objects.create(
            household=self.household,
            name="Dark Chocolate",
        )
        self.ingredient3 = Ingredient.objects.create(
            household=self.household,
            name="Milk",
        )
        self.other_ingredient = Ingredient.objects.create(
            household=self.other_household,
            name="Milk",
        )

    def test_search_api_unauthenticated_returns_redirect(self):
        """Unauthenticated request redirects to login page."""
        response = self.client.get(reverse("ingredients:ingredient_search_api"))
        self.assertEqual(response.status_code, 302)

    def test_search_by_name_substring(self):
        """Search matches substring in ingredient name."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("ingredients:ingredient_search_api"), {"q": "Chocolate"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["ingredients"]
        names = [i["name"] for i in data]
        self.assertIn("Chocolate Chips", names)
        self.assertIn("Dark Chocolate", names)

    def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("ingredients:ingredient_search_api"), {"q": "chocolate"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["ingredients"]
        names = [i["name"] for i in data]
        self.assertIn("Chocolate Chips", names)
        self.assertIn("Dark Chocolate", names)

    def test_search_empty_query_returns_empty_list(self):
        """Empty q parameter returns empty list."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("ingredients:ingredient_search_api"), {"q": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ingredients"], [])

    def test_search_empty_query_whitespace_returns_empty_list(self):
        """Whitespace-only q parameter returns empty list."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("ingredients:ingredient_search_api"), {"q": "   "}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ingredients"], [])

    def test_search_no_params_returns_empty_list(self):
        """Missing q parameter returns empty list (strip() on None)."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("ingredients:ingredient_search_api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ingredients"], [])

    def test_search_only_returns_own_household(self):
        """Search does not return ingredients from other households."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("ingredients:ingredient_search_api"), {"q": "Milk"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["ingredients"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Milk")

    def test_search_respects_limit(self):
        """Search returns at most 20 results."""
        for i in range(25):
            Ingredient.objects.create(
                household=self.household,
                name=f"Ingredient {i}",
            )
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("ingredients:ingredient_search_api"), {"q": "Ingredient"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.json()["ingredients"]), 20)

    def test_search_returns_expected_fields(self):
        """Response includes id and name."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("ingredients:ingredient_search_api"), {"q": "Chocolate"}
        )
        self.assertEqual(response.status_code, 200)
        ingredient_data = response.json()["ingredients"][0]
        self.assertIn("id", ingredient_data)
        self.assertIn("name", ingredient_data)

    def test_search_no_matches_returns_empty_list(self):
        """Search with no matches returns empty list."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("ingredients:ingredient_search_api"), {"q": "xyznotfound"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ingredients"], [])

    def test_search_rejects_non_get_methods(self):
        """Non-GET requests are rejected (405 Method Not Allowed)."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("ingredients:ingredient_search_api"), {"q": "test"}
        )
        self.assertEqual(response.status_code, 405)