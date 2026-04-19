import calendar
from datetime import date, datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    TemplateView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
    View,
)
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.core.serializers import serialize
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from .models import MealPlan, MealType, SideDish
from .forms import MealPlanForm, SideDishForm
from recipes.models import Recipe


class PlannerHomeView(LoginRequiredMixin, TemplateView):
    template_name = "meal_planner/planner.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get year and week from URL params or default to current week
        year = self.kwargs.get("year")
        week = self.kwargs.get("week")

        if year and week:
            # Calculate the Monday of the given week
            jan_1 = date(year, 1, 1)
            # Find the first Monday
            first_monday = jan_1 + timedelta(days=(7 - jan_1.weekday()) % 7)
            # Add weeks
            start_date = first_monday + timedelta(weeks=week - 1)
        else:
            # Default to current week (Monday)
            today = date.today()
            start_date = today - timedelta(days=today.weekday())

        end_date = start_date + timedelta(days=6)

        # Build week days list
        week_days = []
        for i in range(7):
            day = start_date + timedelta(days=i)
            day_name = day.strftime("%A")
            week_days.append(
                {
                    "date": day,
                    "day_name": day_name,
                    "date_str": day.strftime("%Y-%m-%d"),
                }
            )

        context["start_date"] = start_date
        context["end_date"] = end_date
        context["week_days"] = week_days
        context["week_year"] = year
        context["week_number"] = week
        context["meal_types"] = ["breakfast", "lunch", "dinner", "snack"]

        return context


def week_navigate(request):
    """Navigate to next or previous week."""
    current = request.GET.get("current")
    offset = int(request.GET.get("offset", 0))

    if current:
        # Parse current date
        current_date = datetime.strptime(current, "%Y-%m-%d").date()
    else:
        current_date = datetime.now().date()

    # Calculate new week start (Monday)
    new_date = current_date + timedelta(weeks=offset)
    # Adjust to Monday
    new_date = new_date - timedelta(days=new_date.weekday())

    # Get ISO week number
    iso_cal = calendar.IsoCalendar()
    year, week_num, _ = iso_cal.isocalendar(new_date)

    return redirect(reverse("meal_planner:planner_week", args=[year, week_num]))


def json_week_meals(request):
    """Return meals for a date range as JSON."""
    # Get date range from query params
    start = request.GET.get("start")
    end = request.GET.get("end")

    if not start or not end:
        # Default to current week
        today = date.today()
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()

    # Get meals for user's household
    meals = MealPlan.objects.filter(
        household=request.user.household,
        meal_date__gte=start_date,
        meal_date__lte=end_date,
    ).select_related("recipe")

    # Serialize
    data = []
    for meal in meals:
        # Get side dishes
        side_dishes = []
        for sd in meal.side_dishes.all():
            side_dishes.append(
                {
                    "id": sd.id,
                    "recipe_id": sd.recipe.id if sd.recipe else None,
                    "recipe_title": sd.recipe.title if sd.recipe else None,
                    "custom_side": sd.custom_side,
                    "order": sd.order,
                }
            )

        data.append(
            {
                "id": meal.id,
                "meal_date": meal.meal_date.strftime("%Y-%m-%d"),
                "meal_type": meal.meal_type,
                "meal_type_display": meal.get_meal_type_display(),
                "recipe_id": meal.recipe.id if meal.recipe else None,
                "recipe_title": meal.recipe.title if meal.recipe else None,
                "custom_meal": meal.custom_meal,
                "notes": meal.notes,
                "meal_rating": meal.meal_rating,
                "side_dishes": side_dishes,
            }
        )

    return JsonResponse({"meals": data})


class AddMealView(LoginRequiredMixin, CreateView):
    """View for adding a new meal to the planner."""

    model = MealPlan
    form_class = MealPlanForm
    template_name = "meal_planner/meal_form.html"

    def get_success_url(self):
        return reverse("meal_planner:planner")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_initial(self):
        """Pre-fill date and meal_type from query params."""
        initial = super().get_initial()
        date_param = self.request.GET.get("date")
        type_param = self.request.GET.get("type")
        if date_param:
            initial["meal_date"] = date_param
        if type_param:
            initial["meal_type"] = type_param
        return initial

    def form_valid(self, form):
        """Set household before saving."""
        form.instance.household = self.request.user.household
        self.request.user.message_set.create(
            message=f"Meal added: {form.instance.recipe or form.instance.custom_meal}"
        )
        # Save the meal first to get an ID
        response = super().form_valid(form)

        # Save side dishes
        self._save_side_dishes(form.instance)

        return response

    def _save_side_dishes(self, meal):
        """Save side dishes from form data."""
        # Process each side dish from POST data
        prefix = "side_dishes-"
        for key in self.request.POST:
            if key.startswith(prefix):
                # Extract index from key like "side_dishes-0-recipe"
                parts = key.split("-")
                if len(parts) >= 2:
                    try:
                        index = int(parts[1])
                    except ValueError:
                        continue

                    # Skip if marked for deletion
                    delete_key = f"{prefix}{index}-DELETE"
                    if self.request.POST.get(delete_key):
                        continue

                    recipe_id = self.request.POST.get(f"{prefix}{index}-recipe")
                    custom_side = self.request.POST.get(
                        f"{prefix}{index}-custom_side", ""
                    )
                    order = self.request.POST.get(f"{prefix}{index}-order", str(index))

                    if recipe_id or custom_side:
                        SideDish.objects.create(
                            meal_plan=meal,
                            recipe_id=recipe_id if recipe_id else None,
                            custom_side=custom_side or None,
                            order=int(order) if order else index,
                        )


class EditMealView(LoginRequiredMixin, UpdateView):
    """View for editing an existing meal."""

    model = MealPlan
    form_class = MealPlanForm
    template_name = "meal_planner/meal_form.html"
    pk_url_kwarg = "meal_id"

    def get_success_url(self):
        return reverse("meal_planner:planner")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        self.request.user.message_set.create(
            message=f"Meal updated: {form.instance.recipe or form.instance.custom_meal}"
        )
        response = super().form_valid(form)

        # Save side dishes
        self._save_side_dishes(form.instance)

        return response

    def _save_side_dishes(self, meal):
        """Save side dishes from form data - delete existing and recreate."""
        # Delete existing side dishes for this meal
        meal.side_dishes.all().delete()

        # Process each side dish from POST data
        prefix = "side_dishes-"
        for key in self.request.POST:
            if key.startswith(prefix):
                parts = key.split("-")
                if len(parts) >= 2:
                    try:
                        index = int(parts[1])
                    except ValueError:
                        continue

                    # Skip if marked for deletion
                    delete_key = f"{prefix}{index}-DELETE"
                    if self.request.POST.get(delete_key):
                        continue

                    recipe_id = self.request.POST.get(f"{prefix}{index}-recipe")
                    custom_side = self.request.POST.get(
                        f"{prefix}{index}-custom_side", ""
                    )
                    order = self.request.POST.get(f"{prefix}{index}-order", str(index))

                    if recipe_id or custom_side:
                        SideDish.objects.create(
                            meal_plan=meal,
                            recipe_id=recipe_id if recipe_id else None,
                            custom_side=custom_side or None,
                            order=int(order) if order else index,
                        )


@method_decorator(require_POST, name="dispatch")
class DeleteMealView(LoginRequiredMixin, DeleteView):
    """View for deleting a meal."""

    model = MealPlan
    pk_url_kwarg = "meal_id"

    def get_success_url(self):
        return reverse("meal_planner:planner")

    def delete(self, request, *args, **kwargs):
        meal = self.get_object()
        meal_name = meal.recipe or meal.custom_meal
        self.request.user.message_set.create(message=f"Meal deleted: {meal_name}")
        return super().delete(request, *args, **kwargs)


class RateMealView(LoginRequiredMixin, View):
    """API view for rating a meal plan entry."""

    def post(self, request, meal_id):
        meal = get_object_or_404(MealPlan, pk=meal_id, household=request.user.household)
        rating = request.POST.get("rating")

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return JsonResponse(
                    {"error": "Rating must be between 1 and 5"}, status=400
                )
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid rating value"}, status=400)

        meal.meal_rating = rating
        meal.save()

        return JsonResponse({"success": True, "rating": rating})


class RecipeSelectView(LoginRequiredMixin, View):
    """API endpoint for recipe selection dropdown."""

    def get(self, request):
        recipes = (
            request.user.household.recipes.filter(needs_review=False)
            .values("id", "title", "rating")
            .order_by("title")
        )
        return JsonResponse({"recipes": list(recipes)})


class RecipeDetailView(LoginRequiredMixin, DetailView):
    """API endpoint for recipe detail modal."""

    model = Recipe
    template_name = "meal_planner/recipe_detail_inline.html"

    def get_object(self):
        return get_object_or_404(
            Recipe, pk=self.kwargs["pk"], household=self.request.user.household
        )

    def render_to_response(self, context):
        recipe = self.get_object()
        data = {
            "id": recipe.id,
            "title": recipe.title,
            "description": recipe.description,
            "ingredients": [
                {"name": ing.name, "quantity": ing.quantity, "unit": ing.unit}
                for ing in recipe.ingredients.all()
            ],
            "instructions": [
                {"step_number": inst.step_number, "text": inst.text}
                for inst in recipe.instructions.all()
            ],
        }
        return JsonResponse(data)


def json_side_dishes(request, meal_id):
    """Return side dishes for a meal as JSON."""
    meal = get_object_or_404(MealPlan, pk=meal_id, household=request.user.household)

    side_dishes = []
    for sd in meal.side_dishes.all():
        side_dishes.append(
            {
                "id": sd.id,
                "recipe_id": sd.recipe.id if sd.recipe else None,
                "recipe_title": sd.recipe.title if sd.recipe else None,
                "custom_side": sd.custom_side,
                "order": sd.order,
            }
        )

    return JsonResponse({"side_dishes": side_dishes})
