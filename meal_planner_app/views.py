import calendar
from datetime import date, datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.core.serializers import serialize

from .models import MealPlan, MealType
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
            }
        )

    return JsonResponse({"meals": data})
