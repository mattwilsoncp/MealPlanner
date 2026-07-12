#!/usr/bin/env python
"""Seed sanitized production-like test data across all apps."""

import os
import sys


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meal_planner.settings")

# Ensure project root is on Python path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

import django
django.setup()

from django.contrib.auth import get_user_model
from django.conf import settings


settings.DEBUG = False  # Non-debug mode triggers real middleware behavior
settings.ALLOWED_HOSTS = ["*"]  # Allow all hosts during QA testing


User = get_user_model()


def make_testuser():
    """Create a single production-like test user."""
    return User.objects.create_user(
        username="qa_testuser",
        email="qa@example.com",
        password="TestPass123!",  # Passes all production validators
    )


def seed_households_and_stores():
    from household.models import Household
    from inventory.models import Store, InventoryItem

    households = {}
    qa_users = list(User.objects.filter(username__startswith="qa_"))
    for user in qa_users:
        hh_name = f"{user.username.title()} Household"
        hh, created = Household.objects.get_or_create(name=hh_name)
        if not created:
            hh.refresh_from_db()  # Update the object reference
        households[user.pk] = hh
        user.household = hh
        user.save(update_fields=["household"])

    stores = []
    store_names = ["Whole Foods", "Trader Joe's", "Local Grocer", "Costco Warehouse"]
    for i, name in enumerate(store_names):
        s, created = Store.objects.get_or_create(name=name, defaults={"household": households[qa_users[0].pk]})
        if not created:
            s.refresh_from_db()  # Update the object reference
        stores.append(s)

    categories = [("produce", 1.50), ("dairy", 3.99), ("meat", 8.49), ("pantry", 2.15)]
    for i, (cat, price) in enumerate(categories):
        name = f"{cat.title()} Item {i + 1}"
        item, created = InventoryItem.objects.get_or_create(name=name, defaults={
            "category": cat, "price": price, "quantity": 5 if i < 3 else 2,
            "unit": "each", "store": stores[i % len(stores)],
            "household": households[qa_users[0].pk],  # Required field!
        })
    return households, stores


def seed_recipes():
    from recipes.models import Recipe
    from meal_planner_app.models import MealPlan

    recipe_names = [
        ("Grilled Chicken Stir Fry", "4 servings", "15 mins", 320),
        ("Spaghetti Bolognese", "6 servings", "45 mins", 580),
        ("Sheet Pan Salmon & Veggies", "2 servings", "25 mins", 420),
        ("Vegetable Curry", "4 servings", "35 mins", 310),
    ]
    recipes = []
    for name, servings, time_mins, cal in recipe_names:
        r, created = Recipe.objects.get_or_create(name=name, defaults={
            "servings": int(servings.split()[0]),
            "prep_time_minutes": int(time_mins.split()[0]),
            "calories_per_serving": cal,
            "meal_type": "Dinner", "difficulty": "Medium",
        })
        if not created:
            r.refresh_from_db()  # Update the object reference
        recipes.append(r)

    # Create meal plan weeks (production-like weekly structure)
    for week_num in range(1, 4):
        MealPlan.objects.get_or_create(date=f"2026-07-{week_num:02d}")

    return recipes


def seed_ratings():
    from ratings.models import Rating

    user = list(User.objects.filter(username__startswith="qa_"))[0]
    first_recipe = Recipe.objects.first() if Recipe.objects.exists() else None
    if first_recipe and user:
        r, created = Rating.objects.get_or_create(user=user, recipe=first_recipe, defaults={"score": 4.5})
    return len(Rating.objects.all())


def seed_inventory_links():
    from inventory.models import InventoryItemLink

    for r in Recipe.objects.all()[:3]:
        link, created = InventoryItemLink.objects.get_or_create(recipe=r, defaults={"quantity": 200})
    return len(InventoryItemLink.objects.all())


def seed_tags():
    from tags.models import Tag
    tag_names = ["Quick", "Healthy", "Dinner", "Family Favorite"]
    for name in tag_names:
        t, created = Tag.objects.get_or_create(name=name)
    return len(Tag.objects.all())


def seed_shopping_lists():
    from shopping.models import ShoppingListWeek, ShoppingListItem

    today = __import__("datetime").date.today()
    monday = today - __import__("datetime").timedelta(days=today.weekday())
    Household = __import__("household.models").models.Household
    sw, created = ShoppingListWeek.objects.get_or_create(week_start=monday)
    if not created:
        sw.refresh_from_db()  # Update the object reference

    for i in range(5):
        item, created = ShoppingListItem.objects.get_or_create(shopping_week=sw, name=f"Item {i+1}", defaults={"checked": False})


def seed_reviews():
    from reviews.models import ReviewQueue

    recipes = list(Recipe.objects.all()[:2]) if Recipe.objects.exists() else []
    for recipe in recipes:
        rev, created = ReviewQueue.objects.get_or_create(source="youtube_test", defaults={
            "source_url": f"https://example.com/watch?v=test_{recipe.pk}", "reviewed": False,
        })


def seed_preferences():
    from meal_planner_app.models import MealPreferences

    user = list(User.objects.filter(username__startswith="qa_"))[0]
    if user and not MealPreferences.objects.filter(user=user).exists():
        p, created = MealPreferences.objects.get_or_create(user=user, defaults={
            "meals_per_week": 4, "prep_time_preference": "Quick",
        })


def main():
    print("=" * 60)
    print("QA SEED DATA — Production-like sanitized test environment")
    print("=" * 60)

    # Clean existing QA data first
    count_before = User.objects.count()
    qa_users = list(User.objects.filter(username__startswith="qa_"))
    for u in qa_users:
        u.delete()
    print(f"Cleared {len(qa_users)} prior QA users (was {count_before} total)")

    # 1. Users & Households
    testuser = make_testuser()
    households, stores = seed_households_and_stores()
    print(f"\n[1/7] Users & Households: 1 user, {len(households)} household(s)")

    # 2. Stores & Inventory
    print(f"[2/7] Stores & Inventory: {len(stores)} store(s), items seeded")

    # 3. Recipes with full metadata (linked to meal plans)
    recipes = seed_recipes()
    print(f"[3/7] Recipes: {len(recipes)} recipe(s), linked to meal plan weeks")

    # 4. Meal preferences
    seed_preferences()
    print("[4/7] Meal Preferences: populated for test users")

    # 5. Ratings & inventory links
    ratings = seed_ratings()
    links = seed_inventory_links()
    print(f"[5/7] Ratings: {ratings} rating(s), inventory links: {links}")

    # 6. Tags & shopping lists & reviews
    tags = seed_tags()
    seed_shopping_lists()
    seed_reviews()
    print(f"[6/7] Tags: {tags}, Shopping Lists & Reviews seeded")

    total_users = User.objects.count()
    print("\n" + "=" * 60)
    print(f"SEED COMPLETE — {total_users} user(s), sanitized test environment ready")
    print("=" * 60)


if __name__ == "__main__":
    main()
