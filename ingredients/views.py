from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponseNotFound
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from ingredients.models import Ingredient
from ingredients.services.usda import USFACatalog, USDAMatch, USDAAPIError, resolve_usda_api_key


@login_required
@require_http_methods(["GET", "POST"])
def ingredient_usda_link_view(request, pk: int):
    """Search the USDA FoodData Central catalog, let the user pick a match,
    and persist the linked ID + macro snapshot back to the Ingredient row.

    Per-household scoping is enforced by the GET/POST handler — a
    cross-household ingredient id returns 404 rather than leaking. The
    service module owns caching, error mapping, and key resolution.
    """
    household = getattr(request.user, "household", None)
    if household is None:
        return HttpResponseNotFound("No household for user")

    ingredient = get_object_or_404(Ingredient, pk=pk, household=household)

    if request.method == "POST":
        return _handle_confirm(request, ingredient)

    return _handle_search(request, ingredient, household)


def _handle_search(request, ingredient, household):
    query = (request.GET.get("q") or "").strip()
    matches = []
    api_error = None
    if query:
        try:
            matches = USFACatalog.search(
                query,
                api_key=resolve_usda_api_key(household),
                data_types=None,
                page_size=10,
            )
        except USDAAPIError as exc:
            api_error = str(exc)

    context = {
        "ingredient": ingredient,
        "query": query,
        "matches": matches,
        "api_error": api_error,
        "linked": bool(ingredient.usda_food_id),
    }
    return render(request, "ingredients/usda_link.html", context)


def _handle_confirm(request, ingredient):
    try:
        fdc_id = int(request.POST.get("fdc_id") or 0)
    except (TypeError, ValueError):
        fdc_id = 0
    if fdc_id <= 0:
        messages.error(request, "Pick a USDA match before confirming.")
        return HttpResponseRedirect(_build_search_redirect(request, ingredient))

    description = (request.POST.get("description") or "").strip()
    data_type = (request.POST.get("data_type") or "").strip()

    # Re-validate macros server-side; never trust the hidden form fields
    # because they could be edited by the client before posting.
    household = getattr(request.user, "household", None)
    try:
        matches = USFACatalog.search(
            description or ingredient.name,
            api_key=resolve_usda_api_key(household),
            page_size=25,
        )
    except USDAAPIError:
        matches = []
    target = next((m for m in matches if m.fdc_id == fdc_id), None)

    if target is None:
        # Fall back to writing the description + id verbatim and let the
        # user re-look-up the macros later. We never invent numbers.
        ingredient.usda_food_id = str(fdc_id)
        ingredient.save(update_fields=["usda_food_id"])
        messages.warning(
            request,
            f"Linked USDA id {fdc_id} but could not re-fetch macros right now.",
        )
        if description:
            messages.info(request, f"Linked: {description}")
    else:
        ingredient.usda_food_id = str(target.fdc_id)
        ingredient.calories_kcal = target.calories_kcal
        ingredient.protein_g = target.protein_g
        ingredient.carbs_g = target.carbs_g
        ingredient.fat_g = target.fat_g
        ingredient.save(
            update_fields=[
                "usda_food_id",
                "calories_kcal",
                "protein_g",
                "carbs_g",
                "fat_g",
            ]
        )
        messages.success(
            request,
            f"Linked {ingredient.name} to USDA entry {target.fdc_id} ({target.description}).",
        )
        if data_type:
            messages.info(request, f"Dataset: {data_type}")

    back = request.META.get("HTTP_REFERER") or ""
    if back and "/ingredients/" not in back:
        return HttpResponseRedirect(back)
    return HttpResponseRedirect(reverse("recipes:recipe_list"))


def _build_search_redirect(request, ingredient):
    q = (request.POST.get("q") or request.GET.get("q") or "").strip()
    base = reverse("ingredients:link_usda", args=[ingredient.pk])
    return f"{base}?q={q}" if q else base

