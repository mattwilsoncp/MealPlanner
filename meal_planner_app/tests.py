from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, RequestFactory
from django.urls import reverse

from household.models import Household
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
