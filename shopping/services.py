from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from ingredients.models import IngredientLink
from inventory.models import InventoryItem
from meal_planner_app.models import MealPlan
from recipes.models import Recipe

from .models import ShoppingListItem, ShoppingListWeek


TWOPLACES = Decimal("0.01")


def _normalized_key(name):
    return (name or "").strip().casefold()


def _normalize_quantity(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def compute_meal_match(recipe, inventory_items, ingredient_links=None):
    if ingredient_links is None:
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


def build_discovery_matches(household, as_of_date=None):
    as_of_date = as_of_date or date.today()
    urgent_cutoff = as_of_date + timedelta(days=household.expiring_threshold_days)

    recipes = list(Recipe.objects.filter(household=household).order_by("title", "id"))
    if not recipes:
        return []

    recipe_ids = [recipe.id for recipe in recipes]
    inventory_items = list(
        InventoryItem.objects.filter(household=household).order_by("id")
    )

    ingredient_links = list(
        IngredientLink.objects.filter(
            recipe_id__in=recipe_ids, recipe__household=household
        )
        .select_related("ingredient", "recipe")
        .order_by("recipe_id", "order", "id")
    )

    links_by_recipe = defaultdict(list)
    for link in ingredient_links:
        links_by_recipe[link.recipe_id].append(link)

    available_inventory_by_name = defaultdict(list)
    for item in inventory_items:
        if item.quantity is None or Decimal(item.quantity) <= 0:
            continue
        available_inventory_by_name[_normalized_key(item.name)].append(item)

    results = []

    for recipe in recipes:
        recipe_links = links_by_recipe.get(recipe.id, [])
        match_stats = compute_meal_match(
            recipe,
            inventory_items,
            ingredient_links=recipe_links,
        )

        missing_ingredients = []
        urgent_items = []
        has_expired_match = False

        for link in recipe_links:
            ingredient_name = link.ingredient.name
            ingredient_key = _normalized_key(ingredient_name)
            matching_inventory = available_inventory_by_name.get(ingredient_key, [])

            if not matching_inventory:
                missing_ingredients.append(ingredient_name)
                continue

            for item in matching_inventory:
                if item.expiration_date is None:
                    continue
                if (
                    item.expiration_date <= urgent_cutoff
                    and item.name not in urgent_items
                ):
                    urgent_items.append(item.name)
                if item.expiration_date < as_of_date:
                    has_expired_match = True

        has_urgent_match = len(urgent_items) > 0
        results.append(
            {
                "recipe": recipe,
                "available_count": match_stats["available_count"],
                "total_count": match_stats["total_count"],
                "match_percentage": match_stats["match_percentage"],
                "missing_ingredients": missing_ingredients,
                "urgent_items": urgent_items,
                "has_expired_match": has_expired_match,
                "has_urgent_match": has_urgent_match,
            }
        )

    return sorted(
        results,
        key=lambda entry: (
            not entry["has_urgent_match"],
            -entry["match_percentage"],
            entry["recipe"].title.casefold(),
        ),
    )


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
