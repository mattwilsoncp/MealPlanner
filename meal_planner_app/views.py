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
from django.contrib import messages

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
            # Calculate the Monday of the given ISO week
            start_date = date.fromisocalendar(year, week, 1)
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
        context["week_year"] = year
        context["week_number"] = week
        context["meal_types"] = ["breakfast", "lunch", "dinner", "snack"]

        # Get meals for this week
        meals = MealPlan.objects.filter(
            household=self.request.user.household,
            meal_date__gte=start_date,
            meal_date__lte=end_date,
        ).select_related("recipe")

        # Organize meals by date and meal type
        meals_by_day = {}
        for meal in meals:
            date_str = meal.meal_date.strftime("%Y-%m-%d")
            if date_str not in meals_by_day:
                meals_by_day[date_str] = {}
            meals_by_day[date_str][meal.meal_type] = [meal]

        # Build week_days with meals
        for day in week_days:
            date_str = day["date_str"]
            day["meals"] = meals_by_day.get(date_str, {})

        context["week_days"] = week_days

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
    year, week_num, _ = new_date.isocalendar()

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
        recipe_param = self.request.GET.get("recipe")
        if date_param:
            initial["meal_date"] = date_param
        if type_param:
            initial["meal_type"] = type_param
        if recipe_param:
            try:
                recipe = Recipe.objects.get(
                    pk=recipe_param, household=self.request.user.household
                )
                initial["recipe"] = recipe
            except Recipe.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        """Set household before saving."""
        form.instance.household = self.request.user.household
        messages.success(
            self.request,
            f"Meal added: {form.instance.recipe or form.instance.custom_meal}",
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
        messages.success(
            self.request,
            f"Meal updated: {form.instance.recipe or form.instance.custom_meal}",
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
        messages.success(self.request, f"Meal deleted: {meal_name}")
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


# On-Hand Ideas Views


class OnHandIdeasView(LoginRequiredMixin, TemplateView):
    """Display modal with on-hand idea recipes."""

    template_name = "meal_planner/on_hand_ideas.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get on-hand recipes with their ratings
        from ratings.models import Rating

        recipes = Recipe.objects.filter(
            household=self.request.user.household,
            on_hand_idea=True,
        ).order_by("title")

        # Add rating to each recipe
        on_hand_recipes = []
        for recipe in recipes:
            rating_obj = Rating.objects.filter(recipe=recipe).first()
            recipe.rating = rating_obj.rating if rating_obj else 0
            on_hand_recipes.append(recipe)

        context["on_hand_recipes"] = on_hand_recipes
        return context


class ToggleOnHandIdeaView(LoginRequiredMixin, View):
    """Toggle on_hand_idea flag on a recipe."""

    def post(self, request, recipe_id):
        recipe = get_object_or_404(
            Recipe, pk=recipe_id, household=request.user.household
        )

        recipe.on_hand_idea = not recipe.on_hand_idea
        recipe.save()

        return JsonResponse(
            {
                "success": True,
                "on_hand_idea": recipe.on_hand_idea,
            }
        )


class ToggleLeftoverWorthyView(LoginRequiredMixin, View):
    """Toggle leftover_worthy flag on a recipe."""

    def post(self, request, recipe_id):
        recipe = get_object_or_404(
            Recipe, pk=recipe_id, household=request.user.household
        )

        recipe.leftover_worthy = not recipe.leftover_worthy
        recipe.save()

        return JsonResponse(
            {
                "success": True,
                "leftover_worthy": recipe.leftover_worthy,
            }
        )


class AddOnHandToMealView(LoginRequiredMixin, View):
    """Add on-hand recipe directly to a meal slot."""

    def post(self, request):
        recipe_id = request.POST.get("recipe_id")
        meal_date = request.POST.get("meal_date")
        meal_type = request.POST.get("meal_type")

        if not all([recipe_id, meal_date, meal_type]):
            return JsonResponse({"error": "Missing required fields"}, status=400)

        recipe = get_object_or_404(
            Recipe, pk=recipe_id, household=request.user.household
        )

        # Parse date
        try:
            from datetime import datetime

            parsed_date = datetime.strptime(meal_date, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"error": "Invalid date format"}, status=400)

        # Create meal
        meal = MealPlan.objects.create(
            household=request.user.household,
            recipe=recipe,
            meal_date=parsed_date,
            meal_type=meal_type,
        )

        return JsonResponse(
            {
                "success": True,
                "meal_id": meal.id,
            }
        )


class JsonOnHandRecipesView(LoginRequiredMixin, View):
    """Return on-hand recipes as JSON for API access."""

    def get(self, request):
        recipes = (
            Recipe.objects.filter(
                household=request.user.household,
                on_hand_idea=True,
            )
            .values("id", "title", "on_hand_idea", "leftover_worthy")
            .order_by("title")
        )

        return JsonResponse({"recipes": list(recipes)})


class JsonLeftoverRecipesView(LoginRequiredMixin, View):
    """Return leftover-worthy recipes as JSON."""

    def get(self, request):
        recipes = (
            Recipe.objects.filter(
                household=request.user.household,
                leftover_worthy=True,
            )
            .values("id", "title", "leftover_worthy")
            .order_by("title")
        )

        return JsonResponse({"recipes": list(recipes)})


# Cooking Reconciliation Views


class CookingHomeView(LoginRequiredMixin, TemplateView):
    """Show meals ready to cook today."""

    template_name = "meal_planner/cooking_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from datetime import timedelta

        today = date.today()
        yesterday = today - timedelta(days=1)

        # Get meals for today or yesterday, or marked for cooking
        meals = MealPlan.objects.filter(
            household=self.request.user.household,
            meal_date__in=[today, yesterday],
        ).select_related("recipe")

        # Filter to meals with recipes
        cooking_meals = []
        for meal in meals:
            if meal.recipe:
                cooking_meals.append(
                    {
                        "id": meal.id,
                        "recipe_id": meal.recipe.id,
                        "recipe_title": meal.recipe.title,
                        "meal_date": meal.meal_date.strftime("%Y-%m-%d"),
                        "meal_type": meal.meal_type,
                        "meal_type_display": meal.get_meal_type_display(),
                    }
                )

        context["cooking_meals"] = cooking_meals
        return context


class CookingReconciliationView(LoginRequiredMixin, DetailView):
    """Show recipe ingredients vs inventory for reconciliation."""

    model = MealPlan
    template_name = "meal_planner/cooking.html"
    pk_url_kwarg = "meal_id"

    def get_object(self):
        return get_object_or_404(
            MealPlan,
            pk=self.kwargs["meal_id"],
            household=self.request.user.household,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        meal = self.get_object()

        # Get recipe ingredients
        from ingredients.models import IngredientLink

        recipe_ingredients = []
        for ing in IngredientLink.objects.filter(recipe=meal.recipe).select_related(
            "ingredient", "inventory_item"
        ):
            recipe_ingredients.append(
                {
                    "id": ing.id,
                    "ingredient_id": ing.ingredient.id,
                    "name": ing.ingredient.name,
                    "quantity": ing.quantity,
                    "unit": ing.unit,
                    "inventory_item_id": ing.inventory_item.id
                    if ing.inventory_item
                    else None,
                    "inventory_name": (
                        ing.inventory_item.name if ing.inventory_item else None
                    ),
                    "inventory_quantity": (
                        ing.inventory_item.quantity if ing.inventory_item else None
                    ),
                }
            )

        # Get household inventory items
        from inventory.models import InventoryItem

        inventory_items = InventoryItem.objects.filter(
            household=self.request.user.household
        ).order_by("name")

        inventory = []
        for item in inventory_items:
            inventory.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                }
            )

        context["recipe"] = meal.recipe
        context["recipe_ingredients"] = recipe_ingredients
        context["inventory_items"] = inventory
        context["meal_id"] = meal.id

        return context


def json_reconciliation_data(request, meal_id):
    """Return ingredients and inventory for a meal as JSON."""
    meal = get_object_or_404(MealPlan, pk=meal_id, household=request.user.household)

    if not meal.recipe:
        return JsonResponse({"error": "No recipe linked to this meal"}, status=400)

    from ingredients.models import IngredientLink

    # Get recipe ingredients
    ingredients = []
    for ing in IngredientLink.objects.filter(recipe=meal.recipe).select_related(
        "ingredient", "inventory_item"
    ):
        ingredients.append(
            {
                "id": ing.id,
                "name": ing.ingredient.name,
                "quantity": float(ing.quantity),
                "unit": ing.unit,
            }
        )

    # Get household inventory
    from inventory.models import InventoryItem

    inventory = []
    for item in InventoryItem.objects.filter(household=request.user.household):
        inventory.append(
            {
                "id": item.id,
                "name": item.name,
                "quantity": float(item.quantity),
                "unit": item.unit,
            }
        )

    return JsonResponse({"ingredients": ingredients, "inventory": inventory})


class ProcessCookingView(LoginRequiredMixin, View):
    """Process used ingredients and update inventory after cooking."""

    def post(self, request, meal_id):
        meal = get_object_or_404(MealPlan, pk=meal_id, household=request.user.household)

        if not meal.recipe:
            return JsonResponse({"error": "No recipe linked to this meal"}, status=400)

        # Get used ingredient IDs from POST
        used_ingredient_ids = request.POST.getlist("used_ingredient_ids[]")

        # Get updated inventory IDs (moved to used)
        used_inventory_ids = request.POST.getlist("used_inventory_ids[]")

        from ingredients.models import IngredientLink
        from inventory.models import InventoryItem
        from django.db import transaction

        updated_inventory = []

        with transaction.atomic():
            # Process used recipe ingredients
            for ing_id in used_ingredient_ids:
                try:
                    ing_link = IngredientLink.objects.get(id=ing_id, recipe=meal.recipe)
                    # If linked to inventory, decrement quantity
                    if ing_link.inventory_item:
                        inv_item = ing_link.inventory_item
                        inv_item.quantity -= ing_link.quantity
                        if inv_item.quantity < 0:
                            inv_item.quantity = 0
                        inv_item.save()
                        updated_inventory.append(
                            {
                                "id": inv_item.id,
                                "name": inv_item.name,
                                "quantity": float(inv_item.quantity),
                                "unit": inv_item.unit,
                            }
                        )
                except (IngredientLink.DoesNotExist, ValueError):
                    continue

            # Process inventory items moved to "used/ran out"
            for inv_id in used_inventory_ids:
                try:
                    inv_item = InventoryItem.objects.get(
                        id=inv_id, household=request.user.household
                    )
                    # Mark as used - set quantity to 0
                    inv_item.quantity = 0
                    inv_item.save()
                    updated_inventory.append(
                        {
                            "id": inv_item.id,
                            "name": inv_item.name,
                            "quantity": 0,
                            "unit": inv_item.unit,
                        }
                    )
                except (InventoryItem.DoesNotExist, ValueError):
                    continue

            # Mark meal as cooked with timestamp
            from django.utils import timezone

            # Add cooked_at field if it exists, otherwise just log it
            if hasattr(meal, "cooked_at"):
                meal.cooked_at = timezone.now()
                meal.save()

        return JsonResponse(
            {
                "success": True,
                "updated_inventory": updated_inventory,
            }
        )


class MarkIngredientUsedView(LoginRequiredMixin, View):
    """AJAX endpoint to toggle ingredient usage."""

    def post(self, request, meal_id):
        ingredient_link_id = request.POST.get("ingredient_link_id")
        is_used = request.POST.get("is_used") == "true"

        from ingredients.models import IngredientLink

        try:
            ing_link = IngredientLink.objects.get(id=ingredient_link_id)
        except IngredientLink.DoesNotExist:
            return JsonResponse({"error": "Ingredient link not found"}, status=404)

        return JsonResponse({"success": True, "is_used": is_used})
