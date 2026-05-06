from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import IngredientLink, Ingredient
from instructions.models import Instruction
from recipes.models import Recipe
from tags.models import Tag, RecipeTag


User = get_user_model()


class RecipeListViewTests(TestCase):
    """Tests for RecipeListView."""

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
        # Create recipes with different ages
        from django.utils import timezone
        self.now = timezone.now()

        self.recipe_new = Recipe.objects.create(
            household=self.household,
            title="New Recipe",
            needs_review=False,
        )
        # Manually set created_at to be recent
        Recipe.objects.filter(pk=self.recipe_new.pk).update(
            created_at=self.now
        )

        self.recipe_old = Recipe.objects.create(
            household=self.household,
            title="Old Recipe",
            needs_review=False,
        )
        Recipe.objects.filter(pk=self.recipe_old.pk).update(
            created_at=self.now - timedelta(days=30)
        )

        self.recipe_needs_review = Recipe.objects.create(
            household=self.household,
            title="Pending Recipe",
            needs_review=True,
        )

        self.other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Other Household Recipe",
            needs_review=False,
        )

    def test_list_requires_authentication(self):
        """Unauthenticated GET redirects to login."""
        response = self.client.get(reverse("recipes:recipe_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_list_returns_200_for_authenticated(self):
        """Authenticated GET returns 200."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"))
        self.assertEqual(response.status_code, 200)

    def test_list_excludes_other_household_recipes(self):
        """RecipeListView only shows recipes from user's household."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"))
        recipes_in_context = list(response.context["recipes"])
        titles = [r.title for r in recipes_in_context]
        self.assertIn("New Recipe", titles)
        self.assertIn("Old Recipe", titles)
        self.assertNotIn("Other Household Recipe", titles)

    def test_list_excludes_needs_review_recipes(self):
        """Recipes with needs_review=True are excluded from the list."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"))
        recipes_in_context = list(response.context["recipes"])
        titles = [r.title for r in recipes_in_context]
        self.assertNotIn("Pending Recipe", titles)

    def test_list_sort_newest(self):
        """Sort by newest returns most recent first."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"), {"sort": "newest"})
        recipes = list(response.context["recipes"])
        self.assertEqual(recipes[0].title, "New Recipe")
        self.assertEqual(recipes[1].title, "Old Recipe")

    def test_list_sort_oldest(self):
        """Sort by oldest returns earliest first."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"), {"sort": "oldest"})
        recipes = list(response.context["recipes"])
        self.assertEqual(recipes[0].title, "Old Recipe")
        self.assertEqual(recipes[1].title, "New Recipe")

    def test_list_sort_title_az(self):
        """Sort by title A-Z alphabetically."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"), {"sort": "title"})
        recipes = list(response.context["recipes"])
        titles = [r.title for r in recipes]
        self.assertEqual(titles[0], "New Recipe")  # N < O alphabetically
        self.assertEqual(titles[1], "Old Recipe")

    def test_list_search_filters_results(self):
        """Search by q param filters recipes by title/description."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"), {"q": "New"})
        recipes = list(response.context["recipes"])
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0].title, "New Recipe")

    def test_list_search_by_description(self):
        """Search matches description as well as title."""
        self.recipe_old.description = "A delicious new pasta"
        self.recipe_old.save()
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"), {"q": "pasta"})
        recipes = list(response.context["recipes"])
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0].title, "Old Recipe")

    def test_list_context_includes_sort_choices(self):
        """Context includes sort_choices for the template."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_list"))
        self.assertIn("sort_choices", response.context)
        sort_labels = [c[1] for c in response.context["sort_choices"]]
        self.assertIn("Newest First", sort_labels)
        self.assertIn("Oldest First", sort_labels)
        self.assertIn("Highest Rated", sort_labels)
        self.assertIn("Title A-Z", sort_labels)

    def test_list_context_includes_current_sort_and_query(self):
        """Context includes current sort and search query."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_list"), {"sort": "title", "q": "pasta"}
        )
        self.assertEqual(response.context["sort"], "title")
        self.assertEqual(response.context["q"], "pasta")


class RecipeDetailViewTests(TestCase):
    """Tests for RecipeDetailView."""

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
            description="A tasty recipe",
            needs_review=False,
        )
        self.ingredient = Ingredient.objects.create(
            household=self.household,
            name="Flour",
        )
        self.ing_link = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity=2,
            unit="cup",
        )
        Instruction.objects.create(
            recipe=self.recipe,
            step_number=1,
            text="Mix flour",
        )
        Instruction.objects.create(
            recipe=self.recipe,
            step_number=2,
            text="Bake",
        )

    def test_detail_requires_authentication(self):
        """Unauthenticated GET redirects to login."""
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_detail_returns_200_for_authenticated(self):
        """Authenticated GET returns 200."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_detail_context_includes_ingredients(self):
        """Context includes the recipe's ingredients."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.pk])
        )
        self.assertIn("ingredients", response.context)
        ingredients = list(response.context["ingredients"])
        self.assertEqual(len(ingredients), 1)
        self.assertEqual(ingredients[0].ingredient.name, "Flour")

    def test_detail_context_includes_instructions_ordered(self):
        """Context includes instructions ordered by step_number."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.pk])
        )
        self.assertIn("instructions", response.context)
        instructions = list(response.context["instructions"])
        self.assertEqual(len(instructions), 2)
        self.assertEqual(instructions[0].text, "Mix flour")
        self.assertEqual(instructions[1].text, "Bake")

    def test_detail_context_includes_average_rating(self):
        """Context includes average_rating (None when no ratings)."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.pk])
        )
        self.assertIn("average_rating", response.context)
        self.assertIsNone(response.context["average_rating"])

    def test_detail_context_includes_rating_form(self):
        """Context includes a rating_form for the user."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.pk])
        )
        self.assertIn("rating_form", response.context)

    def test_detail_context_includes_tags(self):
        """Context includes the recipe's tags."""
        tag = Tag.objects.create(household=self.household, name="Dinner", color="#fff")
        RecipeTag.objects.create(recipe=self.recipe, tag=tag)
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[self.recipe.pk])
        )
        self.assertIn("tags", response.context)
        tag_names = [rt.tag.name for rt in response.context["tags"]]
        self.assertIn("Dinner", tag_names)

    def test_detail_other_household_returns_404(self):
        """Recipe from another household returns 404."""
        other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Other Recipe",
            needs_review=False,
        )
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_detail", args=[other_recipe.pk])
        )
        self.assertEqual(response.status_code, 404)


class RecipeCreateViewTests(TestCase):
    """Tests for RecipeCreateView."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )

    def test_create_requires_authentication(self):
        """Unauthenticated GET redirects to login."""
        response = self.client.get(reverse("recipes:recipe_create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_create_get_returns_form(self):
        """Authenticated GET returns 200 with form."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("recipes:recipe_create"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_create_post_without_title_returns_form_errors(self):
        """POST without title returns 200 with form errors."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("recipes:recipe_create"),
            {
                "title": "",
                "description": "A recipe",
                "instruction_text_0": "Step 1",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("title", form.errors)

    def test_create_post_with_title_redirects_to_detail(self):
        """Valid POST redirects to the recipe detail page."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("recipes:recipe_create"),
            {
                "title": "New Cake",
                "description": "Delicious cake",
            },
        )
        self.assertEqual(Recipe.objects.count(), 1)
        recipe = Recipe.objects.first()
        self.assertEqual(recipe.title, "New Cake")
        self.assertEqual(recipe.household, self.household)
        self.assertRedirects(
            response,
            reverse("recipes:recipe_detail", args=[recipe.pk]),
        )

    def test_create_assigns_household_from_user(self):
        """Created recipe is assigned to the logged-in user's household."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("recipes:recipe_create"),
            {"title": "My Recipe", "description": "Test"},
        )
        recipe = Recipe.objects.first()
        self.assertEqual(recipe.household, self.household)


class RecipeDeleteViewTests(TestCase):
    """Tests for RecipeDeleteView."""

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
            title="To Delete",
            needs_review=False,
        )

    def test_delete_requires_authentication(self):
        """Unauthenticated GET redirects to login."""
        response = self.client.get(
            reverse("recipes:recipe_delete", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_delete_get_returns_confirm_template(self):
        """GET returns the confirmation page (200)."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_delete", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_post_removes_recipe(self):
        """POST deletes the recipe and redirects to list."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("recipes:recipe_delete", args=[self.recipe.pk])
        )
        self.assertEqual(Recipe.objects.filter(pk=self.recipe.pk).count(), 0)
        self.assertRedirects(response, reverse("recipes:recipe_list"))

    def test_delete_other_household_returns_404(self):
        """Deleting another household's recipe returns 404."""
        other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Bob's Recipe",
            needs_review=False,
        )
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("recipes:recipe_delete", args=[other_recipe.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Recipe.objects.filter(pk=other_recipe.pk).count(), 1)


class RecipeUpdateViewAdditionalTests(TestCase):
    """Additional tests for RecipeUpdateView beyond test_recipe_editing.py."""

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
            title="Original Title",
            description="Original desc",
            needs_review=False,
        )
        self.tag1 = Tag.objects.create(
            household=self.household, name="Vegan", color="#00ff00"
        )
        self.tag2 = Tag.objects.create(
            household=self.household, name="Spicy", color="#ff0000"
        )
        RecipeTag.objects.create(recipe=self.recipe, tag=self.tag1)

    def _update_payload(self):
        return {
            "title": self.recipe.title,
            "description": self.recipe.description,
            "video_url": "",
            "on_hand_idea": "",
            "leftover_worthy": "",
            "needs_review": "",
        }

    def test_update_other_household_returns_404(self):
        """Updating another household's recipe returns 404."""
        other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Bob's Recipe",
            needs_review=False,
        )
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("recipes:recipe_update", args=[other_recipe.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_update_deselects_removed_tags(self):
        """Removing a tag from the form deselects it on the recipe."""
        # Ensure recipe has tag1 via RecipeTag
        self.assertTrue(
            RecipeTag.objects.filter(recipe=self.recipe, tag=self.tag1).exists()
        )
        # POST without tag1 in the tags list
        payload = self._update_payload()
        payload["tags"] = []  # No tags selected

        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("recipes:recipe_update", args=[self.recipe.pk]),
            data=payload,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            RecipeTag.objects.filter(recipe=self.recipe, tag=self.tag1).exists()
        )

    def test_update_keeps_selected_tags(self):
        """Tags included in the form are kept on the recipe."""
        payload = self._update_payload()
        payload["tags"] = [str(self.tag1.pk)]

        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("recipes:recipe_update", args=[self.recipe.pk]),
            data=payload,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            RecipeTag.objects.filter(recipe=self.recipe, tag=self.tag1).exists()
        )

    def test_update_switches_tags(self):
        """Deselecting tag1 and selecting tag2 replaces the association."""
        payload = self._update_payload()
        payload["tags"] = [str(self.tag2.pk)]

        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("recipes:recipe_update", args=[self.recipe.pk]),
            data=payload,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            RecipeTag.objects.filter(recipe=self.recipe, tag=self.tag1).exists()
        )
        self.assertTrue(
            RecipeTag.objects.filter(recipe=self.recipe, tag=self.tag2).exists()
        )
