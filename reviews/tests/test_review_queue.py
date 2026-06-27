from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.models import Ingredient, IngredientLink
from inventory.models import InventoryItem
from recipes.models import Recipe


class ReviewQueueTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Queue Household")
        self.user = user_model.objects.create_user(
            username="queue-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Review Me",
            needs_review=True,
        )
        ingredient = Ingredient.objects.create(
            household=self.household,
            name="Tomato",
        )
        self.link = IngredientLink.objects.create(
            recipe=self.recipe,
            ingredient=ingredient,
            quantity=Decimal("1.00"),
            unit="piece",
            order=0,
        )

    def test_review_queue_and_reconcile_views_render(self):
        queue_response = self.client.get(reverse("reviews:review_queue"))
        reconcile_response = self.client.get(
            reverse("reviews:recipe_reconcile", args=[self.recipe.id])
        )

        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(reconcile_response.status_code, 200)
        self.assertContains(reconcile_response, "Link To")
        self.assertContains(reconcile_response, "Quick Add Inventory Item")
        self.assertContains(reconcile_response, "x-data=\"reconciliation()\"")

    def test_reconciliation_saves_inventory_link(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="Tomato Bin",
            quantity=Decimal("2.00"),
            unit="piece",
            category="produce",
            location="refrigerator",
        )

        response = self.client.post(
            reverse("reviews:save_reconciliation", args=[self.recipe.id]),
            data={f"inventory_item_{self.link.id}": str(item.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.link.refresh_from_db()
        self.assertEqual(self.link.inventory_item_id, item.id)
