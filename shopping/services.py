from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from ingredients.models import IngredientLink
from inventory.models import InventoryItem
from meal_planner_app.models import MealPlan

from .models import ShoppingListItem, ShoppingListWeek


TWOPLACES = Decimal("0.01")


def _normalized_key(name):
    return (name or "").strip().casefold()


def _normalize_quantity(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def compute_meal_match(recipe, inventory_items):
    ingredient_links = list(
        IngredientLink.objects.filter(recipe=recipe).select_related("ingredient")
    )
    total_count = len(ingredient_links)
    if total_count == 0:
        return {"available_count": 0, "total_count": 0, "match_percentage": 0.0}

    inventory_names = {
        _normalized_key(item.name)
        for item in inventory_items
        if item.quantity is not None and Decimal(item.quantity) > 0
    }
    available_count = sum(
        1
        for link in ingredient_links
        if _normalized_key(link.ingredient.name) in inventory_names
    )
    match_percentage = round((available_count / total_count) * 100, 2)

    return {
        "available_count": available_count,
        "total_count": total_count,
        "match_percentage": match_percentage,
    }


def generate_week_shopping_list(household, week_start, regenerate=False):
    week_end = week_start + timedelta(days=6)

    shopping_week, created = ShoppingListWeek.objects.get_or_create(
        household=household,
        week_start=week_start,
    )
    if not created and not regenerate:
        return shopping_week

    if not created:
        shopping_week.items.all().delete()

    meal_plans = (
        MealPlan.objects.filter(
            household=household,
            meal_date__gte=week_start,
            meal_date__lte=week_end,
            recipe__isnull=False,
        )
        .select_related("recipe")
        .order_by("meal_date", "id")
    )

    recipe_ids = [meal.recipe_id for meal in meal_plans if meal.recipe_id]
    if not recipe_ids:
        return shopping_week

    ingredient_links = list(
        IngredientLink.objects.filter(recipe_id__in=recipe_ids)
        .select_related("ingredient", "recipe", "inventory_item")
        .order_by("recipe_id", "order", "id")
    )

    links_by_recipe = defaultdict(list)
    for link in ingredient_links:
        links_by_recipe[link.recipe_id].append(link)

    inventory_items = InventoryItem.objects.filter(household=household)
    remaining_inventory = defaultdict(Decimal)
    inventory_category = {}
    for item in inventory_items:
        key = (_normalized_key(item.name), item.unit)
        remaining_inventory[key] += _normalize_quantity(item.quantity)
        inventory_category[key] = item.category

    aggregated = {}

    for meal in meal_plans:
        for link in links_by_recipe.get(meal.recipe_id, []):
            ingredient_key = (_normalized_key(link.ingredient.name), link.unit)
            needed = _normalize_quantity(link.quantity)
            if needed <= 0:
                continue

            available = remaining_inventory[ingredient_key]
            if available > 0:
                consumed = needed if available >= needed else available
                remaining_inventory[ingredient_key] -= consumed
                needed -= consumed

            if needed <= 0:
                continue

            aggregate_key = (
                ingredient_key[0],
                link.unit,
                (inventory_category.get(ingredient_key) or "other"),
            )
            if aggregate_key not in aggregated:
                aggregated[aggregate_key] = {
                    "name": link.ingredient.name,
                    "quantity": Decimal("0.00"),
                    "unit": link.unit,
                    "category": inventory_category.get(ingredient_key) or "other",
                    "source_recipe": link.recipe,
                }

            aggregated[aggregate_key]["quantity"] += needed

    to_create = []
    for item in aggregated.values():
        to_create.append(
            ShoppingListItem(
                shopping_week=shopping_week,
                name=item["name"],
                quantity=item["quantity"].quantize(TWOPLACES, rounding=ROUND_HALF_UP),
                unit=item["unit"],
                category=item["category"],
                source_recipe=item["source_recipe"],
            )
        )

    if to_create:
        ShoppingListItem.objects.bulk_create(to_create)

    return shopping_week
