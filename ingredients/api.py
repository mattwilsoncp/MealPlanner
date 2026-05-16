"""JSON API endpoints for ingredients."""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from ingredients.models import Ingredient


@login_required
@require_http_methods(["GET"])
def ingredient_list_api(request):
    """Return JSON list of ingredients for the household."""
    ingredients = Ingredient.objects.filter(household=request.user.household).order_by(
        "name"
    )

    data = []
    for ingredient in ingredients:
        data.append(
            {
                "id": ingredient.id,
                "name": ingredient.name,
            }
        )

    return JsonResponse({"ingredients": data})


@login_required
@require_http_methods(["GET"])
def ingredient_search_api(request):
    """Search ingredients by name."""
    q = request.GET.get("q", "").strip()

    if not q:
        return JsonResponse({"ingredients": []})

    ingredients = Ingredient.objects.filter(
        household=request.user.household, name__icontains=q
    )[:20]

    data = []
    for ingredient in ingredients:
        data.append(
            {
                "id": ingredient.id,
                "name": ingredient.name,
            }
        )

    return JsonResponse({"ingredients": data})
