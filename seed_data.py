#!/usr/bin/env python
"""
Seed the meal planner DB with realistic inventory, recipes, and a meal plan.

Run from the project root:
    source .venv/bin/activate
    python seed_data.py

Clears existing inventory/recipes for the household before seeding.
"""
import os
import sys
from datetime import date, timedelta

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meal_planner.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.contrib.auth import get_user_model
from household.models import Household
from inventory.models import InventoryItem
from recipes.models import Recipe
from ingredients.models import Ingredient, IngredientLink
from instructions.models import Instruction
from tags.models import Tag
from ratings.models import Rating
from meal_planner_app.models import MealPlan, MealType
from shopping.models import ShoppingListWeek, ShoppingListItem

User = get_user_model()

TODAY = date.today()

# ── Helpers ──────────────────────────────────────────────────────────────────

def ndays(days: int) -> date:
    return TODAY + timedelta(days=days)


def clear_household(household):
    """Wipe all user-scoped data for a fresh seed."""
    from ingredients.models import IngredientLink
    from instructions.models import Instruction
    from tags.models import RecipeTag

    InventoryItem.objects.filter(household=household).delete()
    for recipe in Recipe.objects.filter(household=household):
        IngredientLink.objects.filter(recipe=recipe).delete()
        Instruction.objects.filter(recipe=recipe).delete()
        RecipeTag.objects.filter(recipe=recipe).delete()
        recipe.rating_set.all().delete()
    Recipe.objects.filter(household=household).delete()
    Tag.objects.filter(household=household).delete()
    MealPlan.objects.filter(household=household).delete()
    ShoppingListWeek.objects.filter(household=household).delete()
    print(f"  Cleared existing data for household '{household.name}'")


# ── Inventory ─────────────────────────────────────────────────────────────────

INVENTORY = [
    # Expiring TODAY — urgent
    {"name": "Baby Spinach",       "qty": 5,  "unit": "oz",     "category": "produce",   "location": "refrigerator", "expiration_date": TODAY},
    {"name": "Half-and-Half",      "qty": 1,  "unit": "cup",    "category": "dairy",     "location": "refrigerator", "expiration_date": TODAY},
    {"name": "Ground Beef",        "qty": 1,  "unit": "lb",     "category": "meat",      "location": "refrigerator", "expiration_date": TODAY},

    # Expiring TOMORROW
    {"name": "Chicken Thighs",     "qty": 2,  "unit": "lb",     "category": "meat",      "location": "refrigerator", "expiration_date": ndays(1)},
    {"name": "Greek Yogurt",       "qty": 1,  "unit": "cup",    "category": "dairy",     "location": "refrigerator", "expiration_date": ndays(1)},
    {"name": "Cherry Tomatoes",    "qty": 1,  "unit": "lb",     "category": "produce",   "location": "counter",      "expiration_date": ndays(1)},

    # Expiring in 3–4 days
    {"name": "Salmon Fillet",      "qty": 1,  "unit": "lb",     "category": "meat",      "location": "refrigerator", "expiration_date": ndays(3)},
    {"name": "Cucumber",           "qty": 2,  "unit": "piece",  "category": "produce",   "location": "refrigerator", "expiration_date": ndays(3)},
    {"name": "Feta Cheese",        "qty": 4,  "unit": "oz",     "category": "dairy",     "location": "refrigerator", "expiration_date": ndays(4)},
    {"name": "Rice",               "qty": 2,  "unit": "lb",     "category": "pantry",    "location": "pantry",      "expiration_date": ndays(4)},

    # Expiring in 7+ days / no expiry
    {"name": "Eggs",               "qty": 12, "unit": "piece",  "category": "dairy",     "location": "refrigerator", "expiration_date": ndays(10)},
    {"name": "Butter",             "qty": 1,  "unit": "lb",     "category": "dairy",     "location": "refrigerator", "expiration_date": ndays(14)},
    {"name": "Olive Oil",          "qty": 1,  "unit": "l",      "category": "pantry",    "location": "pantry",      "expiration_date": None},
    {"name": "Soy Sauce",         "qty": 1,  "unit": "cup",    "category": "condiments", "location": "pantry",     "expiration_date": None},
    {"name": "Garlic",            "qty": 1,  "unit": "head",   "category": "produce",   "location": "counter",      "expiration_date": ndays(12)},
    {"name": "Onion",             "qty": 3,  "unit": "piece",  "category": "produce",   "location": "pantry",      "expiration_date": ndays(20)},
    {"name": "Canned Tomatoes",   "qty": 2,  "unit": "can",    "category": "pantry",    "location": "pantry",      "expiration_date": ndays(365)},
    {"name": "Pasta",             "qty": 1,  "unit": "lb",     "category": "pantry",    "location": "pantry",      "expiration_date": None},
    {"name": "Bread",             "qty": 1,  "unit": "loaf",   "category": "bakery",    "location": "counter",      "expiration_date": ndays(5)},
    {"name": "Milk",              "qty": 1,  "unit": "l",      "category": "dairy",    "location": "refrigerator", "expiration_date": ndays(6)},
]

# ── Recipes ───────────────────────────────────────────────────────────────────

RECIPES = [
    {
        "title": "Salmon with Rice and Roasted Vegetables",
        "description": "Simple sheet-pan salmon with rice and whatever vegetables need using.",
        "tag_names": ["dinner", "healthy", "one-pan"],
        "ingredients": [
            ("Salmon Fillet", 1, "lb"),
            ("Rice", 1, "cup"),
            ("Cherry Tomatoes", 0.5, "lb"),
            ("Olive Oil", 2, "tbsp"),
            ("Garlic", 1, "clove"),
        ],
        "instructions": [
            "Heat oven to 400°F.",
            "Season salmon with salt, pepper, and a squeeze of lemon.",
            "Toss tomatoes with olive oil, salt, and garlic.",
            "Bake salmon and tomatoes for 18–22 minutes.",
            "Cook rice according to package directions.",
            "Serve salmon over rice with roasted tomatoes.",
        ],
        "rating": 4.5,
        "on_hand": False,
        "leftover_worthy": False,
    },
    {
        "title": "Greek Salad with Chicken Thighs",
        "description": "Grilled chicken over a bright cucumber and feta salad with a lemon-oregano dressing.",
        "tag_names": ["lunch", "healthy", "high-protein"],
        "ingredients": [
            ("Chicken Thighs", 1, "lb"),
            ("Cucumber", 1, "piece"),
            ("Cherry Tomatoes", 0.5, "lb"),
            ("Feta Cheese", 2, "oz"),
            ("Olive Oil", 3, "tbsp"),
        ],
        "instructions": [
            "Season chicken thighs with oregano, salt, and pepper.",
            "Grill or pan-sear chicken until cooked through, about 6 min per side.",
            "Slice cucumber and halve tomatoes.",
            "Toss vegetables with olive oil, lemon juice, and oregano.",
            "Top with crumbled feta and sliced chicken.",
        ],
        "rating": 4.2,
        "on_hand": True,
        "leftover_worthy": True,
    },
    {
        "title": "Beef and Vegetable Stir Fry",
        "description": "Quick weeknight stir fry with ground beef, whatever vegetables are in the fridge, and soy sauce.",
        "tag_names": ["dinner", "quick", "high-protein"],
        "ingredients": [
            ("Ground Beef", 1, "lb"),
            ("Baby Spinach", 2, "oz"),
            ("Cucumber", 1, "piece"),
            ("Soy Sauce", 3, "tbsp"),
            ("Rice", 1, "cup"),
            ("Garlic", 1, "clove"),
        ],
        "instructions": [
            "Cook rice according to package directions.",
            "Brown ground beef in a hot wok or skillet.",
            "Add sliced cucumber and stir fry 2 minutes.",
            "Toss in spinach and garlic, cook until wilted.",
            "Add soy sauce and toss everything together.",
            "Serve over rice.",
        ],
        "rating": 4.0,
        "on_hand": True,
        "leftover_worthy": True,
    },
    {
        "title": "Tomato and Feta Pasta",
        "description": "Roasted cherry tomatoes and crumbled feta over penne with olive oil and garlic.",
        "tag_names": ["dinner", "vegetarian", "quick"],
        "ingredients": [
            ("Cherry Tomatoes", 1, "lb"),
            ("Feta Cheese", 4, "oz"),
            ("Pasta", 1, "lb"),
            ("Olive Oil", 3, "tbsp"),
            ("Garlic", 2, "clove"),
        ],
        "instructions": [
            "Roast cherry tomatoes with olive oil and garlic at 425°F for 20 min.",
            "Cook pasta according to package directions.",
            "Toss hot pasta with roasted tomatoes, juices, and feta.",
            "Season with salt, pepper, and fresh basil if available.",
        ],
        "rating": 4.3,
        "on_hand": False,
        "leftover_worthy": False,
    },
    {
        "title": "Overnight Oats",
        "description": "Greek yogurt and oats soaked overnight — grab-and-go breakfast.",
        "tag_names": ["breakfast", "meal-prep", "vegetarian"],
        "ingredients": [
            ("Greek Yogurt", 0.5, "cup"),
            ("Rice", 0.25, "cup"),
            ("Milk", 0.5, "cup"),
            ("Baby Spinach", 1, "oz"),
        ],
        "instructions": [
            "Combine oats, yogurt, and milk in a jar.",
            "Refrigerate overnight.",
            "Eat cold in the morning — optionally heat if preferred.",
        ],
        "rating": 3.8,
        "on_hand": True,
        "leftover_worthy": False,
    },
    {
        "title": "Shakshuka",
        "description": "Eggs poached in a spiced tomato and bell pepper sauce. Great for using up half cans of tomatoes.",
        "tag_names": ["breakfast", "dinner", "vegetarian"],
        "ingredients": [
            ("Canned Tomatoes", 1, "can"),
            ("Eggs", 4, "piece"),
            ("Onion", 1, "piece"),
            ("Garlic", 2, "clove"),
            ("Olive Oil", 2, "tbsp"),
        ],
        "instructions": [
            "Sauté diced onion in olive oil until soft.",
            "Add garlic and cumin, cook 1 minute.",
            "Pour in canned tomatoes, season with salt, pepper, and paprika.",
            "Simmer 10 minutes until thickened.",
            "Create wells in the sauce, crack in eggs, cover and cook 8 min.",
            "Serve with bread.",
        ],
        "rating": 4.6,
        "on_hand": False,
        "leftover_worthy": False,
    },
    {
        "title": "Buttered Eggs and Toast",
        "description": "Classic simple breakfast — fried eggs with buttered toast.",
        "tag_names": ["breakfast"],
        "ingredients": [
            ("Eggs", 2, "piece"),
            ("Butter", 1, "tbsp"),
            ("Bread", 2, "slice"),
        ],
        "instructions": [
            "Butter bread and toast under broiler.",
            "Fry eggs in butter over medium heat until whites set.",
            "Season with salt and pepper, serve with toast.",
        ],
        "rating": 4.0,
        "on_hand": True,
        "leftover_worthy": False,
    },
    {
        "title": "Garlic Butter Salmon",
        "description": "Pan-seared salmon with a garlic butter sauce — on the table in 20 minutes.",
        "tag_names": ["dinner", "healthy", "quick"],
        "ingredients": [
            ("Salmon Fillet", 0.5, "lb"),
            ("Butter", 2, "tbsp"),
            ("Garlic", 3, "clove"),
            ("Olive Oil", 1, "tbsp"),
        ],
        "instructions": [
            "Pat salmon dry, season with salt and pepper.",
            "Sear skin-side down in hot oil 4 min, flip.",
            "Add butter and garlic to pan, baste salmon 3 more min.",
            "Serve immediately with pan juices.",
        ],
        "rating": 4.7,
        "on_hand": False,
        "leftover_worthy": False,
    },
    {
        "title": " Cucumber Feta Salad",
        "description": "Refreshing cucumber and feta salad with red onion, olives, and lemon.",
        "tag_names": ["lunch", "side", "vegetarian"],
        "ingredients": [
            ("Cucumber", 2, "piece"),
            ("Feta Cheese", 4, "oz"),
            ("Olive Oil", 2, "tbsp"),
        ],
        "instructions": [
            "Slice cucumbers thinly.",
            "Combine with crumbled feta and red onion.",
            "Dress with olive oil, lemon juice, salt, and oregano.",
            "Serve chilled.",
        ],
        "rating": 4.1,
        "on_hand": True,
        "leftover_worthy": False,
    },
    {
        "title": "Canned Tomato Soup",
        "description": "Elevated tomato soup from a can — garlic, cream, and fresh basil.",
        "tag_names": ["lunch", "dinner", "vegetarian"],
        "ingredients": [
            ("Canned Tomatoes", 2, "can"),
            ("Butter", 2, "tbsp"),
            ("Garlic", 3, "clove"),
            ("Onion", 1, "piece"),
            ("Bread", 2, "slice"),
        ],
        "instructions": [
            "Sauté onion and garlic in butter until soft.",
            "Add canned tomatoes, simmer 15 minutes.",
            "Blend until smooth (or leave chunky).",
            "Season with salt, pepper, and a pinch of sugar.",
            "Serve with grilled cheese or crusty bread.",
        ],
        "rating": 4.2,
        "on_hand": False,
        "leftover_worthy": False,
    },
]

# ── Meal plan: this week ──────────────────────────────────────────────────────

MEAL_PLAN = [
    # Monday
    (ndays(0),  "breakfast", "Buttered Eggs and Toast",     None),
    (ndays(0),  "lunch",     "Greek Salad with Chicken Thighs", "Greek Salad with Chicken Thighs"),
    (ndays(0),  "dinner",    "Beef and Vegetable Stir Fry", None),

    # Tuesday
    (ndays(1),  "breakfast", "Overnight Oats",               None),
    (ndays(1),  "lunch",     "Cucumber Feta Salad",           None),
    (ndays(1),  "dinner",    "Tomato and Feta Pasta",         None),

    # Wednesday
    (ndays(2),  "breakfast", "Shakshuka",                    None),
    (ndays(2),  "lunch",     "Canned Tomato Soup",            None),
    (ndays(2),  "dinner",    "Garlic Butter Salmon",          None),

    # Thursday
    (ndays(3),  "breakfast", "Overnight Oats",               None),
    (ndays(3),  "lunch",     "Greek Salad with Chicken Thighs", None),
    (ndays(3),  "dinner",    "Salmon with Rice and Roasted Vegetables", None),

    # Friday
    (ndays(4),  "breakfast", "Shakshuka",                    None),
    (ndays(4),  "lunch",     "Beef and Vegetable Stir Fry",   None),
    (ndays(4),  "dinner",    None,                           "Pizza Night (takeout)"),

    # Saturday
    (ndays(5),  "breakfast", "Buttered Eggs and Toast",     None),
    (ndays(5),  "lunch",     "Cucumber Feta Salad",           None),
    (ndays(5),  "dinner",    "Tomato and Feta Pasta",         None),

    # Sunday
    (ndays(6),  "breakfast", "Overnight Oats",               None),
    (ndays(6),  "lunch",     "Canned Tomato Soup",            None),
    (ndays(6),  "dinner",    None,                           "Roast Chicken (whole)"),
]


# ── Main ──────────────────────────────────────────────────────────────────────

def seed(household):
    clear_household(household)

    # ── Inventory ──
    print("  Seeding inventory...")
    for item in INVENTORY:
        InventoryItem.objects.create(
            household=household,
            name=item["name"],
            quantity=item["qty"],
            unit=item["unit"],
            category=item["category"],
            location=item["location"],
            expiration_date=item["expiration_date"],
        )
    print(f"    {len(INVENTORY)} inventory items")

    # ── Recipes ──
    print("  Seeding recipes...")
    recipe_map = {}  # title → Recipe instance

    for recipe_data in RECIPES:
        tag_names = recipe_data.pop("tag_names")
        ingredients_raw = recipe_data.pop("ingredients")
        instructions_raw = recipe_data.pop("instructions")
        rating_value = recipe_data.pop("rating")
        on_hand = recipe_data.pop("on_hand")
        leftover = recipe_data.pop("leftover_worthy")

        recipe = Recipe.objects.create(
            household=household,
            needs_review=False,
            on_hand_idea=on_hand,
            leftover_worthy=leftover,
            **recipe_data,
        )
        recipe_map[recipe.title] = recipe

        # Tags
        for tag_name in tag_names:
            from tags.models import RecipeTag
            tag, _ = Tag.objects.get_or_create(
                household=household,
                name=tag_name,
            )
            RecipeTag.objects.get_or_create(recipe=recipe, tag=tag)

        # Ingredients
        for idx, (name, qty, unit) in enumerate(ingredients_raw):
            ing, _ = Ingredient.objects.get_or_create(
                household=household,
                name=name,
            )
            IngredientLink.objects.create(
                recipe=recipe,
                ingredient=ing,
                quantity=qty,
                unit=unit,
                order=idx,
            )

        # Instructions
        for idx, text in enumerate(instructions_raw):
            Instruction.objects.create(
                recipe=recipe,
                step_number=idx + 1,
                text=text,
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Rating — use the first superuser in the household if available
        if rating_value:
            user = User.objects.filter(
                household=household, is_superuser=True
            ).first() or User.objects.filter(household=household).first()
            if user:
                Rating.objects.create(
                    recipe=recipe,
                    user=user,
                    score=rating_value,
                )

    print(f"    {len(RECIPES)} recipes")

    # ── Meal Plan ──
    print("  Seeding meal plan...")
    meals_created = 0
    for meal_date, meal_type, recipe_title, custom_meal in MEAL_PLAN:
        kwargs = {
            "household": household,
            "meal_date": meal_date,
            "meal_type": meal_type,
        }
        if recipe_title and recipe_title in recipe_map:
            kwargs["recipe"] = recipe_map[recipe_title]
        else:
            kwargs["custom_meal"] = custom_meal

        MealPlan.objects.create(**kwargs)
        meals_created += 1

    print(f"    {meals_created} meal entries")


def main():
    print("\n=== Meal Planner Seed Data ===\n")

    household_name = input("Household name [My Household]: ").strip()
    if not household_name:
        household_name = "My Household"

    household, created = Household.objects.get_or_create(name=household_name)
    if created:
        print(f"  Created household: {household_name}")
    else:
        print(f"  Using existing household: {household_name}")

    # Ensure at least one superuser exists
    if not User.objects.filter(is_superuser=True).exists():
        print("  No superuser found — create one first with:")
        print("    python manage.py createsuperuser")
        return

    seed(household)
    print("\n  Done! Start the server and open /meal/add/ to see 'Use Before It Spoils'.\n")


if __name__ == "__main__":
    main()