from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from inventory.models import InventoryItem
from recipes.models import Recipe


class DiscoveryViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Discovery Home")
        self.user = get_user_model().objects.create_user(
            username="discoverer",
            email="discoverer@example.com",
            password="pass1234",
            household=self.household,
        )

    def _create_recipe(self, title, ingredient_names):
        recipe = Recipe.objects.create(
            household=self.household,
            title=title,
            needs_review=False,
        )
        for index, ingredient_name in enumerate(ingredient_names):
            ingredient = Ingredient.objects.create(
                household=self.household,
                name=ingredient_name,
            )
            IngredientLink.objects.create(
                recipe=recipe,
                ingredient=ingredient,
                quantity=Decimal("1.00"),
                unit="piece",
                order=index,
            )
        return recipe

    def test_discovery_view_requires_authentication(self):
        response = self.client.get(reverse("shopping:discovery"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_discovery_view_context_is_sorted_urgent_first_and_includes_template_keys(
        self,
    ):
        urgent_recipe = self._create_recipe("Urgent Soup", ["Milk", "Bread"])
        regular_recipe = self._create_recipe("Regular Pasta", ["Pasta", "Tomato Sauce"])

        InventoryItem.objects.create(
            household=self.household,
            name="Milk",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="fridge",
            expiration_date=date.today() + timedelta(days=1),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Pasta",
            quantity=Decimal("1.00"),
            unit="piece",
            category="pantry",
            location="pantry",
            expiration_date=date.today() + timedelta(days=30),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Tomato Sauce",
            quantity=Decimal("1.00"),
            unit="piece",
            category="pantry",
            location="pantry",
            expiration_date=date.today() + timedelta(days=30),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("shopping:discovery"))

        self.assertEqual(response.status_code, 200)
        matches = response.context["matches"]
        self.assertEqual(matches[0]["recipe"].id, urgent_recipe.id)
        self.assertEqual(matches[1]["recipe"].id, regular_recipe.id)

        for key in ["match_percentage", "missing_ingredients", "has_urgent_match"]:
            self.assertIn(key, matches[0])

        self.assertTrue(matches[0]["has_urgent_match"])
        self.assertFalse(matches[1]["has_urgent_match"])
        self.assertIn("Bread", matches[0]["missing_ingredients"])

    def test_discovery_view_surfaces_add_to_planner_link_per_card(self):
        """Every discovery card carries an ``Add to Planner`` link
        that routes to ``meal_planner:add_meal`` pre-loaded with the
        card's recipe pk. The link uses the
        ``discovery-card-action`` class so a future CSS regression
        that accidentally hides these anchors fails loud.
        """
        import re as _re
        recipe = self._create_recipe("Addable Pasta", ["Pasta", "Tomato"])
        InventoryItem.objects.create(
            household=self.household,
            name="Pasta",
            quantity=Decimal("1.00"),
            unit="piece",
            category="pantry",
            location="pantry",
            expiration_date=date.today() + timedelta(days=30),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("shopping:discovery"))
        body = response.content.decode()

        # Each card links to meal_planner:add_meal with its recipe pk
        # so the user lands on the meal-add form pre-populated.
        add_url = reverse("meal_planner:add_meal")
        pattern = _re.compile(
            r'<a\b[^>]*class="[^"]*\bdiscovery-card-action\b[^"]*"[^>]*>'
            r'[^<]*\+ Add to Planner[^<]*</a>',
            flags=_re.DOTALL,
        )
        anchors = list(pattern.finditer(body))
        self.assertGreaterEqual(
            len(anchors), 1,
            msg="Discovery cards must surface an 'Add to Planner' link.",
        )
        # At least one anchor matches the only recipe we created.
        matched_anchor = next(
            (
                m.group(0) for m in anchors
                if f"recipe={recipe.pk}" in m.group(0)
            ),
            None,
        )
        self.assertIsNotNone(
            matched_anchor,
            msg=f"No 'Add to Planner' anchor carried recipe={recipe.pk}.",
        )
        # The anchor must point at the meal_planner:add_meal route
        # with the recipe qs param so the form is pre-loaded.
        href_match = _re.search(r'href="([^"]+)"', matched_anchor)
        self.assertIsNotNone(href_match)
        href = href_match.group(1)
        self.assertIn(add_url, href)
        self.assertIn(f"recipe={recipe.pk}", href)
        # And ``draggable="false"`` so the parent's drag handler
        # can't swallow the click.
        self.assertIn('draggable="false"', matched_anchor)

    def test_discovery_view_add_link_landing_page_accepts_recipe(self):
        """Smoke probe: hitting ``meal_planner:add_meal?recipe=<pk>``
        actually loads the meal-add form with the recipe selected,
        so the link from the discovery card does not strand the
        user on a blank page.
        """
        recipe = self._create_recipe("Landing Probe", ["Flour"])
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("meal_planner:add_meal"),
            {"recipe": recipe.pk},
        )
        self.assertEqual(response.status_code, 200)
        # The form initial contains the recipe (the get_initial
        # helper on AddMealView materializes the param into a
        # Recipe instance, then DjangoModelForm's base classes
        # surface the pk for ModelChoiceField rendering).
        initial = response.context["form"].initial
        initial_recipe = initial.get("recipe")
        # `initial_recipe` may come back as either the Recipe
        # instance itself or its pk, depending on the form's
        # model-binding — accept either.
        if hasattr(initial_recipe, "pk"):
            self.assertEqual(initial_recipe.pk, recipe.pk)
        else:
            self.assertEqual(initial_recipe, recipe.pk)
