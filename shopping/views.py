from datetime import date, datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from .models import ShoppingListItem, ShoppingListWeek
from .services import build_discovery_matches, generate_week_shopping_list


def _current_monday():
    today = date.today()
    return today - timedelta(days=today.weekday())


def _parse_week_start(raw_value):
    if not raw_value:
        return _current_monday()

    try:
        parsed = datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return _current_monday()

    return parsed - timedelta(days=parsed.weekday())


class ShoppingWeekView(LoginRequiredMixin, TemplateView):
    template_name = "shopping/shopping_week.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        week_start = _parse_week_start(self.request.GET.get("week_start"))
        household = self.request.user.household

        shopping_week = ShoppingListWeek.objects.filter(
            household=household,
            week_start=week_start,
        ).first()

        if shopping_week is None:
            shopping_week = generate_week_shopping_list(household, week_start)

        context["shopping_week"] = shopping_week
        context["shopping_items"] = shopping_week.items.all()
        context["week_start"] = week_start
        context["week_end"] = week_start + timedelta(days=6)
        context["previous_week"] = week_start - timedelta(days=7)
        context["next_week"] = week_start + timedelta(days=7)
        context["week_start_iso"] = week_start.isoformat()
        context["previous_week_iso"] = context["previous_week"].isoformat()
        context["next_week_iso"] = context["next_week"].isoformat()
        context["week_url"] = reverse("shopping:week")
        context["regenerate_week_url"] = reverse("shopping:regenerate_week")
        context["clear_week_url"] = reverse("shopping:week_clear")
        return context


class RegenerateShoppingWeekView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        week_start = _parse_week_start(request.POST.get("week_start"))
        generate_week_shopping_list(
            household=request.user.household,
            week_start=week_start,
            regenerate=True,
        )
        return redirect(
            f"{reverse('shopping:week')}?week_start={week_start.isoformat()}"
        )


class DiscoveryView(LoginRequiredMixin, TemplateView):
    template_name = "shopping/discovery.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = self.request.user.household
        matches = build_discovery_matches(household)

        context["matches"] = matches
        context["today"] = date.today()
        context["threshold_days"] = household.expiring_threshold_days
        context["urgent_count"] = sum(
            1 for match in matches if match["has_urgent_match"]
        )
        return context


class ToggleShoppingItemView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        item = get_object_or_404(
            ShoppingListItem,
            pk=item_id,
            shopping_week__household=request.user.household,
        )
        item.checked = not item.checked
        item.save(update_fields=["checked"])
        return JsonResponse({"success": True, "checked": item.checked})


class DeleteShoppingItemView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        item = get_object_or_404(
            ShoppingListItem,
            pk=item_id,
            shopping_week__household=request.user.household,
        )
        item.delete()
        return JsonResponse({"success": True, "deleted": True})


class ClearShoppingWeekView(LoginRequiredMixin, View):
    def post(self, request):
        import json
        
        # Handle both form data and JSON
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            week_start = _parse_week_start(data.get("week_start"))
        else:
            week_start = _parse_week_start(request.POST.get("week_start"))
            
        cleared_count, _ = ShoppingListItem.objects.filter(
            shopping_week__household=request.user.household,
            shopping_week__week_start=week_start,
        ).delete()
        return JsonResponse(
            {
                "success": True,
                "week_start": week_start.isoformat(),
                "cleared_count": cleared_count,
            }
        )
