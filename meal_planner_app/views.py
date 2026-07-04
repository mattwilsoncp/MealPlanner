import calendar
from datetime import date, datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import Q
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
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.contrib import messages

from .models import MealPlan, MealType, SideDish, MealPreferences
from .forms import MealPlanForm, SideDishForm, MealPreferencesForm
from recipes.models import Recipe
from ingredients.models import IngredientLink
from inventory.models import InventoryItem


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
        context["planner_meal_types"] = ["breakfast", "lunch", "dinner"]

        # Get meals for this week
        meals = MealPlan.objects.filter(
            household=self.request.user.household,
            meal_date__gte=start_date,
            meal_date__lte=end_date,
        ).select_related("recipe").prefetch_related("side_dishes", "side_dishes__recipe")

        # Organize meals by date and meal type
        meals_by_day = {}
        for meal in meals:
            date_str = meal.meal_date.strftime("%Y-%m-%d")
            if date_str not in meals_by_day:
                meals_by_day[date_str] = {}
            if meal.meal_type not in meals_by_day[date_str]:
                meals_by_day[date_str][meal.meal_type] = []
            meals_by_day[date_str][meal.meal_type].append(meal)

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
        # Process each side dish from POST data — one SideDish per index
        prefix = "side_dishes-"
        seen_indexes = set()
        for key in self.request.POST:
            if key.startswith(prefix):
                # Extract index from key like "side_dishes-0-recipe"
                parts = key.split("-")
                if len(parts) >= 2:
                    try:
                        index = int(parts[1])
                    except ValueError:
                        continue

                    if index in seen_indexes:
                        continue
                    seen_indexes.add(index)

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

    def get_object(self):
        """Limit editing to current user's household only."""
        return get_object_or_404(
            MealPlan, pk=self.kwargs["meal_id"], household=self.request.user.household
        )

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

        # Process each side dish from POST data — one SideDish per index
        prefix = "side_dishes-"
        seen_indexes = set()
        for key in self.request.POST:
            if key.startswith(prefix):
                parts = key.split("-")
                if len(parts) >= 2:
                    try:
                        index = int(parts[1])
                    except ValueError:
                        continue

                    if index in seen_indexes:
                        continue
                    seen_indexes.add(index)

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

    def get_object(self):
        """Limit deletion to current user's household only."""
        return get_object_or_404(
            MealPlan, pk=self.kwargs["meal_id"], household=self.request.user.household
        )

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


class MoveMealView(LoginRequiredMixin, View):
    """API view for moving a meal plan entry to another date or meal slot."""

    def post(self, request, meal_id):
        meal = get_object_or_404(MealPlan, pk=meal_id, household=request.user.household)
        meal_date = request.POST.get("meal_date")
        meal_type = request.POST.get("meal_type")

        if not meal_date or not meal_type:
            return JsonResponse(
                {"error": "meal_date and meal_type are required"}, status=400
            )

        if meal_type not in MealType.values:
            return JsonResponse({"error": "Invalid meal type"}, status=400)

        try:
            parsed_date = datetime.strptime(meal_date, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"error": "Invalid date format"}, status=400)

        meal.meal_date = parsed_date
        meal.meal_type = meal_type

        try:
            meal.save(update_fields=["meal_date", "meal_type", "updated_at"])
        except IntegrityError:
            return JsonResponse(
                {
                    "error": "That planner slot is already taken for this meal.",
                },
                status=409,
            )

        return JsonResponse(
            {
                "success": True,
                "meal_id": meal.id,
                "meal_date": meal.meal_date.strftime("%Y-%m-%d"),
                "meal_type": meal.meal_type,
            }
        )


class RecipeSelectView(LoginRequiredMixin, View):
    """API endpoint for recipe selection dropdown."""

    def get(self, request):
        from django.db.models import Avg
        from ratings.models import Rating

        recipes = (
            request.user.household.recipes.filter(needs_review=False)
            .annotate(avg_rating=Avg("rating__score"))
            .values("id", "title", "avg_rating")
            .order_by("title")
        )
        return JsonResponse({"recipes": list(recipes)})


class RecipeExpiringMatchView(LoginRequiredMixin, View):
    """Return recipes whose ingredients match expiring inventory items."""

    def get(self, request):
        today = timezone.localdate()
        threshold = today + timedelta(days=request.user.household.expiring_threshold_days)

        # Get expiring inventory items
        expiring_items = InventoryItem.objects.filter(
            household=request.user.household,
            expiration_date__gte=today,
            expiration_date__lte=threshold,
        )
        expiring_names = {item.name.lower(): item for item in expiring_items}

        if not expiring_names:
            return JsonResponse({"recipes": []})

        # Find recipes that use any expiring ingredient
        # Match: ingredient name is a substring of inventory name OR vice versa
        # (case-insensitive, word-boundary-friendly)
        matched_recipes = []

        recipes = (
            request.user.household.recipes.filter(needs_review=False)
            .select_related()
            .prefetch_related("ingredients__ingredient")
        )

        for recipe in recipes:
            matched_ingredients = []
            for link in recipe.ingredients.all():
                ing_name = link.ingredient.name.lower()
                for inv_name, inv_item in expiring_names.items():
                    if ing_name in inv_name or inv_name in ing_name:
                        matched_ingredients.append({
                            "name": link.ingredient.name,
                            "quantity": str(link.quantity),
                            "unit": link.unit,
                            "expiration_date": inv_item.expiration_date.isoformat(),
                            "days_until_expiry": (inv_item.expiration_date - today).days,
                        })
                        break

            if matched_ingredients:
                # Sort by urgency (days until expiry)
                matched_ingredients.sort(key=lambda x: x["days_until_expiry"])
                matched_recipes.append({
                    "id": recipe.id,
                    "title": recipe.title,
                    "matched_ingredients": matched_ingredients,
                    "match_count": len(matched_ingredients),
                })

        # Sort by match count desc, then by most urgent expiry
        matched_recipes.sort(
            key=lambda r: (
                -r["match_count"],
                min(i["days_until_expiry"] for i in r["matched_ingredients"]),
            )
        )

        return JsonResponse({"recipes": matched_recipes})


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
                {"name": ing.ingredient.name, "quantity": ing.quantity, "unit": ing.unit}
                for ing in recipe.ingredients.all()
            ],
            "instructions": [
                {"step_number": inst.step_number, "text": inst.text}
                for inst in recipe.instruction_set.all()
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

        # Create or get existing meal (atomic, avoids unique constraint violation)
        meal, created = MealPlan.objects.get_or_create(
            household=request.user.household,
            recipe=recipe,
            meal_date=parsed_date,
            meal_type=meal_type,
        )

        if not created:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"'{recipe.title}' is already planned for {meal.get_meal_type_display()} on {meal_date}.",
                    "already_exists": True,
                    "meal_id": meal.id,
                },
                status=409,
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


class MealPreferencesView(LoginRequiredMixin, UpdateView):
    """View for editing meal planning preferences."""

    model = MealPreferences
    form_class = MealPreferencesForm
    template_name = "meal_planner/preferences.html"
    success_url = reverse_lazy("meal_planner:planner")

    def get_object(self, queryset=None):
        """Get existing preferences or create a new unsaved instance."""
        household = self.request.user.household
        obj, _ = MealPreferences.objects.get_or_create(household=household)
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Preferences saved")
        return super().form_valid(form)


def _normalize_meal_type(raw_type: str) -> str:
    """Normalize a meal type string to one of the valid types (breakfast/lunch/dinner/snack)."""
    raw = raw_type.lower().strip()
    for valid_type in ("breakfast", "lunch", "dinner", "snack"):
        if valid_type in raw:
            return valid_type
    return "dinner"


class GenerateAiPlanView(LoginRequiredMixin, View):
    """View for generating weekly meal plans using AI \u2014 stores in session for review."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        household = request.user.household
        week_start_str = request.POST.get("week_start")

        if not week_start_str:
            messages.error(request, "No week selected")
            return redirect("meal_planner:planner")

        try:
            start_date = date.fromisoformat(week_start_str)
            end_date = start_date + timedelta(days=6)
        except (ValueError, TypeError):
            messages.error(request, "Invalid week start date")
            return redirect("meal_planner:planner")

        # Load preferences
        try:
            preferences = MealPreferences.objects.get(household=household)
        except MealPreferences.DoesNotExist:
            messages.error(
                request, "Please save your meal preferences first before generating a plan"
            )
            return redirect("meal_planner:preferences")

        # Load inventory (non-expired items, mark near-expiry)
        inventory_items = []
        today = date.today()
        threshold_days = getattr(household, "expiring_threshold_days", 3)

        for item in InventoryItem.objects.filter(
            household=household,
        ):
            name = item.name
            expiring = False
            if item.expiration_date:
                days_until_expiry = (item.expiration_date - today).days
                expiring = 0 <= days_until_expiry <= threshold_days

            inventory_items.append({
                "name": name,
                "qty": str(item.quantity) if item.quantity else "1",
                "unit": item.unit or "",
                "expiring": expiring,
            })

        # Generate the plan
        from meal_planner_app.services.ai_service import AIService

        service = AIService()
        result = service.generate_meal_plan(
            household=household,
            start_date=start_date,
            end_date=end_date,
            preferences=preferences,
            inventory_items=inventory_items,
        )

        if not result.success:
            messages.error(request, f"AI generation failed: {result.error}")
            return redirect("meal_planner:planner_week", year=start_date.year, week=start_date.isocalendar()[1])

        # Build plan data for session (no direct DB creation)
        days = []
        for i, day_data in enumerate(result.meals):
            meal_date_str = day_data.get("date")
            try:
                meal_date = date.fromisoformat(meal_date_str)
            except (ValueError, TypeError):
                continue

            meals_for_day = []
            all_skipped = True
            for meal_data in day_data.get("meals", []):
                meal_type = _normalize_meal_type(meal_data.get("meal_type", "dinner"))
                slot_exists = MealPlan.objects.filter(
                    household=household,
                    meal_date=meal_date,
                    meal_type=meal_type,
                ).exists()
                if slot_exists:
                    continue
                all_skipped = False
                meals_for_day.append({
                    "meal_type": meal_type,
                    "title": meal_data.get("title", "AI Meal"),
                    "description": meal_data.get("description", ""),
                    "cook_time_minutes": meal_data.get("cook_time_minutes", 30),
                    "ingredients": meal_data.get("ingredients", []),
                    # Per-meal default: every suggestion is accepted until the
                    # reviewer flips it. Saving skips meals with status=="rejected".
                    "status": meal_data.get("status") or "accepted",
                })

            days.append({
                "index": i,
                "date": str(meal_date),
                "status": "skipped" if all_skipped else "pending",
                "meals": meals_for_day,
                "day_name": meal_date.strftime("%A"),
                "formatted_date": meal_date.strftime("%b %-d"),
            })

        plan_data = {
            "week_start": str(start_date),
            "days": days,
        }

        # Store in session
        session_key = f"ai_pending_plan_{household.pk}_{week_start_str}"
        request.session[session_key] = plan_data
        request.session.modified = True

        return redirect(f"{reverse('meal_planner:ai_plan_review')}?week_start={week_start_str}")


class AiPlanReviewView(LoginRequiredMixin, TemplateView):
    """View to review AI-generated meal plan before saving."""

    template_name = "meal_planner/ai_plan_review.html"

    def get(self, request, *args, **kwargs):
        week_start_str = request.GET.get("week_start")
        if not week_start_str:
            messages.error(request, "Week start date is required.")
            return redirect("meal_planner:planner")

        household = request.user.household
        session_key = f"ai_pending_plan_{household.pk}_{week_start_str}"
        plan_data = request.session.get(session_key)

        if not plan_data:
            messages.info(request, "No pending AI plan found. Generate a new one.")
            return redirect("meal_planner:planner")

        days = plan_data.get("days", [])
        if not days:
            messages.info(request, "The AI plan is empty. Generate a new one.")
            del request.session[session_key]
            request.session.modified = True
            return redirect("meal_planner:planner")

        try:
            week_start = date.fromisoformat(week_start_str)
        except (ValueError, TypeError):
            messages.error(request, "Invalid week start date.")
            return redirect("meal_planner:planner")

        week_days = [week_start + timedelta(days=i) for i in range(7)]

        accepted_count = sum(1 for d in days if d["status"] == "accepted")
        pending_count = sum(1 for d in days if d["status"] == "pending")
        rejected_count = sum(1 for d in days if d["status"] == "rejected")
        skipped_count = sum(1 for d in days if d["status"] == "skipped")

        # Build a parallel `days_with_counts` so the template can show
        # "3 of 5 accepted" on each card without re-computing in Django.
        days_with_counts = []
        for d in days:
            meals = d.get("meals") or []
            meal_accepted = sum(
                1 for m in meals if (m.get("status") or "accepted") == "accepted"
            )
            meal_rejected = sum(
                1 for m in meals if m.get("status") == "rejected"
            )
            days_with_counts.append({
                **d,
                "meal_total": len(meals),
                "meal_accepted": meal_accepted,
                "meal_rejected": meal_rejected,
            })

        context = {
            "plan": plan_data,
            "days": days_with_counts,
            "week_start": week_start,
            "week_end": week_start + timedelta(days=6),
            "week_days": week_days,
            "week_start_str": week_start_str,
            "accepted_count": accepted_count,
            "pending_count": pending_count,
            "rejected_count": rejected_count,
            "skipped_count": skipped_count,
            "total_days": len(days),
            # The Save button is enabled when *any* day is accepted. Per-meal
            # rejections are handled at save time, not at this toggle, so the
            # reviewer can flip meals even on already-accepted days.
            "has_accepted": accepted_count > 0,
        }
        return self.render_to_response(context)


class AiPlanDayActionView(LoginRequiredMixin, View):
    """View to accept/reject/regenerate a day or an individual meal.

    Supported actions:
        - ``accept`` / ``reject`` / ``regenerate`` apply to a whole day
          (and propagate meal status accordingly).
        - ``accept_meal`` / ``reject_meal`` toggle a single meal; the parent
          day's status is then re-derived from its meals so the header pill
          stays consistent.
    """

    http_method_names = ["post"]

    MEAL_ACTIONS = {"accept_meal", "reject_meal"}
    DAY_ACTIONS = {"accept", "reject", "regenerate"}

    def post(self, request, *args, **kwargs):
        week_start_str = request.POST.get("week_start")
        action = request.POST.get("action")
        day_index_str = request.POST.get("day_index")
        meal_index_str = request.POST.get("meal_index")

        if not all([week_start_str, action, day_index_str]):
            messages.error(request, "Missing required parameters.")
            return redirect("meal_planner:planner")

        try:
            day_index = int(day_index_str)
        except (ValueError, TypeError):
            messages.error(request, "Invalid day index.")
            return redirect("meal_planner:planner")

        try:
            meal_index = int(meal_index_str) if meal_index_str not in (None, "") else None
        except (ValueError, TypeError):
            messages.error(request, "Invalid meal index.")
            return redirect(f"{reverse('meal_planner:ai_plan_review')}?week_start={week_start_str}")

        review_url = f"{reverse('meal_planner:ai_plan_review')}?week_start={week_start_str}"

        household = request.user.household
        session_key = f"ai_pending_plan_{household.pk}_{week_start_str}"
        plan_data = request.session.get(session_key)

        if not plan_data:
            messages.error(request, "No pending AI plan found.")
            return redirect("meal_planner:planner")

        days = plan_data.get("days", [])
        if day_index < 0 or day_index >= len(days):
            messages.error(request, "Invalid day index.")
            return redirect(review_url)

        day = days[day_index]

        if action in self.MEAL_ACTIONS:
            ok = self._apply_meal_action(day, action, meal_index)
            if not ok:
                messages.error(request, "Invalid meal selection.")
                return redirect(review_url)
            self._reconcile_day_status(day)
            verb = "accepted" if action == "accept_meal" else "rejected"
            messages.success(request, f"Meal {verb}.")
        elif action in self.DAY_ACTIONS:
            if action == "accept":
                self._set_all_meals(day, "accepted")
                day["status"] = "accepted"
                messages.success(request, "Day accepted.")
            elif action == "reject":
                self._set_all_meals(day, "rejected")
                day["status"] = "rejected"
                messages.success(request, "Day rejected.")
            elif action == "regenerate":
                day["status"] = "pending"
                messages.success(request, "Day marked for regeneration.")
        else:
            messages.error(request, f"Unknown action: {action}")
            return redirect(review_url)

        request.session[session_key] = plan_data
        request.session.modified = True
        return redirect(review_url)

    @staticmethod
    def _apply_meal_action(day: dict, action: str, meal_index: int | None) -> bool:
        meals = day.get("meals") or []
        if meal_index is None or meal_index < 0 or meal_index >= len(meals):
            return False
        new_status = "accepted" if action == "accept_meal" else "rejected"
        meals[meal_index]["status"] = new_status
        return True

    @staticmethod
    def _set_all_meals(day: dict, status_value: str) -> None:
        for meal in day.get("meals") or []:
            meal["status"] = status_value

    @staticmethod
    def _reconcile_day_status(day: dict) -> None:
        """Recompute ``day['status']`` from its meal statuses.

        Used so that flipping a meal via the per-meal action keeps the day
        header pill in sync:
            - any meal accepted  → day "accepted"
            - all meals rejected → day "rejected"
            - mixed without accepted → day "pending"
        Empty days stay where they were; ``skipped`` is never introduced
        here (that's set by ``GenerateAiPlanView`` when slots are full).
        """
        if day.get("status") == "skipped":
            return  # Skipped-day sentinel is owned by the generator; don't churn it.
        meals = day.get("meals") or []
        if not meals:
            # No meals to derive from — leave the day where it was unless it
            # was 'accepted' (which would mislead the reviewer).
            if day.get("status") == "accepted":
                day["status"] = "pending"
            return
        statuses = {m.get("status", "accepted") for m in meals}
        if "accepted" in statuses:
            day["status"] = "accepted"
        elif statuses == {"rejected"}:
            day["status"] = "rejected"
        else:
            day["status"] = "pending"


class AiPlanSaveView(LoginRequiredMixin, View):
    """View to save accepted meals from the AI plan to MealPlan records.

    Honors per-meal status: a day's ``status`` is treated as the user's
    coarse-grained intent (``accepted`` → save everything, ``rejected`` →
    save nothing) but individual meals may have been flipped via the
    per-meal action, in which case only ``accepted`` meals land in the
    planner. ``skipped`` days and rejected meals are skipped silently.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        week_start_str = request.POST.get("week_start")
        if not week_start_str:
            messages.error(request, "Week start date is required.")
            return redirect("meal_planner:planner")

        household = request.user.household
        session_key = f"ai_pending_plan_{household.pk}_{week_start_str}"
        plan_data = request.session.get(session_key)

        if not plan_data:
            messages.error(request, "No pending AI plan found.")
            return redirect("meal_planner:planner")

        days = plan_data.get("days", [])
        candidate_days = [d for d in days if d.get("status") == "accepted"]

        if not candidate_days:
            messages.info(request, "No accepted days to save.")
            return redirect(f"{reverse('meal_planner:ai_plan_review')}?week_start={week_start_str}")

        created_count = 0
        for day in candidate_days:
            meal_date_str = day.get("date")
            try:
                meal_date = date.fromisoformat(meal_date_str)
            except (ValueError, TypeError):
                continue

            for meal_data in day.get("meals", []):
                # Per-meal guard: a meal the reviewer individually rejected
                # is skipped, even when the parent day is accepted.
                if meal_data.get("status") == "rejected":
                    continue

                meal_type = _normalize_meal_type(meal_data.get("meal_type", "dinner"))

                slot_exists = MealPlan.objects.filter(
                    household=household,
                    meal_date=meal_date,
                    meal_type=meal_type,
                ).exists()
                if slot_exists:
                    continue

                title = meal_data.get("title", "AI Meal")
                description = meal_data.get("description", "")
                cook_time = meal_data.get("cook_time_minutes", 30)

                MealPlan.objects.create(
                    household=household,
                    meal_date=meal_date,
                    meal_type=meal_type,
                    custom_meal=f"{title}: {description}".strip(": ")[:500],
                    notes=f"AI-generated | Cook time: {cook_time} min",
                    ingredients=meal_data.get("ingredients", []),
                )
                created_count += 1

        del request.session[session_key]
        request.session.modified = True
        if created_count > 0:
            messages.success(
                request,
                f"Saved {created_count} AI-generated meals! "
                f"Check your Shopping List for missing ingredients.",
            )
        else:
            messages.info(request, "No new meals were saved (slots may already be filled).")

        return redirect("meal_planner:planner")


class AiPlanCancelView(LoginRequiredMixin, View):
    """View to cancel the AI plan review and discard all pending data."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        week_start_str = request.POST.get("week_start")
        household = request.user.household

        if week_start_str:
            session_key = f"ai_pending_plan_{household.pk}_{week_start_str}"
            if session_key in request.session:
                del request.session[session_key]
                request.session.modified = True

        messages.info(request, "AI plan review cancelled.")
        return redirect("meal_planner:planner")


class AIModelsSettingsView(LoginRequiredMixin, TemplateView):
    """Per-household AI model picker, fed from the live OpenRouter catalog."""

    template_name = "settings/ai_models.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import AISettings
        from .services.ai_settings import (
            FEATURE_KEYS,
            OpenRouterCatalog,
            resolve_openrouter_api_key,
        )

        household = self.request.user.household
        settings_row, _ = AISettings.objects.get_or_create(household=household)

        refresh = self.request.GET.get("refresh") == "1"

        # Always include both groups in the sidebar badges so the counts are
        # known without per-feature fetches; the dropdown population happens
        # lazily below so a single feature-key bug doesn't blank the page.
        try:
            all_models = OpenRouterCatalog.fetch(force_refresh=refresh)
        except Exception as exc:  # pragma: no cover - upstream blip
            messages.warning(
                self.request,
                f"Could not reach the OpenRouter catalog ({exc}). "
                "Showing the last known snapshot or — on first visit — nothing.",
            )
            all_models = []

        features: list[dict] = []
        for feature_key, spec in FEATURE_KEYS.items():
            if spec["needs_image"]:
                eligible = [m for m in all_models if m.supports_image_input]
            else:
                eligible = list(all_models)
            binding = settings_row.get_model(feature_key)
            current_model_id = binding["model_id"] if binding else ""
            free_count = sum(1 for m in eligible if m.is_free)
            features.append(
                {
                    "key": feature_key,
                    "label": spec["label"],
                    "help": spec["help"],
                    "needs_image": spec["needs_image"],
                    "default_model": spec["default_model"],
                    "current_model_id": current_model_id,
                    "options": eligible,
                    "free_count": free_count,
                    "paid_count": len(eligible) - free_count,
                }
            )

        context.update(
            {
                "features": features,
                "catalog_size": len(all_models),
                "env_api_key_set": bool(resolve_openrouter_api_key(None)),
                "override_api_key": settings_row.openrouter_api_key_override or "",
                "override_usda_api_key": settings_row.usda_fdc_api_key_override or "",
                "refreshed": refresh,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        from .models import AISettings
        from .services.ai_settings import FEATURE_KEYS, OpenRouterCatalog

        household = request.user.household
        settings_row, _ = AISettings.objects.get_or_create(household=household)

        # Catalog lookup so we can stamp the saved label + reject unknown IDs.
        all_models = OpenRouterCatalog.fetch()
        by_id = {m.id: m for m in all_models}

        saved: list[str] = []
        cleared: list[str] = []
        for feature_key, spec in FEATURE_KEYS.items():
            raw = (request.POST.get(f"model_{feature_key}") or "").strip()
            if not raw:
                # Empty dropdown: remove any saved binding so the baked-in
                # default applies. We don't persist an "empty" record.
                if settings_row.get_model(feature_key) is not None:
                    bindings = dict(settings_row.model_bindings or {})
                    bindings.pop(feature_key, None)
                    settings_row.model_bindings = bindings
                    settings_row.save(
                        update_fields=["model_bindings", "updated_at"]
                    )
                    cleared.append(feature_key)
                continue
            model = by_id.get(raw)
            if model is None:
                # Unknown id — keep the previous value, surface a soft message.
                messages.warning(
                    request,
                    f"'{raw}' is not in the current OpenRouter catalog, "
                    f"so {spec['label']} was left unchanged.",
                )
                continue
            if spec["needs_image"] and not model.supports_image_input:
                messages.warning(
                    request,
                    f"'{model.name}' does not accept image input, so it "
                    f"can't be used for {spec['label']}. Keeping the prior model.",
                )
                continue
            settings_row.set_model(feature_key, model.id, model.name)
            saved.append(feature_key)

        override = (request.POST.get("openrouter_api_key_override") or "").strip()
        previous_override = settings_row.openrouter_api_key_override or ""
        openrouter_changed = override != previous_override
        if openrouter_changed:
            settings_row.openrouter_api_key_override = override
            settings_row.save(update_fields=["openrouter_api_key_override", "updated_at"])

        usda_override = (
            request.POST.get("usda_fdc_api_key_override") or ""
        ).strip()
        previous_usda_override = settings_row.usda_fdc_api_key_override or ""
        usda_changed = usda_override != previous_usda_override
        if usda_changed:
            settings_row.usda_fdc_api_key_override = usda_override
            settings_row.save(
                update_fields=["usda_fdc_api_key_override", "updated_at"]
            )

        if saved or cleared:
            parts: list[str] = []
            if saved:
                parts.append(
                    f"updated {len(saved)} feature{'s' if len(saved) != 1 else ''}: "
                    f"{', '.join(saved)}"
                )
            if cleared:
                parts.append(
                    f"reset {len(cleared)} feature{'s' if len(cleared) != 1 else ''} "
                    f"to the default: {', '.join(cleared)}"
                )
            messages.success(request, "AI settings saved — " + "; ".join(parts) + ".")
        elif openrouter_changed or usda_changed:
            parts = []
            if openrouter_changed:
                parts.append("OpenRouter key")
            if usda_changed:
                parts.append("USDA FDC key")
            messages.success(request, "API key(s) saved — " + ", ".join(parts) + ".")
        else:
            messages.info(request, "No AI model changes submitted.")

        return redirect("meal_planner:ai_models_settings")
