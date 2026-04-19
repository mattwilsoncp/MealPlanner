from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from shopping.models import ShoppingListItem, ShoppingListWeek


class ShoppingActionEndpointTests(TestCase):
    def setUp(self):
        self.week_start = date(2026, 4, 13)
        self.household = Household.objects.create(name="Home")
        self.other_household = Household.objects.create(name="Other")

        self.user = get_user_model().objects.create_user(
            username="shopper",
            password="pass1234",
            household=self.household,
        )
        self.other_user = get_user_model().objects.create_user(
            username="intruder",
            password="pass1234",
            household=self.other_household,
        )

        self.week = ShoppingListWeek.objects.create(
            household=self.household,
            week_start=self.week_start,
        )
        self.other_week = ShoppingListWeek.objects.create(
            household=self.other_household,
            week_start=self.week_start,
        )

        self.item = ShoppingListItem.objects.create(
            shopping_week=self.week,
            name="Milk",
            quantity=Decimal("1.00"),
            unit="carton",
            checked=False,
        )
        self.other_item = ShoppingListItem.objects.create(
            shopping_week=self.other_week,
            name="Eggs",
            quantity=Decimal("12.00"),
            unit="piece",
            checked=False,
        )

        self.client.force_login(self.user)

    def test_toggle_endpoint_flips_checked_state_and_returns_json(self):
        response = self.client.post(
            reverse("shopping:item_toggle", kwargs={"item_id": self.item.id})
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.checked)
        self.assertEqual(response.json()["checked"], True)

    def test_toggle_endpoint_denies_cross_household_item(self):
        response = self.client.post(
            reverse("shopping:item_toggle", kwargs={"item_id": self.other_item.id})
        )

        self.assertEqual(response.status_code, 404)
        self.other_item.refresh_from_db()
        self.assertFalse(self.other_item.checked)

    def test_delete_endpoint_removes_item(self):
        response = self.client.post(
            reverse("shopping:item_delete", kwargs={"item_id": self.item.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], True)
        self.assertFalse(ShoppingListItem.objects.filter(id=self.item.id).exists())

    def test_delete_endpoint_denies_cross_household_item(self):
        response = self.client.post(
            reverse("shopping:item_delete", kwargs={"item_id": self.other_item.id})
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(ShoppingListItem.objects.filter(id=self.other_item.id).exists())

    def test_clear_endpoint_deletes_week_items_and_is_idempotent(self):
        ShoppingListItem.objects.create(
            shopping_week=self.week,
            name="Bread",
            quantity=Decimal("1.00"),
            unit="loaf",
        )

        first = self.client.post(
            reverse("shopping:week_clear"),
            {"week_start": self.week_start.isoformat()},
        )
        second = self.client.post(
            reverse("shopping:week_clear"),
            {"week_start": self.week_start.isoformat()},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["cleared_count"], 2)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["cleared_count"], 0)

    def test_clear_endpoint_does_not_affect_other_household(self):
        response = self.client.post(
            reverse("shopping:week_clear"),
            {"week_start": self.week_start.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ShoppingListItem.objects.filter(
                id=self.other_item.id,
                shopping_week__household=self.other_household,
            ).exists()
        )

    def test_clear_endpoint_when_only_other_household_has_week_returns_zero(self):
        ShoppingListItem.objects.filter(shopping_week=self.week).delete()

        response = self.client.post(
            reverse("shopping:week_clear"),
            {"week_start": self.week_start.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cleared_count"], 0)
        self.assertTrue(ShoppingListItem.objects.filter(id=self.other_item.id).exists())
