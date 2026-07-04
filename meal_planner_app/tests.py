from datetime import date, timedelta
from decimal import Decimal
from json import dumps as json_dumps, loads as json_loads
from unittest.mock import MagicMock, patch

import httpx

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, RequestFactory, TransactionTestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from instructions.models import Instruction
from meal_planner_app.models import MealPlan, MealType, SideDish, MealPreferences
from meal_planner_app.forms import MealPlanForm
from meal_planner_app.models import CookingEffort
from recipes.models import Recipe


User = get_user_model()


# =============================================================================
# Model Tests
# =============================================================================


class MealPlanModelTests(TestCase):
    """Tests for MealPlan model creation, constraints, and behavior."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            description="A test recipe",
            needs_review=False,
        )
        self.today = date.today()

    def test_create_mealplan_with_recipe(self):
        """MealPlan creates successfully with a recipe assigned."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )
        self.assertEqual(meal.household, self.household)
        self.assertEqual(meal.meal_date, self.today)
        self.assertEqual(meal.meal_type, MealType.DINNER)
        self.assertEqual(meal.recipe, self.recipe)
        self.assertIsNone(meal.custom_meal)
        self.assertIsNone(meal.notes)
        self.assertIsNone(meal.meal_rating)
        self.assertIsNone(meal.cooked_at)

    def test_create_mealplan_with_custom_meal(self):
        """MealPlan creates successfully with a custom meal (no recipe)."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.LUNCH,
            custom_meal="Homemade Pizza",
        )
        self.assertIsNone(meal.recipe)
        self.assertEqual(meal.custom_meal, "Homemade Pizza")

    def test_create_mealplan_with_notes_and_rating(self):
        """MealPlan stores notes and rating correctly."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.BREAKFAST,
            recipe=self.recipe,
            notes="Great with extra cheese",
            meal_rating=4,
        )
        self.assertEqual(meal.notes, "Great with extra cheese")
        self.assertEqual(meal.meal_rating, 4)

    def test_delete_household_cascades_to_mealplans(self):
        """Deleting household deletes all its MealPlan entries."""
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.today + timedelta(days=1),
            meal_type=MealType.LUNCH,
            custom_meal="Salad",
        )
        self.assertEqual(MealPlan.objects.count(), 2)
        self.household.delete()
        self.assertEqual(MealPlan.objects.count(), 0)

    def test_delete_recipe_sets_null_on_mealplan(self):
        """Deleting a recipe sets recipe FK to NULL on MealPlan (SET_NULL)."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )
        self.assertEqual(meal.recipe, self.recipe)
        self.recipe.delete()
        meal.refresh_from_db()
        self.assertIsNone(meal.recipe)

    def test_unique_constraint_prevents_duplicate(self):
        """Unique together (household, meal_date, meal_type, recipe) prevents duplicates."""
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )
        with self.assertRaises(IntegrityError):
            MealPlan.objects.create(
                household=self.household,
                meal_date=self.today,
                meal_type=MealType.DINNER,
                recipe=self.recipe,
            )

    def test_same_type_different_date_is_valid(self):
        """Same meal_type on different dates is allowed."""
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )
        tomorrow = self.today + timedelta(days=1)
        meal2 = MealPlan.objects.create(
            household=self.household,
            meal_date=tomorrow,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )
        self.assertIsNotNone(meal2.id)

    def test_str_with_recipe(self):
        """str(meal) returns recipe title."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )
        self.assertIn("Test Recipe", str(meal))
        self.assertIn("Dinner", str(meal))
        self.assertIn(str(self.today), str(meal))

    def test_str_with_custom_meal(self):
        """str(meal) falls back to custom_meal when no recipe."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.LUNCH,
            custom_meal="Grilled Cheese",
        )
        self.assertIn("Grilled Cheese", str(meal))

    def test_str_with_no_meal_returns_placeholder(self):
        """str(meal) with neither recipe nor custom_meal returns 'No meal'."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.SNACK,
            # no recipe, no custom_meal
        )
        self.assertIn("No meal", str(meal))

    def test_is_custom_true_when_no_recipe(self):
        """is_custom is True when meal has no recipe."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.BREAKFAST,
            custom_meal="Eggs",
        )
        self.assertTrue(meal.is_custom)

    def test_is_custom_false_when_recipe(self):
        """is_custom is False when meal has a recipe."""
        meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.BREAKFAST,
            recipe=self.recipe,
        )
        self.assertFalse(meal.is_custom)

    def test_ordering_by_date_and_type(self):
        """MealPlans are ordered by meal_date ASC, meal_type ASC."""
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.today + timedelta(days=1),
            meal_type=MealType.BREAKFAST,
            recipe=self.recipe,
        )
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.today,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )
        meals = list(MealPlan.objects.all())
        self.assertEqual(meals[0].meal_date, self.today)
        self.assertEqual(meals[0].meal_type, MealType.DINNER)
        self.assertEqual(meals[1].meal_date, self.today + timedelta(days=1))
        self.assertEqual(meals[1].meal_type, MealType.BREAKFAST)


class MealTypeTests(TestCase):
    """Tests for MealType choices."""

    def test_meal_type_choices_exist(self):
        """All four meal types are available."""
        self.assertEqual(MealType.BREAKFAST, "breakfast")
        self.assertEqual(MealType.LUNCH, "lunch")
        self.assertEqual(MealType.DINNER, "dinner")
        self.assertEqual(MealType.SNACK, "snack")

    def test_meal_type_display_values(self):
        """MealType display values are human-readable."""
        self.assertEqual(MealType.BREAKFAST.label, "Breakfast")
        self.assertEqual(MealType.LUNCH.label, "Lunch")
        self.assertEqual(MealType.DINNER.label, "Dinner")
        self.assertEqual(MealType.SNACK.label, "Snack")

    def test_meal_type_choices_length(self):
        """Exactly 4 meal type choices exist."""
        self.assertEqual(len(MealType.choices), 4)


class SideDishModelTests(TestCase):
    """Tests for SideDish model."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Main Recipe",
            needs_review=False,
        )
        self.side_recipe = Recipe.objects.create(
            household=self.household,
            title="Side Recipe",
            needs_review=False,
        )
        self.meal = MealPlan.objects.create(
            household=self.household,
            meal_date=date.today(),
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )

    def test_create_side_dish_with_recipe(self):
        """SideDish creates with a recipe."""
        sd = SideDish.objects.create(
            meal_plan=self.meal,
            recipe=self.side_recipe,
            order=1,
        )
        self.assertEqual(sd.recipe, self.side_recipe)
        self.assertEqual(sd.meal_plan, self.meal)

    def test_create_side_dish_with_custom_side(self):
        """SideDish creates with a custom_side string."""
        sd = SideDish.objects.create(
            meal_plan=self.meal,
            custom_side="Mashed Potatoes",
            order=0,
        )
        self.assertIsNone(sd.recipe)
        self.assertEqual(sd.custom_side, "Mashed Potatoes")

    def test_delete_meal_plan_cascades_to_side_dishes(self):
        """Deleting MealPlan deletes its SideDish entries."""
        SideDish.objects.create(meal_plan=self.meal, custom_side="Salad", order=0)
        SideDish.objects.create(meal_plan=self.meal, recipe=self.side_recipe, order=1)
        self.assertEqual(SideDish.objects.count(), 2)
        self.meal.delete()
        self.assertEqual(SideDish.objects.count(), 0)

    def test_side_dish_ordering(self):
        """SideDishes are ordered by the order field."""
        sd3 = SideDish.objects.create(meal_plan=self.meal, custom_side="Dessert", order=3)
        sd1 = SideDish.objects.create(meal_plan=self.meal, custom_side="Starter", order=1)
        sd2 = SideDish.objects.create(meal_plan=self.meal, custom_side="Main Side", order=2)
        dishes = list(SideDish.objects.filter(meal_plan=self.meal))
        self.assertEqual(dishes[0].order, 1)
        self.assertEqual(dishes[1].order, 2)
        self.assertEqual(dishes[2].order, 3)

    def test_str_with_recipe(self):
        """str(side_dish) returns recipe title."""
        sd = SideDish.objects.create(
            meal_plan=self.meal, recipe=self.side_recipe, order=0
        )
        self.assertIn("Side Recipe", str(sd))

    def test_str_with_custom_side(self):
        """str(side_dish) returns custom_side string."""
        sd = SideDish.objects.create(
            meal_plan=self.meal, custom_side="Coleslaw", order=0
        )
        self.assertIn("Coleslaw", str(sd))


# =============================================================================
# View Tests
# =============================================================================


class PlannerHomeViewTests(TestCase):
    """Tests for PlannerHomeView (meal plan calendar)."""

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
            needs_review=False,
        )
        self.today = date.today()
        self.monday = self.today - timedelta(days=self.today.weekday())

    def test_unauthenticated_redirects_to_login(self):
        """Unauthenticated GET redirects to login."""
        response = self.client.get(reverse("meal_planner:planner"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_authenticated_returns_200(self):
        """Authenticated GET returns 200 with planner template."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("meal_planner:planner"))
        self.assertEqual(response.status_code, 200)

    def test_view_shows_only_own_household_meals(self):
        """Planner only shows meals belonging to the user's household."""
        other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Other Recipe",
            needs_review=False,
        )
        # Create meal for other household
        MealPlan.objects.create(
            household=self.other_household,
            meal_date=self.monday,
            meal_type=MealType.DINNER,
            recipe=other_recipe,
        )
        # Create meal for own household
        own_meal = MealPlan.objects.create(
            household=self.household,
            meal_date=self.monday,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )

        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("meal_planner:planner"))
        self.assertEqual(response.status_code, 200)
        context = response.context
        # Walk week_days and count meals
        total_meals = 0
        for day in context["week_days"]:
            total_meals += len(day["meals"])
        self.assertEqual(total_meals, 1)
        # Check the meal is the correct one (meal type key is lowercase)
        monday_str = self.monday.strftime("%Y-%m-%d")
        self.assertIn(
            "dinner", context["week_days"][0]["meals"]
        )

    def test_week_navigation_redirects_to_correct_week(self):
        """Navigating to next/previous week redirects to planner_week URL."""
        self.client.login(username="alice", password="pass1234")
        next_monday = self.monday + timedelta(weeks=1)
        year, week_num, _ = next_monday.isocalendar()
        response = self.client.get(
            reverse("meal_planner:planner_navigate"),
            {"current": str(self.monday), "offset": 1},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/{year}/{week_num}/", response.url)

    def test_week_navigation_prev_week(self):
        """Navigating backward by one week."""
        self.client.login(username="alice", password="pass1234")
        prev_monday = self.monday - timedelta(weeks=1)
        year, week_num, _ = prev_monday.isocalendar()
        response = self.client.get(
            reverse("meal_planner:planner_navigate"),
            {"current": str(self.monday), "offset": -1},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/{year}/{week_num}/", response.url)

    def test_planner_week_url_with_year_week_loads_correct_week(self):
        """PlannerHomeView at /planner/<year>/<week>/ loads the correct week."""
        self.client.login(username="alice", password="pass1234")
        year, week_num, _ = self.monday.isocalendar()
        response = self.client.get(
            reverse("meal_planner:planner_week", args=[year, week_num])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["start_date"], self.monday)
        self.assertEqual(response.context["end_date"], self.monday + timedelta(days=6))

    def test_json_week_meals_returns_only_own_meals(self):
        """json_week_meals API only returns meals for authenticated user's household."""
        other_recipe = Recipe.objects.create(
            household=self.other_household,
            title="Other Recipe",
            needs_review=False,
        )
        MealPlan.objects.create(
            household=self.other_household,
            meal_date=self.monday,
            meal_type=MealType.DINNER,
            recipe=other_recipe,
        )
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.monday,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )

        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("meal_planner:api_meals"),
            {
                "start": str(self.monday),
                "end": str(self.monday + timedelta(days=6)),
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["meals"]), 1)
        self.assertEqual(data["meals"][0]["recipe_title"], "Test Recipe")

    def test_planner_context_includes_meal_types(self):
        """PlannerHomeView context includes all meal types."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("meal_planner:planner"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("breakfast", response.context["meal_types"])
        self.assertIn("lunch", response.context["meal_types"])
        self.assertIn("dinner", response.context["meal_types"])
        self.assertIn("snack", response.context["meal_types"])

    def test_recipe_meal_title_links_to_detail_page_with_drag_disabled(self):
        """Regression: the planner meal card surfaces a direct link to
        ``recipes:recipe_detail`` from the actions row so users can read
        the full recipe without opening the modal preview. Earlier
        attempts to wire the *title* itself to the URL failed in the
        browser: descendants of a ``drag-and-drop`` element are
        themselves draggable, and even a 1-pixel pointer movement on
        the title suppressed its click. The action-row link with
        ``draggable="false"`` reliably receives a normal click."""
        import re
        self.client.login(username="alice", password="pass1234")
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.monday,
            meal_type=MealType.LUNCH,
            recipe=self.recipe,
        )
        response = self.client.get(reverse("meal_planner:planner"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        expected_href = reverse(
            "recipes:recipe_detail", args=[self.recipe.pk]
        )
        # The actions row carries a ``View`` anchor that points at the
        # recipe detail page and is ``draggable="false"`` so its parent
        # card's drag handler cannot suppress its click. It uses the
        # vp-btn-ghost class — small but unmistakable button shape —
        # sat inside a dashed-border divider so users don't miss it.
        pattern = (
            rf'<a\s+href="{re.escape(expected_href)}"\s+draggable="false"'
            rf'[^>]*class="vp-btn-ghost planner-meal-action"'
            rf'[^>]*>\s*View\s*</a>'
        )
        self.assertRegex(
            body,
            pattern,
            "Expected a View link in the planner actions row pointing "
            "at recipe_detail with draggable=\"false\".",
        )
        # The divider line is rendered above the action row.
        self.assertIn("border-top: 1px dashed var(--border-subtle)", body)
        # The recipe title is still rendered.
        self.assertIn("Test Recipe", body)


# =============================================================================
# Form Tests
# =============================================================================


class MealPlanFormTests(TestCase):
    """Tests for MealPlanForm validation."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )
        self.factory = RequestFactory()
        self.today = date.today()

    def _make_request(self, data=None):
        request = self.factory.post("/", data or {})
        request.user = self.user
        return request

    def test_form_valid_with_recipe(self):
        """Form is valid when recipe is provided."""
        form = MealPlanForm(
            data={
                "meal_date": str(self.today),
                "meal_type": MealType.DINNER,
                "recipe": self.recipe.pk,
            },
            request=self._make_request(),
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_valid_with_custom_meal(self):
        """Form is valid when custom_meal is provided."""
        form = MealPlanForm(
            data={
                "meal_date": str(self.today),
                "meal_type": MealType.LUNCH,
                "custom_meal": "Grilled Chicken",
            },
            request=self._make_request(),
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_invalid_when_neither_recipe_nor_custom_meal(self):
        """Form is invalid when both recipe and custom_meal are empty."""
        form = MealPlanForm(
            data={
                "meal_date": str(self.today),
                "meal_type": MealType.BREAKFAST,
            },
            request=self._make_request(),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_form_filters_recipes_to_household(self):
        """Recipe queryset is filtered to user's household."""
        other_household = Household.objects.create(name="Other")
        other_recipe = Recipe.objects.create(
            household=other_household,
            title="Other Recipe",
            needs_review=False,
        )
        form = MealPlanForm(
            data={
                "meal_date": str(self.today),
                "meal_type": MealType.DINNER,
                "recipe": self.recipe.pk,
            },
            request=self._make_request(),
        )
        # other_recipe should NOT be in the queryset
        self.assertIn(self.recipe, form.fields["recipe"].queryset)
        self.assertNotIn(other_recipe, form.fields["recipe"].queryset)

    def test_form_excludes_needs_review_recipes(self):
        """Recipes needing review are excluded from form queryset."""
        pending_recipe = Recipe.objects.create(
            household=self.household,
            title="Pending Recipe",
            needs_review=True,  # needs review — should be excluded
        )
        form = MealPlanForm(
            data={
                "meal_date": str(self.today),
                "meal_type": MealType.DINNER,
                "recipe": self.recipe.pk,
            },
            request=self._make_request(),
        )
        self.assertIn(self.recipe, form.fields["recipe"].queryset)
        self.assertNotIn(pending_recipe, form.fields["recipe"].queryset)


# =============================================================================
# AddMealView and EditMealView Tests
# =============================================================================


class AddMealViewTests(TestCase):
    """Tests for AddMealView (meal creation via form)."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )
        self.today = date.today()

    def test_add_meal_requires_login(self):
        """AddMealView unauthenticated GET redirects to login."""
        response = self.client.get(reverse("meal_planner:add_meal"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_add_meal_get_returns_form(self):
        """Authenticated GET returns 200 with form."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("meal_planner:add_meal"))
        self.assertEqual(response.status_code, 200)

    def test_add_meal_post_creates_mealplan(self):
        """Valid POST creates a MealPlan for the user's household."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:add_meal"),
            {
                "meal_date": str(self.today),
                "meal_type": MealType.DINNER,
                "recipe": self.recipe.pk,
            },
        )
        self.assertEqual(MealPlan.objects.count(), 1)
        meal = MealPlan.objects.first()
        self.assertEqual(meal.household, self.household)
        self.assertEqual(meal.recipe, self.recipe)
        self.assertEqual(meal.meal_type, MealType.DINNER)
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_add_meal_with_custom_meal(self):
        """POST with custom_meal creates a custom meal entry."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:add_meal"),
            {
                "meal_date": str(self.today),
                "meal_type": MealType.LUNCH,
                "custom_meal": "Leftover Pasta",
            },
        )
        self.assertEqual(MealPlan.objects.count(), 1)
        meal = MealPlan.objects.first()
        self.assertEqual(meal.custom_meal, "Leftover Pasta")
        self.assertIsNone(meal.recipe)

    def test_add_meal_prefills_from_query_params(self):
        """AddMealView pre-fills date/type/recipe from query string."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("meal_planner:add_meal"),
            {
                "date": str(self.today),
                "type": MealType.BREAKFAST,
                "recipe": self.recipe.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(str(form.initial.get("meal_date")), str(self.today))
        self.assertEqual(form.initial.get("meal_type"), MealType.BREAKFAST)
        self.assertEqual(form.initial.get("recipe"), self.recipe)


class EditMealViewTests(TestCase):
    """Tests for EditMealView (meal update via form)."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )
        self.meal = MealPlan.objects.create(
            household=self.household,
            meal_date=date.today(),
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )

    def test_edit_meal_get_returns_form(self):
        """Authenticated GET returns 200 with populated form."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("meal_planner:edit_meal", args=[self.meal.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_meal_post_updates_mealplan(self):
        """Valid POST updates the MealPlan."""
        self.client.login(username="alice", password="pass1234")
        new_date = date.today() + timedelta(days=1)
        response = self.client.post(
            reverse("meal_planner:edit_meal", args=[self.meal.pk]),
            {
                "meal_date": str(new_date),
                "meal_type": MealType.LUNCH,
                "recipe": self.recipe.pk,
            },
        )
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.meal_date, new_date)
        self.assertEqual(self.meal.meal_type, MealType.LUNCH)
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_edit_other_household_meal_returns_404(self):
        """Editing another household's meal returns 404."""
        other_household = Household.objects.create(name="Other")
        other_user = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="pass1234",
            household=other_household,
        )
        self.client.login(username="bob", password="pass1234")
        response = self.client.get(
            reverse("meal_planner:edit_meal", args=[self.meal.pk])
        )
        self.assertEqual(response.status_code, 404)


class DeleteMealViewTests(TestCase):
    """Tests for DeleteMealView."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )
        self.meal = MealPlan.objects.create(
            household=self.household,
            meal_date=date.today(),
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )

    def test_delete_meal_removes_mealplan(self):
        """POST deletes the MealPlan."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:delete_meal", args=[self.meal.pk])
        )
        self.assertEqual(MealPlan.objects.count(), 0)

    def test_delete_other_household_returns_404(self):
        """Deleting another household's meal returns 404."""
        other_household = Household.objects.create(name="Other")
        User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="pass1234",
            household=other_household,
        )
        self.client.login(username="bob", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:delete_meal", args=[self.meal.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(MealPlan.objects.count(), 1)


class RateMealViewTests(TestCase):
    """Tests for RateMealView (rating a meal plan entry)."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )
        self.meal = MealPlan.objects.create(
            household=self.household,
            meal_date=date.today(),
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )

    def test_rate_meal_with_valid_rating(self):
        """POST with rating 1-5 updates meal_rating."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:rate_meal", args=[self.meal.pk]),
            {"rating": "4"},
        )
        self.assertEqual(response.status_code, 200)
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.meal_rating, 4)

    def test_rate_meal_invalid_rating_returns_400(self):
        """POST with rating > 5 returns 400."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:rate_meal", args=[self.meal.pk]),
            {"rating": "6"},
        )
        self.assertEqual(response.status_code, 400)

    def test_rate_meal_zero_returns_400(self):
        """POST with rating < 1 returns 400."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:rate_meal", args=[self.meal.pk]),
            {"rating": "0"},
        )
        self.assertEqual(response.status_code, 400)

    def test_rate_other_household_returns_404(self):
        """Rating another household's meal returns 404."""
        other_household = Household.objects.create(name="Other")
        User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="pass1234",
            household=other_household,
        )
        self.client.login(username="bob", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:rate_meal", args=[self.meal.pk]),
            {"rating": "5"},
        )
        self.assertEqual(response.status_code, 404)


class MoveMealViewTests(TestCase):
    """Tests for MoveMealView (drag-and-drop meal moves)."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )
        self.meal = MealPlan.objects.create(
            household=self.household,
            meal_date=date.today(),
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )

    def test_move_meal_updates_date_and_type(self):
        """POST moves the meal to a different planner slot."""
        self.client.login(username="alice", password="pass1234")
        new_date = date.today() + timedelta(days=2)

        response = self.client.post(
            reverse("meal_planner:move_meal", args=[self.meal.pk]),
            {"meal_date": str(new_date), "meal_type": MealType.LUNCH},
        )

        self.assertEqual(response.status_code, 200)
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.meal_date, new_date)
        self.assertEqual(self.meal.meal_type, MealType.LUNCH)

    def test_move_meal_rejects_invalid_type(self):
        """POST with invalid meal type returns 400."""
        self.client.login(username="alice", password="pass1234")

        response = self.client.post(
            reverse("meal_planner:move_meal", args=[self.meal.pk]),
            {"meal_date": str(date.today()), "meal_type": "brunch"},
        )

        self.assertEqual(response.status_code, 400)

    def test_move_meal_rejects_conflicting_slot(self):
        """POST to an occupied slot returns conflict."""
        self.client.login(username="alice", password="pass1234")
        target_date = date.today() + timedelta(days=1)
        MealPlan.objects.create(
            household=self.household,
            meal_date=target_date,
            meal_type=MealType.DINNER,
            recipe=self.recipe,
        )

        response = self.client.post(
            reverse("meal_planner:move_meal", args=[self.meal.pk]),
            {"meal_date": str(target_date), "meal_type": MealType.DINNER},
        )

        self.assertEqual(response.status_code, 409)

    def test_move_other_household_meal_returns_404(self):
        """Moving another household's meal returns 404."""
        other_household = Household.objects.create(name="Other")
        User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="pass1234",
            household=other_household,
        )
        self.client.login(username="bob", password="pass1234")

        response = self.client.post(
            reverse("meal_planner:move_meal", args=[self.meal.pk]),
            {"meal_date": str(date.today()), "meal_type": MealType.LUNCH},
        )

        self.assertEqual(response.status_code, 404)


# =============================================================================
# Side Dish Tests (via AddMealView)
# =============================================================================


class AddMealViewSideDishesTests(TestCase):
    """Tests for side dish creation via AddMealView."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Main Dish",
            needs_review=False,
        )
        self.side_recipe = Recipe.objects.create(
            household=self.household,
            title="Side Dish Recipe",
            needs_review=False,
        )
        self.today = date.today()

    def test_add_meal_with_side_dish_custom(self):
        """Side dishes passed via POST data are created."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:add_meal"),
            {
                "meal_date": str(self.today),
                "meal_type": MealType.DINNER,
                "recipe": self.recipe.pk,
                "side_dishes-0-custom_side": "Mashed Potatoes",
                "side_dishes-0-order": "0",
            },
        )
        self.assertEqual(MealPlan.objects.count(), 1)
        meal = MealPlan.objects.first()
        self.assertEqual(meal.side_dishes.count(), 1)
        self.assertEqual(meal.side_dishes.first().custom_side, "Mashed Potatoes")

    def test_add_meal_with_side_dish_recipe(self):
        """Side dish linked to a recipe is created."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:add_meal"),
            {
                "meal_date": str(self.today),
                "meal_type": MealType.DINNER,
                "recipe": self.recipe.pk,
                f"side_dishes-0-recipe": str(self.side_recipe.pk),
                "side_dishes-0-order": "0",
            },
        )
        meal = MealPlan.objects.first()
        self.assertEqual(meal.side_dishes.count(), 1)
        self.assertEqual(meal.side_dishes.first().recipe, self.side_recipe)


# =============================================================================
# RecipeSelectView Tests
# =============================================================================


class RecipeSelectViewTests(TestCase):
    """Tests for RecipeSelectView API endpoint."""

    def setUp(self):
        self.household = Household.objects.create(name="Test Household")
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Available Recipe",
            needs_review=False,
        )
        self.pending_recipe = Recipe.objects.create(
            household=self.household,
            title="Pending Recipe",
            needs_review=True,
        )

    def test_recipe_select_excludes_needs_review(self):
        """RecipeSelectView excludes recipes needing review."""
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("meal_planner:api_recipe_select"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        titles = [r["title"] for r in data["recipes"]]
        self.assertIn("Available Recipe", titles)
        self.assertNotIn("Pending Recipe", titles)

    def test_recipe_select_requires_auth(self):
        """RecipeSelectView unauthenticated returns 302."""
        response = self.client.get(reverse("meal_planner:api_recipe_select"))
        self.assertEqual(response.status_code, 302)


# =============================================================================
# MealPreferences Tests
# =============================================================================


class MealPreferencesModelTests(TestCase):
    """Tests for MealPreferences model."""

    def setUp(self):
        self.household = Household.objects.create(name="Pref Test Household")

    def test_create_preferences_defaults(self):
        """MealPreferences creates with sensible defaults."""
        prefs = MealPreferences.objects.create(household=self.household)
        self.assertEqual(prefs.servings_per_meal, 2)
        self.assertEqual(prefs.cooking_effort, "moderate")
        self.assertEqual(prefs.cuisine_preferences, [])
        self.assertEqual(prefs.dietary_restrictions, [])
        self.assertEqual(prefs.excluded_ingredients, [])

    def test_preferences_one_to_one_household(self):
        """Each household has exactly one MealPreferences."""
        MealPreferences.objects.create(household=self.household)
        with self.assertRaises(IntegrityError):
            MealPreferences.objects.create(household=self.household)

    def test_preferences_str(self):
        """String representation includes household name."""
        prefs = MealPreferences.objects.create(household=self.household)
        self.assertIn(str(self.household), str(prefs))

    def test_preferences_with_cuisines_and_restrictions(self):
        """MealPreferences stores array fields correctly."""
        prefs = MealPreferences.objects.create(
            household=self.household,
            cuisine_preferences=["italian", "mexican"],
            dietary_restrictions=["vegetarian", "gluten-free"],
            cooking_effort=CookingEffort.QUICK,
            servings_per_meal=1,
            excluded_ingredients=["cilantro", "mushrooms"],
        )
        prefs.refresh_from_db()
        self.assertEqual(prefs.cuisine_preferences, ["italian", "mexican"])
        self.assertEqual(prefs.dietary_restrictions, ["vegetarian", "gluten-free"])
        self.assertEqual(prefs.cooking_effort, CookingEffort.QUICK)
        self.assertEqual(prefs.servings_per_meal, 1)
        self.assertEqual(prefs.excluded_ingredients, ["cilantro", "mushrooms"])


class MealPreferencesViewTests(TestCase):
    """Tests for MealPreferencesView."""

    def setUp(self):
        self.household = Household.objects.create(name="Pref View Household")
        self.user = User.objects.create_user(
            username="prefuser",
            email="prefuser@example.com",
            password="pass1234",
        )
        self.user.household = self.household
        self.user.save()

    def test_view_requires_login(self):
        """Unauthenticated users are redirected."""
        response = self.client.get(reverse("meal_planner:preferences"))
        self.assertEqual(response.status_code, 302)

    def test_view_creates_preferences_on_first_visit(self):
        """GET creates MealPreferences if none exist."""
        self.client.login(username="prefuser", password="pass1234")
        response = self.client.get(reverse("meal_planner:preferences"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            MealPreferences.objects.filter(household=self.household).exists()
        )

    def test_view_loads_existing_preferences(self):
        """GET loads existing MealPreferences."""
        MealPreferences.objects.create(
            household=self.household,
            cuisine_preferences=["italian"],
            cooking_effort="elaborate",
            servings_per_meal=4,
        )
        self.client.login(username="prefuser", password="pass1234")
        response = self.client.get(reverse("meal_planner:preferences"))
        self.assertEqual(response.status_code, 200)

    def test_view_saves_new_preferences(self):
        """POST saves preferences and redirects to planner."""
        self.client.login(username="prefuser", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:preferences"),
            {
                "cuisine_preferences": ["italian", "mexican"],
                "dietary_restrictions": ["vegetarian"],
                "cooking_effort": "quick",
                "servings_per_meal": 2,
                "excluded_ingredients": "cilantro, mushrooms",
            },
        )
        self.assertRedirects(response, reverse("meal_planner:planner"))
        prefs = MealPreferences.objects.get(household=self.household)
        self.assertEqual(prefs.cuisine_preferences, ["italian", "mexican"])
        self.assertEqual(prefs.dietary_restrictions, ["vegetarian"])
        self.assertEqual(prefs.cooking_effort, "quick")
        self.assertEqual(prefs.excluded_ingredients, ["cilantro", "mushrooms"])

    def test_view_defaults_to_two_servings(self):
        """Unspecified servings_per_meal defaults to 2."""
        self.client.login(username="prefuser", password="pass1234")
        self.client.post(
            reverse("meal_planner:preferences"),
            {
                "cuisine_preferences": [],
                "dietary_restrictions": [],
                "cooking_effort": "moderate",
                "servings_per_meal": 2,
                "excluded_ingredients": "",
            },
        )
        prefs = MealPreferences.objects.get(household=self.household)
        self.assertEqual(prefs.servings_per_meal, 2)


class MealPreferencesFormTests(TestCase):
    """Tests for MealPreferencesForm."""

    def setUp(self):
        self.household = Household.objects.create(name="Form Test Household")

    def test_form_empty_excluded_ingredients(self):
        """Empty excluded_ingredients returns empty list."""
        from meal_planner_app.forms import MealPreferencesForm

        data = {
            "cuisine_preferences": [],
            "dietary_restrictions": [],
            "cooking_effort": "moderate",
            "servings_per_meal": 2,
            "excluded_ingredients": "",
        }
        form = MealPreferencesForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["excluded_ingredients"], [])

    def test_form_parses_excluded_ingredients(self):
        """Comma-separated excluded_ingredients parsed correctly."""
        from meal_planner_app.forms import MealPreferencesForm

        data = {
            "cuisine_preferences": [],
            "dietary_restrictions": [],
            "cooking_effort": "moderate",
            "servings_per_meal": 2,
            "excluded_ingredients": "cilantro, mushrooms,  anchovies ",
        }
        form = MealPreferencesForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data["excluded_ingredients"],
            ["cilantro", "mushrooms", "anchovies"],
        )

    def test_form_requires_cooking_effort(self):
        """cooking_effort is required."""
        from meal_planner_app.forms import MealPreferencesForm

        data = {
            "cuisine_preferences": [],
            "dietary_restrictions": [],
            "cooking_effort": "",
            "servings_per_meal": 2,
            "excluded_ingredients": "",
        }
        form = MealPreferencesForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("cooking_effort", form.errors)

    def test_form_servings_within_range(self):
        """servings_per_meal must be between 1 and 8."""
        from meal_planner_app.forms import MealPreferencesForm

        data = {
            "cuisine_preferences": [],
            "dietary_restrictions": [],
            "cooking_effort": "moderate",
            "servings_per_meal": 0,
            "excluded_ingredients": "",
        }
        form = MealPreferencesForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("servings_per_meal", form.errors)

        data["servings_per_meal"] = 9
        form = MealPreferencesForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("servings_per_meal", form.errors)


# =============================================================================
# AI Service Tests
# =============================================================================


class AIServiceTests(TestCase):
    """Tests for AIService prompt construction, retry logic, and error handling."""

    def setUp(self):
        self.household = Household.objects.create(name="AI Test Household")
        self.start_date = date(2026, 6, 1)
        self.end_date = date(2026, 6, 7)
        self.prefs = MealPreferences.objects.create(
            household=self.household,
            cuisine_preferences=["italian", "mexican"],
            dietary_restrictions=["vegetarian"],
            cooking_effort="quick",
            servings_per_meal=2,
            excluded_ingredients=["cilantro"],
        )
        self.valid_ai_response = [
            {
                "date": "2026-06-01",
                "meals": [
                    {
                        "meal_type": "breakfast",
                        "title": "Veggie Scramble",
                        "description": "Quick veggie eggs",
                        "cook_time_minutes": 15,
                        "ingredients": ["eggs", "bell peppers"],
                    },
                    {
                        "meal_type": "dinner",
                        "title": "Pasta Primavera",
                        "description": "Light pasta with veggies",
                        "cook_time_minutes": 30,
                        "ingredients": ["pasta", "zucchini", "tomatoes"],
                    },
                ],
            },
        ]

    @patch("httpx.Client.post")
    def test_prompt_includes_preferences(self, mock_post):
        """The prompt sent to AI includes user's cuisine and dietary preferences."""
        from meal_planner_app.services.ai_service import AIService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json_dumps(self.valid_ai_response)}}]
        }
        mock_post.return_value = mock_response
        mock_response.raise_for_status = lambda: None

        service = AIService()
        result = service.generate_meal_plan(
            household=self.household,
            start_date=self.start_date,
            end_date=self.end_date,
            preferences=self.prefs,
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.meals), 1)
        self.assertEqual(result.meals[0]["date"], "2026-06-01")
        self.assertEqual(len(result.meals[0]["meals"]), 2)

        # Verify the prompt included preference info
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        user_msg = payload["messages"][1]["content"]
        self.assertIn("italian", user_msg)
        self.assertIn("vegetarian", user_msg)
        self.assertIn("Quick", user_msg)  # cooking effort
        self.assertIn("cilantro", user_msg)  # excluded

    @patch("httpx.Client.post")
    def test_retry_on_transient_error(self, mock_post):
        """AIService retries on HTTP 503, succeeds on third attempt."""
        from meal_planner_app.services.ai_service import AIService

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                resp = MagicMock()
                resp.status_code = 503
                resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Server Error", request=MagicMock(), response=resp
                )
                return resp
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": json_dumps(self.valid_ai_response)}}]
            }
            resp.raise_for_status = lambda: None
            return resp

        mock_post.side_effect = side_effect

        service = AIService()
        result = service.generate_meal_plan(
            household=self.household,
            start_date=self.start_date,
            end_date=self.end_date,
            preferences=self.prefs,
        )

        self.assertTrue(result.success)
        self.assertEqual(call_count, 3)

    @patch("httpx.Client.post")
    def test_fails_after_max_retries(self, mock_post):
        """AIService returns error when all retries are exhausted."""
        from meal_planner_app.services.ai_service import AIService

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        service = AIService()
        result = service.generate_meal_plan(
            household=self.household,
            start_date=self.start_date,
            end_date=self.end_date,
            preferences=self.prefs,
        )

        self.assertFalse(result.success)
        self.assertIn("3 attempts", result.error.lower())

    @patch("httpx.Client.post")
    def test_client_error_not_retried(self, mock_post):
        """AIService does not retry on 4xx client errors."""
        from meal_planner_app.services.ai_service import AIService

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        service = AIService()
        result = service.generate_meal_plan(
            household=self.household,
            start_date=self.start_date,
            end_date=self.end_date,
            preferences=self.prefs,
        )

        self.assertFalse(result.success)
        self.assertIn("400", result.error)

    @patch("httpx.Client.post")
    def test_generates_without_preferences(self, mock_post):
        """AIService works when no MealPreferences exist yet (falls back to defaults)."""
        from meal_planner_app.services.ai_service import AIService

        # Delete the preferences created in setUp
        self.prefs.delete()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json_dumps(self.valid_ai_response)}}]
        }
        mock_post.return_value = mock_response
        mock_response.raise_for_status = lambda: None

        service = AIService()
        result = service.generate_meal_plan(
            household=self.household,
            start_date=self.start_date,
            end_date=self.end_date,
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.meals), 1)

    @patch("httpx.Client.post")
    def test_truncated_reasoning_retries_with_larger_budget(self, mock_post):
        """First response empties the budget mid-reasoning (finish_reason=length,
        empty content). The retry loop doubles max_tokens and succeeds on a
        second attempt that returns valid JSON."""
        from meal_planner_app.services.ai_service import AIService

        call_count = 0
        budgets = []

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            budgets.append(kwargs["json"]["max_tokens"])
            if call_count == 1:
                # First call: reasoning model ran out of tokens before content
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": "", "reasoning_content": "thinking..."},
                        }
                    ]
                }
                resp.raise_for_status = lambda: None
                return resp
            # Second call after retry: model has budget and emits JSON
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": json_dumps(self.valid_ai_response)}}]
            }
            resp.raise_for_status = lambda: None
            return resp

        mock_post.side_effect = side_effect

        service = AIService()
        result = service.generate_meal_plan(
            household=self.household,
            start_date=self.start_date,
            end_date=self.end_date,
            preferences=self.prefs,
        )

        self.assertTrue(result.success, msg=result.error)
        self.assertEqual(call_count, 2)
        # First attempt uses the default; retry should have grown the budget
        self.assertEqual(budgets[0], 8192)
        self.assertEqual(budgets[1], 16384)

    @patch("httpx.Client.post")
    def test_empty_content_without_length_is_fatal(self, mock_post):
        """If content is empty for any reason other than finish_reason=length,
        the loop must NOT retry with a larger budget — that would just waste
        tokens on an empty response."""
        from meal_planner_app.services.ai_service import AIService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": ""},
                }
            ]
        }
        mock_post.return_value = mock_response
        mock_response.raise_for_status = lambda: None

        service = AIService()
        result = service.generate_meal_plan(
            household=self.household,
            start_date=self.start_date,
            end_date=self.end_date,
            preferences=self.prefs,
        )

        self.assertFalse(result.success)
        self.assertIn("Failed to parse AI response", result.error)
        # Only one HTTP attempt — no retry on non-truncation empty content.
        self.assertEqual(mock_post.call_count, 1)

    @patch("httpx.Client.post")
    def test_truncated_past_ceiling_returns_actionable_error(self, mock_post):
        """Even after max_retries and the 16384 ceiling, an empty reasoning
        response must surface a useful error that names finish_reason and the
        budget hit, so the user (and operator) can act on it."""
        from meal_planner_app.services.ai_service import AIService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": ""},
                }
            ]
        }
        mock_post.return_value = mock_response
        mock_response.raise_for_status = lambda: None

        service = AIService()
        result = service.generate_meal_plan(
            household=self.household,
            start_date=self.start_date,
            end_date=self.end_date,
            preferences=self.prefs,
        )

        self.assertFalse(result.success)
        self.assertIn("finish_reason=length", result.error)
        self.assertIn("max_tokens=16384", result.error)
        # Two attempts: 8192 → 16384. We don't re-shoot at the ceiling — the
        # same params produced the same truncation, so give up and report.
        self.assertEqual(mock_post.call_count, 2)


# =============================================================================
# AI Settings Tests
# =============================================================================


class AISettingsTests(TestCase):
    """Storage and resolution of per-household AI model preferences."""

    def setUp(self):
        self.household = Household.objects.create(name="AI Settings Household")

    def test_get_or_create_returns_row(self):
        from meal_planner_app.models import AISettings

        first, created_first = AISettings.objects.get_or_create(
            household=self.household
        )
        second, created_second = AISettings.objects.get_or_create(
            household=self.household
        )
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)

    def test_set_model_persists_with_timestamp(self):
        from meal_planner_app.models import AISettings

        settings_row, _ = AISettings.objects.get_or_create(
            household=self.household
        )
        settings_row.set_model(
            "meal_plan_generation",
            "anthropic/claude-sonnet-4",
            "Claude Sonnet 4",
        )
        settings_row.refresh_from_db()
        binding = settings_row.get_model("meal_plan_generation")
        self.assertIsNotNone(binding)
        self.assertEqual(binding["model_id"], "anthropic/claude-sonnet-4")
        self.assertEqual(binding["label"], "Claude Sonnet 4")
        self.assertIn("updated_at", binding)

    def test_get_model_returns_none_for_unspecified_feature(self):
        from meal_planner_app.models import AISettings

        settings_row, _ = AISettings.objects.get_or_create(
            household=self.household
        )
        self.assertIsNone(settings_row.get_model("nonexistent"))

    def test_resolve_model_uses_override_first(self):
        from meal_planner_app.models import AISettings
        from meal_planner_app.services.ai_settings import resolve_model

        AISettings.objects.get_or_create(household=self.household)
        # Even if the household saved a binding, an explicit override wins.
        settings_row = AISettings.objects.get(household=self.household)
        settings_row.set_model("meal_plan_generation", "saved/model", "Saved")
        self.assertEqual(
            resolve_model(self.household, "meal_plan_generation", override="override/model"),
            "override/model",
        )

    def test_resolve_model_uses_household_binding(self):
        from meal_planner_app.models import AISettings
        from meal_planner_app.services.ai_settings import resolve_model

        settings_row, _ = AISettings.objects.get_or_create(
            household=self.household
        )
        settings_row.set_model("recipe_import_text", "saved/recipe", "Saved Recipe")
        self.assertEqual(
            resolve_model(self.household, "recipe_import_text"),
            "saved/recipe",
        )

    def test_resolve_model_falls_back_to_default(self):
        from meal_planner_app.services.ai_settings import (
            FEATURE_KEYS, resolve_model,
        )

        # No AISettings row + no override → baked-in default.
        self.assertEqual(
            resolve_model(self.household, "meal_plan_generation"),
            FEATURE_KEYS["meal_plan_generation"]["default_model"],
        )

    def test_resolve_model_raises_for_unknown_feature(self):
        from meal_planner_app.services.ai_settings import resolve_model

        with self.assertRaises(KeyError):
            resolve_model(self.household, "nope/not/a/feature")

    def test_resolve_openrouter_api_key_prefers_household_override(self):
        from meal_planner_app.services.ai_settings import resolve_openrouter_api_key

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            settings_row, _ = __import__(
                "meal_planner_app.models", fromlist=["AISettings"]
            ).AISettings.objects.get_or_create(household=self.household)
            self.assertEqual(resolve_openrouter_api_key(self.household), "env-key")

            settings_row.openrouter_api_key_override = "house-key"
            settings_row.save()
            self.assertEqual(resolve_openrouter_api_key(self.household), "house-key")

            self.assertEqual(resolve_openrouter_api_key(None), "env-key")


class OpenRouterCatalogTests(TestCase):
    """Process-wide cache of the OpenRouter /v1/models catalog."""

    def setUp(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        OpenRouterCatalog.reset()

    def tearDown(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        OpenRouterCatalog.reset()

    def _sample_catalog(self):
        return {
            "data": [
                {
                    "id": "anthropic/claude-sonnet-4",
                    "name": "Claude Sonnet 4",
                    "description": "Paid, very smart",
                    "context_length": 200000,
                    "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                    "architecture": {
                        "modality": "text+image->text",
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"],
                    },
                },
                {
                    "id": "google/gemini-2.0-flash-001",
                    "name": "Gemini 2.0 Flash (Paid)",
                    "description": "Paid, fast",
                    "context_length": 1000000,
                    "pricing": {"prompt": "0.0000001", "completion": "0.0000004"},
                    "architecture": {
                        "modality": "text+image->text",
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"],
                    },
                },
                {
                    "id": "qwen/qwen3-coder:free",
                    "name": "Qwen3 Coder (Free)",
                    "description": "Free text-only",
                    "context_length": 32768,
                    "pricing": {"prompt": "0", "completion": "0"},
                    "architecture": {
                        "modality": "text->text",
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                    },
                },
                {
                    "id": "deepseek/deepseek-chat-v3:free",
                    "name": "DeepSeek Chat v3 (Free)",
                    "description": "Free",
                    "context_length": 64000,
                    "pricing": {"prompt": "0", "completion": "0"},
                    "architecture": {
                        "modality": "text->text",
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                    },
                },
            ]
        }

    def _stub_client(self, payload):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = payload
        response.raise_for_status = lambda: None
        client = MagicMock()
        client.__enter__ = lambda self_: client
        client.__exit__ = lambda self_, *args: False
        client.get = MagicMock(return_value=response)
        return client

    def test_fetch_parses_and_sorts_free_first(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        client = self._stub_client(self._sample_catalog())
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client):
            models = OpenRouterCatalog.fetch(force_refresh=True)
        # Free models come first; paid after — alphabetical within each group.
        ids = [m.id for m in models]
        self.assertEqual(
            ids,
            [
                "deepseek/deepseek-chat-v3:free",
                "qwen/qwen3-coder:free",
                "anthropic/claude-sonnet-4",
                "google/gemini-2.0-flash-001",
            ],
        )
        self.assertEqual(models[0].is_free, True)
        self.assertEqual(models[-1].is_free, False)

    def test_fetch_caches_and_only_hits_upstream_once(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        client = self._stub_client(self._sample_catalog())
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client) as constructor:
            OpenRouterCatalog.fetch(force_refresh=True)
            OpenRouterCatalog.fetch()
            OpenRouterCatalog.fetch()
            # Constructor run count == 1 because the catalog is cached in process.
            self.assertEqual(constructor.call_count, 1)

    def test_force_refresh_busts_cache(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        client = self._stub_client(self._sample_catalog())
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client) as constructor:
            OpenRouterCatalog.fetch()
            OpenRouterCatalog.fetch(force_refresh=True)
            self.assertEqual(constructor.call_count, 2)

    def test_vision_feature_filters_text_only_models(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        client = self._stub_client(self._sample_catalog())
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client):
            vision = OpenRouterCatalog.for_feature("recipe_import_image")
        ids = [m.id for m in vision]
        self.assertNotIn("qwen/qwen3-coder:free", ids)
        self.assertNotIn("deepseek/deepseek-chat-v3:free", ids)
        self.assertIn("anthropic/claude-sonnet-4", ids)
        self.assertIn("google/gemini-2.0-flash-001", ids)

    def test_text_feature_returns_everything(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        client = self._stub_client(self._sample_catalog())
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client):
            all_models = OpenRouterCatalog.for_feature("meal_plan_generation")
        self.assertEqual(len(all_models), 4)

    def test_fetch_serves_last_good_value_when_upstream_blips(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        good = self._sample_catalog()
        good_response = MagicMock()
        good_response.json.return_value = good
        good_response.raise_for_status = lambda: None

        bad_response = MagicMock()
        bad_response.raise_for_status.side_effect = httpx.HTTPError("upstream down")

        success_client = MagicMock()
        success_client.__enter__ = lambda self_: success_client
        success_client.__exit__ = lambda self_, *args: False
        success_client.get = MagicMock(return_value=good_response)

        failing_client = MagicMock()
        failing_client.__enter__ = lambda self_: failing_client
        failing_client.__exit__ = lambda self_, *args: False
        failing_client.get = MagicMock(return_value=bad_response)

        with patch(
            "meal_planner_app.services.ai_settings.httpx.Client",
            side_effect=[success_client, failing_client],
        ):
            OpenRouterCatalog.fetch(force_refresh=True)
            # Second fetch swallows the upstream error and serves the cache.
            models = OpenRouterCatalog.fetch()
        self.assertEqual(len(models), 4)

    def test_for_feature_raises_for_unknown_key(self):
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        with self.assertRaises(KeyError):
            OpenRouterCatalog.for_feature("not-a-feature")


class AIModelsSettingsViewTests(TestCase):
    """GET / POST /tools/ai-models/ behavior."""

    def setUp(self):
        self.household = Household.objects.create(name="AI Settings View HH")
        self.user = User.objects.create_user(
            username="aiuser",
            email="ai@example.com",
            password="pass1234",
            household=self.household,
        )
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        OpenRouterCatalog.reset()
        self.url = reverse("meal_planner:ai_models_settings")

    def _stub_catalog(self):
        return {
            "data": [
                {
                    "id": "anthropic/claude-sonnet-4",
                    "name": "Claude Sonnet 4",
                    "description": "Paid",
                    "context_length": 200000,
                    "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                    "architecture": {
                        "modality": "text+image->text",
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"],
                    },
                },
                {
                    "id": "qwen/qwen3-coder:free",
                    "name": "Qwen3 Coder (Free)",
                    "description": "Free text-only",
                    "context_length": 32768,
                    "pricing": {"prompt": "0", "completion": "0"},
                    "architecture": {
                        "modality": "text->text",
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                    },
                },
            ]
        }

    def _stub_client(self, payload):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = payload
        response.raise_for_status = lambda: None
        client = MagicMock()
        client.__enter__ = lambda self_: client
        client.__exit__ = lambda self_, *args: False
        client.get = MagicMock(return_value=response)
        return client

    def test_get_requires_auth(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_renders_with_features_and_options(self):
        self.client.login(username="aiuser", password="pass1234")
        client = self._stub_client(self._stub_catalog())
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "settings/ai_models.html")
        features = response.context["features"]
        # One feature block per FEATURE_KEYS entry.
        from meal_planner_app.services.ai_settings import FEATURE_KEYS

        self.assertEqual({f["key"] for f in features}, set(FEATURE_KEYS.keys()))
        # Recipe photo feature should NOT list the text-only free Qwen model.
        photo_block = next(f for f in features if f["key"] == "recipe_import_image")
        photo_ids = [m.id for m in photo_block["options"]]
        self.assertNotIn("qwen/qwen3-coder:free", photo_ids)
        self.assertIn("anthropic/claude-sonnet-4", photo_ids)

    def test_post_persists_model_for_each_feature(self):
        self.client.login(username="aiuser", password="pass1234")
        client = self._stub_client(self._stub_catalog())
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client):
            response = self.client.post(
                self.url,
                data={
                    "model_meal_plan_generation": "anthropic/claude-sonnet-4",
                    "model_recipe_import_text": "qwen/qwen3-coder:free",
                    "model_recipe_import_image": "anthropic/claude-sonnet-4",
                    "model_receipt_barcode": "anthropic/claude-sonnet-4",
                    "openrouter_api_key_override": "house-key-1234",
                },
            )
        self.assertEqual(response.status_code, 302)
        from meal_planner_app.models import AISettings

        settings_row = AISettings.objects.get(household=self.household)
        for key in (
            "meal_plan_generation",
            "recipe_import_text",
            "recipe_import_image",
            "receipt_barcode",
        ):
            binding = settings_row.get_model(key)
            self.assertIsNotNone(binding, msg=key)
        self.assertEqual(
            settings_row.get_model("recipe_import_text")["model_id"],
            "qwen/qwen3-coder:free",
        )
        self.assertEqual(settings_row.openrouter_api_key_override, "house-key-1234")

    def test_post_rejects_text_only_model_for_vision_feature(self):
        self.client.login(username="aiuser", password="pass1234")
        client = self._stub_client(self._stub_catalog())
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client):
            response = self.client.post(
                self.url,
                data={
                    "model_meal_plan_generation": "",
                    "model_recipe_import_text": "",
                    # Vision feature submitted with a text-only model — should be refused.
                    "model_recipe_import_image": "qwen/qwen3-coder:free",
                    "model_receipt_barcode": "",
                    "openrouter_api_key_override": "",
                },
            )
        self.assertEqual(response.status_code, 302)
        from meal_planner_app.models import AISettings

        settings_row = AISettings.objects.get(household=self.household)
        # Vision feature kept unset because the chosen model can't read images.
        self.assertIsNone(settings_row.get_model("recipe_import_image"))

    def test_post_clears_binding_when_empty_string(self):
        self.client.login(username="aiuser", password="pass1234")
        client = self._stub_client(self._stub_catalog())
        # Pre-seed a binding.
        from meal_planner_app.models import AISettings
        from meal_planner_app.services.ai_settings import OpenRouterCatalog

        settings_row, _ = AISettings.objects.get_or_create(household=self.household)
        settings_row.set_model("meal_plan_generation", "anthropic/claude-sonnet-4", "Claude")
        with patch("meal_planner_app.services.ai_settings.httpx.Client", return_value=client):
            self.client.post(
                self.url,
                data={
                    "model_meal_plan_generation": "",
                    "model_recipe_import_text": "",
                    "model_recipe_import_image": "",
                    "model_receipt_barcode": "",
                    "openrouter_api_key_override": "",
                },
            )
        settings_row.refresh_from_db()
        self.assertIsNone(settings_row.get_model("meal_plan_generation"))

    def test_get_refresh_busts_catalog_cache(self):
        self.client.login(username="aiuser", password="pass1234")
        client = self._stub_client(self._stub_catalog())
        with patch(
            "meal_planner_app.services.ai_settings.httpx.Client",
            return_value=client,
        ) as constructor:
            self.client.get(self.url)
            self.client.get(self.url + "?refresh=1")
        # First load fetches, second load with refresh=1 fetches again.
        self.assertEqual(constructor.call_count, 2)

    def test_get_renders_with_usda_key_input(self):
        from meal_planner_app.models import AISettings

        self.client.login(username="aiuser", password="pass1234")
        settings_row, _ = AISettings.objects.get_or_create(household=self.household)
        settings_row.usda_fdc_api_key_override = "FDC-12345"
        settings_row.save()
        with patch(
            "meal_planner_app.services.ai_settings.httpx.Client",
            return_value=self._stub_client(self._stub_catalog()),
        ):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["override_usda_api_key"], "FDC-12345"
        )
        self.assertContains(response, 'name="usda_fdc_api_key_override"')
        self.assertContains(response, 'value="FDC-12345"')

    def test_post_persists_usda_key_override(self):
        from meal_planner_app.models import AISettings

        self.client.login(username="aiuser", password="pass1234")
        with patch(
            "meal_planner_app.services.ai_settings.httpx.Client",
            return_value=self._stub_client(self._stub_catalog()),
        ):
            response = self.client.post(
                self.url,
                {
                    "model_meal_plan_generation": "",
                    "model_recipe_import_text": "",
                    "model_recipe_import_image": "",
                    "model_receipt_barcode": "",
                    "openrouter_api_key_override": "",
                    "usda_fdc_api_key_override": "FDC-SECRET-KEY",
                },
            )
        self.assertEqual(response.status_code, 302)
        settings_row = AISettings.objects.get(household=self.household)
        self.assertEqual(settings_row.usda_fdc_api_key_override, "FDC-SECRET-KEY")

    def test_post_usda_blank_clears_override(self):
        from meal_planner_app.models import AISettings

        self.client.login(username="aiuser", password="pass1234")
        settings_row, _ = AISettings.objects.get_or_create(household=self.household)
        settings_row.usda_fdc_api_key_override = "FDC-12345"
        settings_row.save()
        with patch(
            "meal_planner_app.services.ai_settings.httpx.Client",
            return_value=self._stub_client(self._stub_catalog()),
        ):
            response = self.client.post(
                self.url,
                {
                    "model_meal_plan_generation": "",
                    "model_recipe_import_text": "",
                    "model_recipe_import_image": "",
                    "model_receipt_barcode": "",
                    "openrouter_api_key_override": "",
                    "usda_fdc_api_key_override": "",
                },
            )
        self.assertEqual(response.status_code, 302)
        settings_row.refresh_from_db()
        self.assertEqual(settings_row.usda_fdc_api_key_override, "")


class AIServiceUsesPerHouseholdSettingsTests(TestCase):
    """The meal-plan service must honor the saved binding for the household."""

    def setUp(self):
        self.household = Household.objects.create(name="Resolved Plan HH")
        self.prefs = MealPreferences.objects.create(
            household=self.household,
            cuisine_preferences=["italian"],
            dietary_restrictions=[],
            cooking_effort="moderate",
            servings_per_meal=2,
        )
        self.valid_plan = [
            {
                "date": "2026-06-01",
                "meals": [
                    {
                        "meal_type": "dinner",
                        "title": "Pasta",
                        "description": "Quick pasta",
                        "cook_time_minutes": 20,
                        "ingredients": ["pasta"],
                    },
                ],
            }
        ]
        self._plan_json = json_dumps(self.valid_plan)

    def _make_fake_post(self, captured: dict):
        """Build a fake httpx.Client.post replacement that captures the call."""
        outer_json = self._plan_json  # local alias — never touch self inside

        def fake_post(self, url, json=None, headers=None, **_kwargs):
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers or {}
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": outer_json}}]
            }
            resp.raise_for_status = lambda: None
            return resp

        return fake_post

    def test_make_api_call_sends_saved_model_and_bearer_token(self):
        """When the household saved a binding, _make_api_call must POST
        that model id and use the API key (env or per-household)."""
        from meal_planner_app.models import AISettings
        from meal_planner_app.services.ai_service import AIService

        settings_row, _ = AISettings.objects.get_or_create(
            household=self.household
        )
        settings_row.set_model("meal_plan_generation", "saved/model", "Saved")

        captured: dict = {}
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            with patch("httpx.Client.post", new=self._make_fake_post(captured)):
                AIService(
                    household=self.household,
                    feature="meal_plan_generation",
                ).generate_meal_plan(
                    household=self.household,
                    start_date=date(2026, 6, 1),
                    end_date=date(2026, 6, 7),
                    preferences=self.prefs,
                )

        self.assertEqual(captured["payload"]["model"], "saved/model")
        self.assertEqual(
            captured["headers"].get("Authorization"), "Bearer test-key"
        )

    def test_make_api_call_uses_override_over_saved_binding(self):
        from meal_planner_app.models import AISettings
        from meal_planner_app.services.ai_service import AIService

        settings_row, _ = AISettings.objects.get_or_create(
            household=self.household
        )
        settings_row.set_model("meal_plan_generation", "saved/model", "Saved")

        captured: dict = {}
        with patch("httpx.Client.post", new=self._make_fake_post(captured)):
            AIService(
                household=self.household,
                feature="meal_plan_generation",
                model_override="override/model",
            ).generate_meal_plan(
                household=self.household,
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 7),
                preferences=self.prefs,
            )
        self.assertEqual(captured["payload"]["model"], "override/model")

    def test_make_api_call_uses_default_when_no_binding(self):
        from meal_planner_app.services.ai_service import AIService
        from meal_planner_app.services.ai_settings import FEATURE_KEYS

        captured: dict = {}
        with patch("httpx.Client.post", new=self._make_fake_post(captured)):
            # No AISettings row exists for self.household at this point.
            AIService(
                household=self.household,
                feature="meal_plan_generation",
            ).generate_meal_plan(
                household=self.household,
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 7),
                preferences=self.prefs,
            )
        self.assertEqual(
            captured["payload"]["model"],
            FEATURE_KEYS["meal_plan_generation"]["default_model"],
        )

    def test_per_household_api_key_override_beats_env(self):
        from meal_planner_app.models import AISettings
        from meal_planner_app.services.ai_service import AIService

        settings_row, _ = AISettings.objects.get_or_create(
            household=self.household
        )
        settings_row.openrouter_api_key_override = "house-key"
        settings_row.save()

        captured: dict = {}
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            with patch("httpx.Client.post", new=self._make_fake_post(captured)):
                AIService(
                    household=self.household,
                    feature="meal_plan_generation",
                ).generate_meal_plan(
                    household=self.household,
                    start_date=date(2026, 6, 1),
                    end_date=date(2026, 6, 7),
                    preferences=self.prefs,
                )
        self.assertEqual(
            captured["headers"].get("Authorization"), "Bearer house-key"
        )


# =============================================================================
# Response Parser Tests
# =============================================================================


class ResponseParserTests(TestCase):
    """Tests for the AI response parser."""

    def test_parse_valid_json(self):
        """Parse a valid JSON array of daily meals."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        response = [
            {
                "date": "2026-06-01",
                "meals": [
                    {
                        "meal_type": "breakfast",
                        "title": "Oatmeal",
                        "description": "Warm oats",
                        "cook_time_minutes": 10,
                        "ingredients": ["oats", "milk"],
                    },
                ],
            },
        ]
        result = parse_weekly_plan(response)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2026-06-01")
        self.assertEqual(result[0]["meals"][0]["title"], "Oatmeal")

    def test_parse_nested_in_dict(self):
        """Parse response wrapped in a 'days' key."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        response = {
            "days": [
                {
                    "date": "2026-06-01",
                    "meals": [
                        {
                            "meal_type": "lunch",
                            "title": "Salad",
                            "description": "Green salad",
                            "cook_time_minutes": 15,
                            "ingredients": ["lettuce", "tomato"],
                        },
                    ],
                },
            ],
        }
        result = parse_weekly_plan(response)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["meals"][0]["title"], "Salad")

    def test_parse_empty_list_raises(self):
        """Empty array raises ValueError."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        with self.assertRaises(ValueError):
            parse_weekly_plan([])

    def test_parse_non_list_raises(self):
        """Non-list response raises ValueError."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        with self.assertRaises(ValueError):
            parse_weekly_plan({"not": "a list"})

    def test_parse_missing_date_skips_day(self):
        """Day entry without a date is skipped."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        response = [
            {"meals": [{"meal_type": "dinner", "title": "Pizza"}]},
            {
                "date": "2026-06-02",
                "meals": [{"meal_type": "dinner", "title": "Pasta"}],
            },
        ]
        result = parse_weekly_plan(response)
        self.assertEqual(len(result), 1)

    def test_parse_invalid_date_format_skips_day(self):
        """Day entry with bad date format is skipped."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        response = [
            {
                "date": "not-a-date",
                "meals": [{"meal_type": "breakfast", "title": "Eggs"}],
            },
        ]
        with self.assertRaises(ValueError):
            parse_weekly_plan(response)

    def test_parse_missing_title_skips_meal(self):
        """Meal entry without a title is skipped within a day."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        response = [
            {
                "date": "2026-06-01",
                "meals": [
                    {},
                    {
                        "meal_type": "dinner",
                        "title": "Tacos",
                        "cook_time_minutes": 25,
                    },
                ],
            },
        ]
        result = parse_weekly_plan(response)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["meals"]), 1)
        self.assertEqual(result[0]["meals"][0]["title"], "Tacos")

    def test_parse_cook_time_defaults(self):
        """Missing or invalid cook_time defaults to 30."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        response = [
            {
                "date": "2026-06-01",
                "meals": [
                    {
                        "meal_type": "breakfast",
                        "title": "Toast",
                        "cook_time_minutes": "invalid",
                    },
                    {
                        "meal_type": "lunch",
                        "title": "Soup",
                    },
                ],
            },
        ]
        result = parse_weekly_plan(response)
        for meal in result[0]["meals"]:
            self.assertEqual(meal["cook_time_minutes"], 30)

    def test_parse_ingredients_as_string(self):
        """Comma-separated ingredient string is parsed correctly."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        response = [
            {
                "date": "2026-06-01",
                "meals": [
                    {
                        "meal_type": "dinner",
                        "title": "Pasta",
                        "ingredients": "pasta,  tomatoes,  basil ",
                    },
                ],
            },
        ]
        result = parse_weekly_plan(response)
        self.assertEqual(
            result[0]["meals"][0]["ingredients"],
            ["pasta", "tomatoes", "basil"],
        )


# =============================================================================
# GenerateAiPlanView Tests
# =============================================================================


def _consume_events(response):
    """Drain a ``StreamingHttpResponse`` from the test client into JSON events.

    The AI plan view streams ``text/event-stream`` with one ``data: {...}``
    payload per line, separated by blank lines. The test client returns a
    normal ``HttpResponse`` whose ``streaming_content`` holds the body;
    this helper joins decoded chunks and feeds each ``data:`` line to
    ``json.loads``.
    """
    raw = b"".join(
        chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
        for chunk in response.streaming_content
    ).decode("utf-8")
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line.split(":", 1)[1].strip()
            try:
                events.append(json_loads(payload))
            except ValueError:
                continue
    return events


def _run_progress_then_return(payload, sink):
    """Append a couple of fake progress labels so tests can assert streaming."""
    sink.append("Reading model response")
    sink.append("Saving review data")
    return payload


class GenerateAiPlanViewTests(TransactionTestCase):
    """Tests for GenerateAiPlanView.

    Uses ``TransactionTestCase`` rather than plain ``TestCase`` because the
    view runs the AI service on a worker ``threading.Thread`` whose reads
    would otherwise deadlock on the test class's outer transaction
    (SQLite holds a write lock for the duration of the parent's BEGIN).
    """

    # Reset between tests so threads left over from a previous run cannot
    # leak into the next case's MealPlan state.
    reset_sequences = False

    def setUp(self):
        self.household = Household.objects.create(name="AI View Test Household")
        self.user = User.objects.create_user(
            username="aiview",
            email="aiview@example.com",
            password="pass1234",
            household=self.household,
        )
        self.prefs = MealPreferences.objects.create(
            household=self.household,
            cuisine_preferences=["italian"],
            cooking_effort="moderate",
        )
        self.week_start = date(2026, 6, 1)
        self.valid_ai_response = [
            {
                "date": "2026-06-01",
                "meals": [
                    {
                        "meal_type": "breakfast",
                        "title": "Oatmeal",
                        "description": "Warm oats",
                        "cook_time_minutes": 10,
                        "ingredients": ["oats", "milk"],
                    },
                    {
                        "meal_type": "dinner",
                        "title": "Pasta",
                        "description": "Pasta with sauce",
                        "cook_time_minutes": 25,
                        "ingredients": ["pasta", "tomato sauce"],
                    },
                ],
            },
            {
                "date": "2026-06-02",
                "meals": [
                    {
                        "meal_type": "lunch",
                        "title": "Salad",
                        "description": "Fresh salad",
                        "cook_time_minutes": 10,
                        "ingredients": ["lettuce", "tomato"],
                    },
                ],
            },
        ]

    def test_requires_login(self):
        """Unauthenticated POST redirects to login."""
        response = self.client.post(reverse("meal_planner:generate_ai_plan"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_post_missing_week_start(self):
        """POST without week_start shows error and redirects."""
        self.client.login(username="aiview", password="pass1234")
        response = self.client.post(reverse("meal_planner:generate_ai_plan"))
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_post_requires_preferences_first(self):
        """Redirects to preferences page if no MealPreferences exists."""
        self.prefs.delete()
        self.client.login(username="aiview", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:generate_ai_plan"),
            {"week_start": str(self.week_start)},
        )
        self.assertRedirects(response, reverse("meal_planner:preferences"))

    @patch("meal_planner_app.services.ai_service.AIService._make_api_call")
    def test_post_redirects_to_review_on_success(self, mock_api_call):
        """Successful AI generation streams a ready event + redirect URL and stores in session."""
        mock_api_call.return_value = self.valid_ai_response

        self.client.login(username="aiview", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:generate_ai_plan"),
            {"week_start": str(self.week_start)},
        )

        # Streaming response: 200 OK with text/event-stream body.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/event-stream"))
        self.assertEqual(response["Cache-Control"], "no-cache")
        # No MealPlan rows should have been created (saved later on review).
        meals = MealPlan.objects.filter(household=self.household)
        self.assertEqual(meals.count(), 0)

        # Drain the stream and parse events.
        events = _consume_events(response)
        terminal = events[-1]
        self.assertEqual(terminal["kind"], "ready")
        self.assertEqual(
            terminal["redirect_url"],
            f"{reverse('meal_planner:ai_plan_review')}?week_start={self.week_start}",
        )

        # The session generator persists the plan via
        # ``request.session.save()`` because the SessionMiddleware save
        # already ran before the WSGI worker iterated the body. Verify the
        # DB-backed session store has the right payload for the next
        # request (the review page) to pick up.
        from django.contrib.sessions.models import Session

        session_key = f"ai_pending_plan_{self.household.pk}_{self.week_start}"
        matching = []
        for session_obj in Session.objects.all():
            decoded = session_obj.get_decoded()
            if session_key in decoded:
                matching.append(decoded[session_key])
        self.assertEqual(len(matching), 1)
        plan_data = matching[0]
        self.assertEqual(plan_data["week_start"], str(self.week_start))

    @patch("meal_planner_app.services.ai_service.AIService._make_api_call")
    def test_post_handles_api_error(self, mock_api_call):
        """API error streams an error event so the client can surface it."""
        mock_api_call.side_effect = ValueError("API connection failed")

        self.client.login(username="aiview", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:generate_ai_plan"),
            {"week_start": str(self.week_start)},
        )

        self.assertEqual(response.status_code, 200)
        meals = MealPlan.objects.filter(household=self.household)
        self.assertEqual(meals.count(), 0)

        events = _consume_events(response)
        terminal = events[-1]
        self.assertEqual(terminal["kind"], "error")
        self.assertIn("API connection failed", terminal["message"])

    @patch("meal_planner_app.services.ai_service.AIService._make_api_call")
    def test_marks_skipped_for_filled_days(self, mock_api_call):
        """Pre-filled slots cause day to be marked 'skipped' in session."""
        mock_api_call.return_value = self.valid_ai_response

        # Pre-fill all slots for day 1
        for mt in [t[0] for t in MealType.choices]:
            MealPlan.objects.create(
                household=self.household,
                meal_date=self.week_start,
                meal_type=mt,
                custom_meal="Existing Meal",
            )

        self.client.login(username="aiview", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:generate_ai_plan"),
            {"week_start": str(self.week_start)},
        )

        events = _consume_events(response)
        self.assertEqual(events[-1]["kind"], "ready")

        # Read the persisted plan via Session.objects; same DB session that
        # the next request (review page GET) would load.
        from django.contrib.sessions.models import Session

        session_key = f"ai_pending_plan_{self.household.pk}_{self.week_start}"
        plan_data = next(
            (
                s.get_decoded()[session_key]
                for s in Session.objects.all()
                if session_key in s.get_decoded()
            ),
            None,
        )
        self.assertIsNotNone(plan_data)
        self.assertEqual(plan_data["days"][0]["status"], "skipped")
        self.assertEqual(plan_data["days"][1]["status"], "pending")

    @patch("meal_planner_app.services.ai_service.AIService._make_api_call")
    def test_post_emits_progress_events_before_terminal(self, mock_api_call):
        """Each AIService-side label reaches the client before the terminal."""
        mock_api_call.return_value = self.valid_ai_response

        self.client.login(username="aiview", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:generate_ai_plan"),
            {"week_start": str(self.week_start)},
        )
        events = _consume_events(response)

        # Wire-side coverage: every AIService-emitted label surfaces as a
        # "progress" event in the stream before the terminal.
        progress_labels = [e["label"] for e in events if e["kind"] == "progress"]
        self.assertIn("Preparing prompt", progress_labels)
        self.assertIn("Talking to the model", progress_labels)
        self.assertIn("Reading model response", progress_labels)
        self.assertIn("Saving review data", progress_labels)

        # Terminal event must come LAST.
        self.assertEqual(events[-1]["kind"], "ready")


class AiPlanReviewViewTests(TestCase):
    """Tests for AiPlanReviewView (GET /ai-plan/review/)."""

    def setUp(self):
        self.household = Household.objects.create(name="Review Test Household")
        self.user = User.objects.create_user(
            username="reviewuser",
            email="review@example.com",
            password="pass1234",
            household=self.household,
        )
        self.week_start = date(2026, 6, 1)
        self.review_url = reverse("meal_planner:ai_plan_review")
        self.session_key = f"ai_pending_plan_{self.household.pk}_{self.week_start}"
        self.valid_session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "pending",
                    "day_name": "Monday",
                    "formatted_date": "Jun 1",
                    "meals": [
                        {
                            "meal_type": "breakfast",
                            "title": "Oatmeal",
                            "description": "Warm oats",
                            "cook_time_minutes": 10,
                            "ingredients": ["oats", "milk"],
                        },
                    ],
                },
                {
                    "index": 1,
                    "date": "2026-06-02",
                    "status": "accepted",
                    "day_name": "Tuesday",
                    "formatted_date": "Jun 2",
                    "meals": [
                        {
                            "meal_type": "dinner",
                            "title": "Pasta",
                            "description": "Pasta with sauce",
                            "cook_time_minutes": 25,
                            "ingredients": ["pasta", "tomato sauce"],
                        },
                    ],
                },
            ],
        }

    def test_requires_login(self):
        """Unauthenticated GET redirects to login."""
        response = self.client.get(self.review_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_no_week_start(self):
        """GET without week_start shows error and redirects to planner."""
        self.client.login(username="reviewuser", password="pass1234")
        response = self.client.get(self.review_url)
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_no_session_data(self):
        """GET with week_start but no session data redirects with info message."""
        self.client.login(username="reviewuser", password="pass1234")
        response = self.client.get(
            self.review_url,
            {"week_start": str(self.week_start)},
        )
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_renders_review_page(self):
        """GET with session data renders review template with day cards."""
        self.client.login(username="reviewuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = self.valid_session_data
        session.save()

        response = self.client.get(
            self.review_url,
            {"week_start": str(self.week_start)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "meal_planner/ai_plan_review.html")
        self.assertContains(response, "Monday")
        self.assertContains(response, "Tuesday")
        self.assertContains(response, "Oatmeal")
        self.assertContains(response, "Pasta")

    def test_display_counts(self):
        """Review page shows correct accepted/pending/rejected counts."""
        data = self.valid_session_data.copy()
        data["days"] = [
            {"index": 0, "date": "2026-06-01", "status": "pending", "meals": []},
            {"index": 1, "date": "2026-06-02", "status": "accepted", "meals": []},
            {"index": 2, "date": "2026-06-03", "status": "rejected", "meals": []},
        ]
        self.client.login(username="reviewuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = data
        session.save()

        response = self.client.get(
            self.review_url,
            {"week_start": str(self.week_start)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 accepted")
        self.assertContains(response, "1 pending")
        self.assertContains(response, "1 rejected")

    def test_empty_plan_shows_info(self):
        """Review page with empty days redirects with info."""
        data = self.valid_session_data.copy()
        data["days"] = []
        self.client.login(username="reviewuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = data
        session.save()

        response = self.client.get(
            self.review_url,
            {"week_start": str(self.week_start)},
        )
        self.assertRedirects(response, reverse("meal_planner:planner"))


class AiPlanDayActionViewTests(TestCase):
    """Tests for AiPlanDayActionView (POST /ai-plan/day-action/)."""

    def setUp(self):
        self.household = Household.objects.create(name="Day Action Test Household")
        self.user = User.objects.create_user(
            username="dayaction",
            email="dayaction@example.com",
            password="pass1234",
            household=self.household,
        )
        self.week_start = date(2026, 6, 1)
        self.action_url = reverse("meal_planner:ai_plan_day_action")
        self.review_url = reverse("meal_planner:ai_plan_review")
        self.session_key = f"ai_pending_plan_{self.household.pk}_{self.week_start}"

        self.session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "pending",
                    "meals": [
                        {
                            "meal_type": "breakfast",
                            "title": "Oatmeal",
                            "description": "Warm oats",
                            "cook_time_minutes": 10,
                            "ingredients": ["oats", "milk"],
                        },
                    ],
                },
                {
                    "index": 1,
                    "date": "2026-06-02",
                    "status": "pending",
                    "meals": [],
                },
            ],
        }

    def _init_session(self):
        session = self.client.session
        session[self.session_key] = self.session_data
        session.save()

    def test_requires_login(self):
        """Unauthenticated POST redirects to login."""
        response = self.client.post(self.action_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_missing_params(self):
        """POST with missing params shows error and redirects."""
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {"week_start": str(self.week_start)},
        )
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_invalid_day_index(self):
        """POST with invalid day index shows error and stays on review."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "accept",
                "day_index": "99",
            },
        )
        self.assertRedirects(
            response,
            f"{self.review_url}?week_start={self.week_start}",
        )

    def test_accept_day(self):
        """POST with action=accept updates day status to accepted."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "accept",
                "day_index": "0",
            },
        )
        self.assertRedirects(
            response,
            f"{self.review_url}?week_start={self.week_start}",
        )

        session = self.client.session
        plan_data = session[self.session_key]
        self.assertEqual(plan_data["days"][0]["status"], "accepted")

    def test_reject_day(self):
        """POST with action=reject updates day status to rejected."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject",
                "day_index": "0",
            },
        )
        self.assertRedirects(
            response,
            f"{self.review_url}?week_start={self.week_start}",
        )

        session = self.client.session
        plan_data = session[self.session_key]
        self.assertEqual(plan_data["days"][0]["status"], "rejected")

    def test_unknown_action(self):
        """POST with unknown action stays on review with error."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "unknown",
                "day_index": "0",
            },
        )
        self.assertRedirects(
            response,
            f"{self.review_url}?week_start={self.week_start}",
        )

        session = self.client.session
        plan_data = session[self.session_key]
        self.assertEqual(plan_data["days"][0]["status"], "pending")

    def test_missing_action(self):
        """POST without action redirects to planner with error."""
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "day_index": "0",
            },
        )
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_accept_meal_sets_status_and_keeps_day_accepted(self):
        """POST with action=accept_meal flips that meal's status to
        'accepted' and leaves a previously accepted day accepted."""
        self._init_session()
        # Make the day start out as "pending" so we can observe the
        # reconcile logic flipping it to "accepted" after one meal is
        # accepted.
        self.session_data["days"][0]["status"] = "pending"
        session = self.client.session
        session[self.session_key] = self.session_data
        session.save()

        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "accept_meal",
                "day_index": "0",
                "meal_index": "0",
            },
        )
        self.assertRedirects(
            response,
            f"{self.review_url}?week_start={self.week_start}",
        )

        session = self.client.session
        plan_data = session[self.session_key]
        self.assertEqual(
            plan_data["days"][0]["meals"][0]["status"], "accepted"
        )
        # Day status derived from meals: any accepted → day "accepted".
        self.assertEqual(plan_data["days"][0]["status"], "accepted")

    def test_reject_meal_marks_only_that_meal(self):
        """POST with action=reject_meal leaves the day accepted (other meals
        still accepted) and only flips the targeted meal."""
        self._init_session()
        # Accept the day first, with two meals so flipping one doesn't tip
        # the derived day status.
        self.session_data["days"][0]["status"] = "accepted"
        self.session_data["days"][0]["meals"] = [
            {
                "meal_type": "breakfast",
                "title": "Oatmeal",
                "description": "",
                "cook_time_minutes": 10,
                "ingredients": ["oats"],
                "status": "accepted",
            },
            {
                "meal_type": "dinner",
                "title": "Pasta",
                "description": "",
                "cook_time_minutes": 20,
                "ingredients": ["pasta"],
                "status": "accepted",
            },
        ]
        session = self.client.session
        session[self.session_key] = self.session_data
        session.save()

        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject_meal",
                "day_index": "0",
                "meal_index": "0",
            },
        )
        self.assertRedirects(
            response,
            f"{self.review_url}?week_start={self.week_start}",
        )

        plan_data = self.client.session[self.session_key]
        self.assertEqual(
            plan_data["days"][0]["meals"][0]["status"], "rejected"
        )
        self.assertEqual(
            plan_data["days"][0]["meals"][1]["status"], "accepted"
        )
        # Day still accepted because the other meal is still accepted.
        self.assertEqual(plan_data["days"][0]["status"], "accepted")

    def test_reject_all_meals_flips_day_status_to_rejected(self):
        """When every meal on a day is rejected, the day pill should
        automatically show as rejected (derived from meal statuses)."""
        self._init_session()
        self.session_data["days"][0]["status"] = "accepted"
        for meal in self.session_data["days"][0]["meals"]:
            meal["status"] = "accepted"
        session = self.client.session
        session[self.session_key] = self.session_data
        session.save()

        self.client.login(username="dayaction", password="pass1234")
        self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject_meal",
                "day_index": "0",
                "meal_index": "0",
            },
        )
        plan_data = self.client.session[self.session_key]
        self.assertEqual(plan_data["days"][0]["status"], "rejected")

    def test_reject_meal_with_invalid_index_returns_clean_error(self):
        """Rejecting an out-of-range meal index redirects to review,
        not to the planner — the user is mid-review and should not lose
        their place."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject_meal",
                "day_index": "0",
                "meal_index": "99",
            },
        )
        self.assertRedirects(
            response,
            f"{self.review_url}?week_start={self.week_start}",
        )

    def test_accept_day_marks_all_meals_accepted(self):
        """Day-level accept propagates to every meal so a later per-meal
        reject still finds the others accepted."""
        self._init_session()
        # Reset all meals to "rejected" to make the propagation visible.
        for meal in self.session_data["days"][0]["meals"]:
            meal["status"] = "rejected"
        session = self.client.session
        session[self.session_key] = self.session_data
        session.save()

        self.client.login(username="dayaction", password="pass1234")
        self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "accept",
                "day_index": "0",
            },
        )
        plan_data = self.client.session[self.session_key]
        for meal in plan_data["days"][0]["meals"]:
            self.assertEqual(meal["status"], "accepted")

    def test_reject_day_marks_all_meals_rejected(self):
        """Day-level reject propagates to every meal too."""
        self._init_session()
        for meal in self.session_data["days"][0]["meals"]:
            meal["status"] = "accepted"
        session = self.client.session
        session[self.session_key] = self.session_data
        session.save()

        self.client.login(username="dayaction", password="pass1234")
        self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject",
                "day_index": "0",
            },
        )
        plan_data = self.client.session[self.session_key]
        for meal in plan_data["days"][0]["meals"]:
            self.assertEqual(meal["status"], "rejected")

    def test_ajax_reject_meal_returns_json(self):
        """AJAX POST rejects a meal in-place and reports the new state
        so the page can animate the meal card out without a redirect."""
        self._init_session()
        # Day is accepted with two meals accepted; rejecting one keeps
        # the day accepted (other meal still accepted).
        self.session_data["days"][0]["status"] = "accepted"
        self.session_data["days"][0]["meals"] = [
            {
                "meal_type": "breakfast",
                "title": "Oatmeal",
                "description": "",
                "cook_time_minutes": 10,
                "ingredients": ["oats"],
                "status": "accepted",
            },
            {
                "meal_type": "dinner",
                "title": "Pasta",
                "description": "",
                "cook_time_minutes": 20,
                "ingredients": ["pasta"],
                "status": "accepted",
            },
        ]
        session = self.client.session
        session[self.session_key] = self.session_data
        session.save()

        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject_meal",
                "day_index": "0",
                "meal_index": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["action"], "reject_meal")
        self.assertEqual(body["day_index"], 0)
        self.assertEqual(body["day_status"], "accepted")
        self.assertEqual(body["meal_total"], 2)
        self.assertEqual(body["meal_accepted"], 1)
        self.assertEqual(body["meal_rejected"], 1)
        self.assertEqual(body["meal"], {"meal_index": 0, "meal_status": "rejected"})

    def test_ajax_reject_last_meal_flips_day_status(self):
        """Rejecting the last accepted meal flips the day from accepted
        to rejected and the JSON payload reports the new day_status so
        the page can reload (and re-render the day footer)."""
        self._init_session()
        self.session_data["days"][0]["status"] = "accepted"
        self.session_data["days"][0]["meals"][0]["status"] = "accepted"
        session = self.client.session
        session[self.session_key] = self.session_data
        session.save()

        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject_meal",
                "day_index": "0",
                "meal_index": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["day_status"], "rejected")
        self.assertEqual(body["meal_total"], 1)
        self.assertEqual(body["meal_accepted"], 0)
        self.assertEqual(body["meal_rejected"], 1)

    def test_ajax_bad_action_returns_400(self):
        """AJAX unknown action returns 400 JSON error so the page can surface
        it without a page reload."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "sideways",
                "day_index": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("Unknown action", body["error"])

    def test_ajax_missing_plan_returns_400(self):
        """AJAX reject on a session that has no AI plan returns 400 JSON."""
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject_meal",
                "day_index": "0",
                "meal_index": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("No pending AI plan", body["error"])

    def test_ajax_reject_day_returns_day_status(self):
        """AJAX day-level reject reports the new day_status and counts."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                "week_start": str(self.week_start),
                "action": "reject",
                "day_index": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["day_status"], "rejected")
        # Did not include a single-meal sub-payload.
        self.assertNotIn("meal", body)

    def test_ajax_reject_meal_iso_week_start_matches_session_key(self):
        """Regression: the review page used to send the long-format
        ``{{ week_start }}`` ``value`` (e.g. "June 29, 2026"), which
        diverged from the ISO ``2026-06-29`` written by the generator's
        ``date:'Y-m-d'`` filter. The session lookup then failed even
        though the plan was present. The form now serializes with the
        ISO filter; this test pins the contract."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                # ISO — must match the session key the generator wrote.
                "week_start": str(self.week_start),
                "action": "reject_meal",
                "day_index": "0",
                "meal_index": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_ajax_reject_meal_long_format_week_start_does_not_match(self):
        """The long format that the buggy {{ week_start }} used to send
        (e.g. ``June 29, 2026``) should *not* match the session key —
        if this ever changes, the AJAX path will silently regress to
        "No pending AI plan found" errors. Locked in to fail loud."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.post(
            self.action_url,
            {
                # Same date as str(self.week_start) but in Django's long
                # default format — exactly what ``{{ week_start }}``
                # rendered before the render-side filter was added.
                "week_start": self.week_start.strftime("%B %-d, %Y"),
                "action": "reject_meal",
                "day_index": "0",
                "meal_index": "0",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_review_page_renders_iso_week_start_in_all_hidden_inputs(self):
        """Every ``week_start`` hidden input on the rendered review page
        must use ISO ``YYYY-MM-DD`` — otherwise the AJAX POST sends the
        wrong key and looks like a session-loss bug."""
        self._init_session()
        self.client.login(username="dayaction", password="pass1234")
        response = self.client.get(
            f"{self.review_url}?week_start={self.week_start}",
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        iso_value = str(self.week_start)
        long_value = self.week_start.strftime("%B %-d, %Y")
        # The ISO value appears in the markup; the long format must NOT.
        self.assertIn(f'value="{iso_value}"', body)
        # Make sure no form-value still ships the legacy long format.
        self.assertNotIn(f'value="{long_value}"', body)


class AiPlanSaveViewTests(TestCase):
    """Tests for AiPlanSaveView (POST /ai-plan/save/)."""

    def setUp(self):
        self.household = Household.objects.create(name="Save Test Household")
        self.user = User.objects.create_user(
            username="saveuser",
            email="save@example.com",
            password="pass1234",
            household=self.household,
        )
        self.week_start = date(2026, 6, 1)
        self.save_url = reverse("meal_planner:ai_plan_save")
        self.review_url = reverse("meal_planner:ai_plan_review")
        self.session_key = f"ai_pending_plan_{self.household.pk}_{self.week_start}"

    def test_requires_login(self):
        """Unauthenticated POST redirects to login."""
        response = self.client.post(self.save_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_no_accepted_days(self):
        """POST with no accepted days redirects to review with info."""
        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "pending",
                    "meals": [
                        {
                            "meal_type": "dinner",
                            "title": "Test Meal",
                            "description": "Desc",
                            "cook_time_minutes": 20,
                            "ingredients": ["x"],
                        },
                    ],
                },
            ],
        }
        self.client.login(username="saveuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        response = self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )
        self.assertRedirects(
            response,
            f"{self.review_url}?week_start={self.week_start}",
        )

        self.assertEqual(MealPlan.objects.filter(household=self.household).count(), 0)

    def test_saves_accepted_days(self):
        """POST with accepted days creates MealPlan entries."""
        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "breakfast",
                            "title": "Oatmeal",
                            "description": "Warm oats",
                            "cook_time_minutes": 10,
                            "ingredients": ["oats", "milk"],
                        },
                        {
                            "meal_type": "dinner",
                            "title": "Pasta",
                            "description": "Pasta with sauce",
                            "cook_time_minutes": 25,
                            "ingredients": ["pasta", "tomato"],
                        },
                    ],
                },
                {
                    "index": 1,
                    "date": "2026-06-02",
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "lunch",
                            "title": "Salad",
                            "description": "Fresh salad",
                            "cook_time_minutes": 10,
                            "ingredients": ["lettuce"],
                        },
                    ],
                },
            ],
        }
        self.client.login(username="saveuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        response = self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )

        meals = MealPlan.objects.filter(household=self.household)
        self.assertEqual(meals.count(), 3)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(self.session_key, self.client.session)

    def test_skips_filled_slots(self):
        """Pre-existing meals in a slot are not overwritten."""
        MealPlan.objects.create(
            household=self.household,
            meal_date=self.week_start,
            meal_type="breakfast",
            custom_meal="Existing Meal",
        )

        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "breakfast",
                            "title": "AI Oatmeal",
                            "description": "AI version",
                            "cook_time_minutes": 10,
                            "ingredients": ["oats"],
                        },
                        {
                            "meal_type": "dinner",
                            "title": "Pasta",
                            "description": "AI version",
                            "cook_time_minutes": 25,
                            "ingredients": ["pasta"],
                        },
                    ],
                },
            ],
        }
        self.client.login(username="saveuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )

        meals = MealPlan.objects.filter(household=self.household)
        self.assertEqual(meals.count(), 2)

    def test_missing_week_start(self):
        """POST without week_start redirects to planner."""
        self.client.login(username="saveuser", password="pass1234")
        response = self.client.post(self.save_url)
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_no_session_data(self):
        """POST with no session data redirects to planner."""
        self.client.login(username="saveuser", password="pass1234")
        response = self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_saves_ingredients_from_session(self):
        """Accepted meals persist their ingredients list to MealPlan."""
        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "breakfast",
                            "title": "Oatmeal",
                            "description": "Warm oats",
                            "cook_time_minutes": 10,
                            "ingredients": ["oats", "milk", "banana"],
                        },
                    ],
                },
            ],
        }
        self.client.login(username="saveuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )

        meal = MealPlan.objects.get(
            household=self.household,
            meal_date=date(2026, 6, 1),
            meal_type="breakfast",
        )
        self.assertEqual(meal.ingredients, ["oats", "milk", "banana"])

    def test_saves_without_ingredients_defaults_to_empty(self):
        """Accepted meals without ingredients field default to empty list."""
        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "dinner",
                            "title": "Pasta",
                            "description": "Pasta with sauce",
                            "cook_time_minutes": 25,
                        },
                    ],
                },
            ],
        }
        self.client.login(username="saveuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )

        meal = MealPlan.objects.get(
            household=self.household,
            meal_date=date(2026, 6, 1),
            meal_type="dinner",
        )
        self.assertEqual(meal.ingredients, [])

    def test_saves_with_empty_ingredients(self):
        """Accepted meals with empty ingredients list saved as empty."""
        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "snack",
                            "title": "Fruit",
                            "description": "Fresh fruit",
                            "cook_time_minutes": 5,
                            "ingredients": [],
                        },
                    ],
                },
            ],
        }
        self.client.login(username="saveuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )

        meal = MealPlan.objects.get(
            household=self.household,
            meal_date=date(2026, 6, 1),
            meal_type="snack",
        )
        self.assertEqual(meal.ingredients, [])

    def test_skips_per_meal_rejections_when_saving_accepted_day(self):
        """A day can stay "accepted" while one meal is individually rejected.
        Save must honor that and only persist the accepted meals."""
        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": str(self.week_start),
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "breakfast",
                            "title": "Yes Oatmeal",
                            "description": "",
                            "cook_time_minutes": 10,
                            "ingredients": ["oats"],
                            "status": "accepted",
                        },
                        {
                            "meal_type": "dinner",
                            "title": "No Pasta",
                            "description": "",
                            "cook_time_minutes": 25,
                            "ingredients": ["pasta"],
                            "status": "rejected",
                        },
                    ],
                },
            ],
        }
        self.client.login(username="saveuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )
        meals = MealPlan.objects.filter(household=self.household)
        self.assertEqual(meals.count(), 1)
        self.assertEqual(meals.first().meal_type, "breakfast")
        self.assertIn("Yes Oatmeal", meals.first().custom_meal)

    def test_saves_only_accepted_meals_when_day_has_mixed_statuses(self):
        """If meals are flipped individually after the day was accepted,
        only the explicitly accepted meals land in MealPlan."""
        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": str(self.week_start),
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "breakfast",
                            "title": "A1",
                            "description": "",
                            "cook_time_minutes": 5,
                            "ingredients": ["x"],
                            "status": "accepted",
                        },
                        {
                            "meal_type": "lunch",
                            "title": "A2",
                            "description": "",
                            "cook_time_minutes": 5,
                            "ingredients": ["x"],
                            "status": "accepted",
                        },
                        {
                            "meal_type": "dinner",
                            "title": "A3",
                            "description": "",
                            "cook_time_minutes": 5,
                            "ingredients": ["x"],
                            "status": "rejected",
                        },
                    ],
                },
            ],
        }
        self.client.login(username="saveuser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )
        slots = list(
            MealPlan.objects.filter(household=self.household)
            .order_by("meal_type")
            .values_list("meal_type", flat=True)
        )
        self.assertEqual(slots, ["breakfast", "lunch"])


class AiPlanCancelViewTests(TestCase):
    """Tests for AiPlanCancelView (POST /ai-plan/cancel/)."""

    def setUp(self):
        self.household = Household.objects.create(name="Cancel Test Household")
        self.user = User.objects.create_user(
            username="canceluser",
            email="cancel@example.com",
            password="pass1234",
            household=self.household,
        )
        self.week_start = date(2026, 6, 1)
        self.cancel_url = reverse("meal_planner:ai_plan_cancel")
        self.session_key = f"ai_pending_plan_{self.household.pk}_{self.week_start}"

    def test_requires_login(self):
        """Unauthenticated POST redirects to login."""
        response = self.client.post(self.cancel_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_cancels_session(self):
        """POST with week_start clears session and redirects."""
        self.client.login(username="canceluser", password="pass1234")
        session = self.client.session
        session[self.session_key] = {"week_start": str(self.week_start), "days": []}
        session.save()

        self.assertIn(self.session_key, self.client.session)

        response = self.client.post(
            self.cancel_url,
            {"week_start": str(self.week_start)},
        )
        self.assertNotIn(self.session_key, self.client.session)
        self.assertEqual(response.status_code, 302)

    def test_cancel_without_week_start(self):
        """POST without week_start redirects to planner."""
        self.client.login(username="canceluser", password="pass1234")
        response = self.client.post(self.cancel_url)
        self.assertRedirects(response, reverse("meal_planner:planner"))

    def test_cancel_creates_no_meals(self):
        """Cancelling the plan creates no MealPlan entries."""
        self.client.login(username="canceluser", password="pass1234")
        session = self.client.session
        session[self.session_key] = {"week_start": str(self.week_start), "days": []}
        session.save()

        self.client.post(
            self.cancel_url,
            {"week_start": str(self.week_start)},
        )
        self.assertEqual(MealPlan.objects.filter(household=self.household).count(), 0)


class AiPlanWorkflowIntegrationTests(TransactionTestCase):
    """Integration tests for the complete AI plan workflow end-to-end."""

    def setUp(self):
        self.household = Household.objects.create(name="Workflow Test Household")
        self.user = User.objects.create_user(
            username="workflow",
            email="workflow@example.com",
            password="pass1234",
            household=self.household,
        )
        self.prefs = MealPreferences.objects.create(
            household=self.household,
            cuisine_preferences=["italian"],
            cooking_effort="moderate",
        )
        self.week_start = date(2026, 6, 1)
        self.valid_ai_response = [
            {
                "date": "2026-06-01",
                "meals": [
                    {
                        "meal_type": "dinner",
                        "title": "Pasta",
                        "description": "Pasta with sauce",
                        "cook_time_minutes": 25,
                        "ingredients": ["pasta", "tomato"],
                    },
                ],
            },
        ]

    @patch("meal_planner_app.services.ai_service.AIService._make_api_call")
    def test_full_generate_accept_save_flow(self, mock_api_call):
        """Complete flow: generate - review - accept - save."""
        mock_api_call.return_value = self.valid_ai_response

        self.client.login(username="workflow", password="pass1234")

        response = self.client.post(
            reverse("meal_planner:generate_ai_plan"),
            {"week_start": str(self.week_start)},
        )
        # Drain the SSE body so the generator's session.write runs and the
        # DB-backed session is persisted for the next request to load.
        events = _consume_events(response)
        self.assertEqual(events[-1]["kind"], "ready")

        response = self.client.post(
            reverse("meal_planner:ai_plan_day_action"),
            {
                "week_start": str(self.week_start),
                "action": "accept",
                "day_index": "0",
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('meal_planner:ai_plan_review')}?week_start={self.week_start}",
        )

        response = self.client.post(
            reverse("meal_planner:ai_plan_save"),
            {"week_start": str(self.week_start)},
        )
        self.assertEqual(response.status_code, 302)

        meals = MealPlan.objects.filter(household=self.household)
        self.assertEqual(meals.count(), 1)
        self.assertIn("Pasta", meals[0].custom_meal)

    @patch("meal_planner_app.services.ai_service.AIService._make_api_call")
    def test_generate_reject_flow(self, mock_api_call):
        """Flow: generate - reject - verify status updated."""
        mock_api_call.return_value = self.valid_ai_response

        self.client.login(username="workflow", password="pass1234")

        response = self.client.post(
            reverse("meal_planner:generate_ai_plan"),
            {"week_start": str(self.week_start)},
        )
        # Drain the SSE body so the worker thread commits its session write
        # to the DB before the next request loads it.
        events = _consume_events(response)
        self.assertEqual(events[-1]["kind"], "ready")

        self.client.post(
            reverse("meal_planner:ai_plan_day_action"),
            {
                "week_start": str(self.week_start),
                "action": "reject",
                "day_index": "0",
            },
        )

        # Read the persisted plan via Session.objects so we look at the
        # same DB row the next page view (or test assert_*) is reading.
        from django.contrib.sessions.models import Session

        session_key = f"ai_pending_plan_{self.household.pk}_{self.week_start}"
        plan_data = next(
            (
                s.get_decoded()[session_key]
                for s in Session.objects.all()
                if session_key in s.get_decoded()
            ),
            None,
        )
        self.assertIsNotNone(plan_data)
        self.assertEqual(plan_data["days"][0]["status"], "rejected")


# =============================================================================
# Tests for On-Hand Ideas Views
# =============================================================================


class OnHandIdeasViewTests(TestCase):
    """Tests for OnHandIdeasView (GET /on-hand/)."""

    def setUp(self):
        self.household = Household.objects.create(name="OnHand Test")
        self.user = User.objects.create_user(
            username="onhanduser",
            email="onhand@example.com",
            password="pass1234",
            household=self.household,
        )
        self.url = reverse("meal_planner:on_hand_ideas")

        # Create some recipes — one on-hand, one not
        self.recipe_on_hand = Recipe.objects.create(
            household=self.household,
            title="On Hand Recipe",
            on_hand_idea=True,
            needs_review=False,
        )
        self.recipe_normal = Recipe.objects.create(
            household=self.household,
            title="Normal Recipe",
            on_hand_idea=False,
            needs_review=False,
        )

    def test_requires_login(self):
        """Unauthenticated GET redirects to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_returns_on_hand_recipes_in_context(self):
        """GET returns only recipes with on_hand_idea=True."""
        self.client.login(username="onhanduser", password="pass1234")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "meal_planner/on_hand_ideas.html")
        recipes = response.context["on_hand_recipes"]
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0].title, "On Hand Recipe")

    def test_rating_zero_when_no_rating_exists(self):
        """Recipe rating is 0 when no Rating records exist."""
        self.client.login(username="onhanduser", password="pass1234")
        response = self.client.get(self.url)
        recipes = response.context["on_hand_recipes"]
        self.assertEqual(recipes[0].rating, 0)

    def test_other_household_not_shown(self):
        """Recipes from other households are excluded."""
        other_household = Household.objects.create(name="Other")
        other_recipe = Recipe.objects.create(
            household=other_household,
            title="Other's On Hand",
            on_hand_idea=True,
            needs_review=False,
        )
        self.client.login(username="onhanduser", password="pass1234")
        response = self.client.get(self.url)
        recipes = response.context["on_hand_recipes"]
        self.assertEqual(len(recipes), 1)
        self.assertNotIn(other_recipe, recipes)


class ToggleOnHandIdeaViewTests(TestCase):
    """Tests for ToggleOnHandIdeaView (POST /api/recipe/<id>/toggle-on-hand/)."""

    def setUp(self):
        self.household = Household.objects.create(name="ToggleOnHand Test")
        self.user = User.objects.create_user(
            username="toggleonuser",
            email="toggleon@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Toggle Recipe",
            on_hand_idea=False,
            needs_review=False,
        )

    def _url(self):
        return reverse("meal_planner:toggle_on_hand", args=[self.recipe.pk])

    def test_requires_login(self):
        """Unauthenticated POST returns 302."""
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 302)

    def test_toggles_on_hand_flag_on(self):
        """POST toggles on_hand_idea from False to True."""
        self.client.login(username="toggleonuser", password="pass1234")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["on_hand_idea"])
        self.recipe.refresh_from_db()
        self.assertTrue(self.recipe.on_hand_idea)

    def test_toggles_on_hand_flag_off(self):
        """POST toggles on_hand_idea from True to False."""
        self.recipe.on_hand_idea = True
        self.recipe.save()
        self.client.login(username="toggleonuser", password="pass1234")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["on_hand_idea"])
        self.recipe.refresh_from_db()
        self.assertFalse(self.recipe.on_hand_idea)

    def test_other_household_returns_404(self):
        """Toggling another household's recipe returns 404."""
        other_household = Household.objects.create(name="Other")
        other_recipe = Recipe.objects.create(
            household=other_household,
            title="Other's Recipe",
            needs_review=False,
        )
        self.client.login(username="toggleonuser", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:toggle_on_hand", args=[other_recipe.pk])
        )
        self.assertEqual(response.status_code, 404)


class ToggleLeftoverWorthyViewTests(TestCase):
    """Tests for ToggleLeftoverWorthyView (POST /api/recipe/<id>/toggle-leftover/)."""

    def setUp(self):
        self.household = Household.objects.create(name="ToggleLeftover Test")
        self.user = User.objects.create_user(
            username="toggleleftuser",
            email="toggleleft@example.com",
            password="pass1234",
            household=self.household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Leftover Recipe",
            leftover_worthy=False,
            needs_review=False,
        )

    def _url(self):
        return reverse("meal_planner:toggle_leftover", args=[self.recipe.pk])

    def test_requires_login(self):
        """Unauthenticated POST returns 302."""
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 302)

    def test_toggles_leftover_flag_on(self):
        """POST toggles leftover_worthy from False to True."""
        self.client.login(username="toggleleftuser", password="pass1234")
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["leftover_worthy"])
        self.recipe.refresh_from_db()
        self.assertTrue(self.recipe.leftover_worthy)

    def test_toggles_leftover_flag_off(self):
        """POST toggles leftover_worthy from True to False."""
        self.recipe.leftover_worthy = True
        self.recipe.save()
        self.client.login(username="toggleleftuser", password="pass1234")
        response = self.client.post(self._url())
        data = response.json()
        self.assertFalse(data["leftover_worthy"])
        self.recipe.refresh_from_db()
        self.assertFalse(self.recipe.leftover_worthy)

    def test_other_household_returns_404(self):
        """Toggling another household's recipe returns 404."""
        other_household = Household.objects.create(name="Other")
        other_recipe = Recipe.objects.create(
            household=other_household,
            title="Other's Recipe",
            needs_review=False,
        )
        self.client.login(username="toggleleftuser", password="pass1234")
        response = self.client.post(
            reverse("meal_planner:toggle_leftover", args=[other_recipe.pk])
        )
        self.assertEqual(response.status_code, 404)


class JsonOnHandRecipesViewTests(TestCase):
    """Tests for JsonOnHandRecipesView (GET /api/on-hand/recipes/)."""

    def setUp(self):
        self.household = Household.objects.create(name="JsonOnHand Test")
        self.user = User.objects.create_user(
            username="jsononuser",
            email="jsonon@example.com",
            password="pass1234",
            household=self.household,
        )
        self.url = reverse("meal_planner:api_on_hand_recipes")

        # Create recipes with ingredients
        self.on_hand_recipe = Recipe.objects.create(
            household=self.household,
            title="On Hand Pasta",
            on_hand_idea=True,
            needs_review=False,
        )
        ingredient = Ingredient.objects.create(
            household=self.household, name="pasta"
        )
        IngredientLink.objects.create(
            recipe=self.on_hand_recipe,
            ingredient=ingredient,
            quantity=Decimal("1.00"),
            unit="cup",
            order=0,
        )

        self.normal_recipe = Recipe.objects.create(
            household=self.household,
            title="Normal Pizza",
            on_hand_idea=False,
            needs_review=False,
        )

    def test_requires_login(self):
        """Unauthenticated GET returns 302."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_returns_json_with_on_hand_recipes(self):
        """GET returns JSON with only on_hand_idea=True recipes."""
        self.client.login(username="jsononuser", password="pass1234")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("recipes", data)
        self.assertIsInstance(data["recipes"], list)
        self.assertEqual(len(data["recipes"]), 1)
        self.assertEqual(data["recipes"][0]["title"], "On Hand Pasta")

    def test_json_includes_recipe_fields(self):
        """JSON response includes id, title, on_hand_idea fields."""
        self.client.login(username="jsononuser", password="pass1234")
        response = self.client.get(self.url)
        data = response.json()
        recipe = data["recipes"][0]
        self.assertIn("id", recipe)
        self.assertIn("title", recipe)
        self.assertIn("on_hand_idea", recipe)
        self.assertTrue(recipe["on_hand_idea"])

    def test_excludes_other_household_recipes(self):
        """Recipes from other households are excluded."""
        other_household = Household.objects.create(name="Other")
        other_recipe = Recipe.objects.create(
            household=other_household,
            title="Other's On Hand",
            on_hand_idea=True,
            needs_review=False,
        )
        self.client.login(username="jsononuser", password="pass1234")
        response = self.client.get(self.url)
        data = response.json()
        titles = [r["title"] for r in data["recipes"]]
        self.assertNotIn("Other's On Hand", titles)


class JsonLeftoverRecipesViewTests(TestCase):
    """Tests for JsonLeftoverRecipesView (GET /api/leftover/recipes/)."""

    def setUp(self):
        self.household = Household.objects.create(name="JsonLeftover Test")
        self.user = User.objects.create_user(
            username="jsonleftuser",
            email="jsonleft@example.com",
            password="pass1234",
            household=self.household,
        )
        self.url = reverse("meal_planner:api_leftover_recipes")

        self.leftover_recipe = Recipe.objects.create(
            household=self.household,
            title="Leftover Soup",
            leftover_worthy=True,
            needs_review=False,
        )
        self.normal_recipe = Recipe.objects.create(
            household=self.household,
            title="Normal Salad",
            leftover_worthy=False,
            needs_review=False,
        )

    def test_requires_login(self):
        """Unauthenticated GET returns 302."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_returns_json_with_leftover_recipes(self):
        """GET returns JSON with only leftover_worthy=True recipes."""
        self.client.login(username="jsonleftuser", password="pass1234")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("recipes", data)
        self.assertEqual(len(data["recipes"]), 1)
        self.assertEqual(data["recipes"][0]["title"], "Leftover Soup")

    def test_excludes_other_household(self):
        """Other household's leftover recipes are excluded."""
        other = Household.objects.create(name="Other")
        Recipe.objects.create(
            household=other,
            title="Other's Leftover",
            leftover_worthy=True,
            needs_review=False,
        )
        self.client.login(username="jsonleftuser", password="pass1234")
        response = self.client.get(self.url)
        data = response.json()
        titles = [r["title"] for r in data["recipes"]]
        self.assertNotIn("Other's Leftover", titles)


class AiPlanSaveSuccessMessageTests(TestCase):
    """Tests for success message content in AiPlanSaveView."""

    def setUp(self):
        self.household = Household.objects.create(name="Msg Test")
        self.user = User.objects.create_user(
            username="msguser",
            email="msg@example.com",
            password="pass1234",
            household=self.household,
        )
        self.week_start = date(2026, 6, 1)
        self.save_url = reverse("meal_planner:ai_plan_save")
        self.session_key = f"ai_pending_plan_{self.household.pk}_{self.week_start}"

    def test_success_message_mentions_shopping_list(self):
        """Success message includes 'Shopping List' text."""
        session_data = {
            "week_start": str(self.week_start),
            "days": [
                {
                    "index": 0,
                    "date": "2026-06-01",
                    "status": "accepted",
                    "meals": [
                        {
                            "meal_type": "dinner",
                            "title": "Test Meal",
                            "description": "Desc",
                            "cook_time_minutes": 20,
                            "ingredients": [],
                        },
                    ],
                },
            ],
        }
        self.client.login(username="msguser", password="pass1234")
        session = self.client.session
        session[self.session_key] = session_data
        session.save()

        response = self.client.post(
            self.save_url,
            {"week_start": str(self.week_start)},
        )

        messages_list = list(response.wsgi_request._messages)
        self.assertEqual(len(messages_list), 1)
        self.assertIn("Shopping List", str(messages_list[0]))
        self.assertIn("1", str(messages_list[0]))


class HomePageViewTests(TestCase):
    """Tests for the project HomePageView and the reviews-count badge."""

    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Homepage Household")
        self.other_household = Household.objects.create(name="Other Homepage")
        self.user = user_model.objects.create_user(
            username="homepage-user",
            email="homepage@example.com",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def _make_recipes(self, count, household, needs_review=True):
        for index in range(count):
            Recipe.objects.create(
                household=household,
                title=f"Recipe {index}",
                needs_review=needs_review,
            )

    def test_home_renders_for_authenticated_user(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_home_counts_only_needs_review_recipes_in_self_household(self):
        # 3 needs_review=True in self.household; 1 needs_review=False in
        # self.household; 2 in other_household (must NOT be counted).
        for index in range(3):
            Recipe.objects.create(
                household=self.household,
                title=f"Pending {index}",
                needs_review=True,
            )
        Recipe.objects.create(
            household=self.household,
            title="Reviewed",
            needs_review=False,
        )
        for index in range(2):
            Recipe.objects.create(
                household=self.other_household,
                title=f"Other {index}",
                needs_review=True,
            )

        response = self.client.get(reverse("home"))
        self.assertEqual(response.context.get("reviews_count"), 3)

    def test_home_recipe_reviews_card_omits_badge_when_no_pending(self):
        Recipe.objects.create(
            household=self.household, title="Done", needs_review=False
        )

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.get("reviews_count"), 0)
        body = response.content.decode("utf-8")
        # The phrase "need review" only appears inside the badge; the section
        # is absent when no recipes are pending.
        self.assertNotIn("need review", body)

    def test_home_recipe_reviews_card_shows_singular_badge_for_one(self):
        self._make_recipes(1, self.household)

        response = self.client.get(reverse("home"))
        body = response.content.decode("utf-8")
        # Count == 1: Django's pluralize tag drops the "s" so the rendered
        # text is "1 need review" (no apostrophe-s). CSS uppercase shows it
        # as "1 NEED REVIEW" but that's a presentational transform.
        self.assertIn("1 need review</span>", body)
        self.assertNotIn("1 needs review", body)

    def test_home_recipe_reviews_card_shows_plural_badge_for_many(self):
        self._make_recipes(5, self.household)

        response = self.client.get(reverse("home"))
        body = response.content.decode("utf-8")
        self.assertIn("5 needs review</span>", body)

    def test_home_anonymous_user_omits_reviews_count_from_context(self):
        self.client.logout()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        # reviews_count is not passed at all for anonymous visitors so the
        # template's `{% if reviews_count %}` branch is skipped cleanly.
        self.assertNotIn("reviews_count", response.context)
