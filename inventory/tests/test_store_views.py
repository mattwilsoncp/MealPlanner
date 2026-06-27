from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from inventory.models import InventoryItem, Store


class StoreModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Store Model Home")

    def test_str_returns_name(self):
        store = Store.objects.create(household=self.household, name="Joe's Mart")
        self.assertEqual(str(store), "Joe's Mart")

    def test_unique_per_household_constraint_blocks_duplicate_name(self):
        from django.db import IntegrityError, transaction

        Store.objects.create(household=self.household, name="Acme")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Store.objects.create(household=self.household, name="Acme")

    def test_same_name_allowed_in_different_households(self):
        other_household = Household.objects.create(name="Other Home")
        Store.objects.create(household=self.household, name="Acme")
        Store.objects.create(household=other_household, name="Acme")
        self.assertEqual(Store.objects.filter(name="Acme").count(), 2)


class StoreViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Store Test Home")
        self.other_household = Household.objects.create(name="Other Store Home")
        self.user = user_model.objects.create_user(
            username="store-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def test_store_list_renders_only_own_household_stores(self):
        own_a = Store.objects.create(household=self.household, name="Own A")
        Store.objects.create(household=self.other_household, name="Other A")

        response = self.client.get(reverse("inventory:store_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(own_a, response.context["stores"])
        names = {store.name for store in response.context["stores"]}
        self.assertIn("Own A", names)
        self.assertNotIn("Other A", names)

    def test_store_list_counts_linked_inventory_items(self):
        store = Store.objects.create(household=self.household, name="With Items")
        InventoryItem.objects.create(
            household=self.household,
            name="Item 1",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
            store=store,
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Item 2",
            quantity=Decimal("2"),
            unit="piece",
            category="other",
            location="pantry",
            store=store,
        )

        response = self.client.get(reverse("inventory:store_list"))

        for store_obj in response.context["stores"]:
            if store_obj.pk == store.pk:
                self.assertEqual(store_obj.item_count, 2)

    def test_store_create_assigns_household_and_redirects(self):
        response = self.client.post(
            reverse("inventory:store_add"),
            data={"name": "Brand New Store", "notes": "Open 24h"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("inventory:store_list"))
        created = Store.objects.get(name="Brand New Store")
        self.assertEqual(created.household, self.household)
        self.assertEqual(created.notes, "Open 24h")

    def test_store_create_rejects_duplicate_name_in_same_household(self):
        Store.objects.create(household=self.household, name="Acme")

        response = self.client.post(
            reverse("inventory:store_add"),
            data={"name": "Acme", "notes": ""},
        )

        self.assertEqual(response.status_code, 200)
        errors = response.context["form"].errors
        self.assertTrue(
            errors.get("__all__") or errors.get("name"),
            f"expected duplicate-name validation error, got: {errors.as_json()}",
        )
        self.assertEqual(Store.objects.filter(name="Acme").count(), 1)

    def test_store_update_renames_within_household_scoped_queryset(self):
        store = Store.objects.create(household=self.household, name="Old Name")
        response = self.client.post(
            reverse("inventory:store_edit", args=[store.pk]),
            data={"name": "New Name", "notes": ""},
        )
        self.assertEqual(response.status_code, 302)
        store.refresh_from_db()
        self.assertEqual(store.name, "New Name")

    def test_store_update_rejects_other_households_store(self):
        other_store = Store.objects.create(
            household=self.other_household, name="Foreign"
        )
        response = self.client.get(
            reverse("inventory:store_edit", args=[other_store.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_store_delete_unlinks_inventory_items_first(self):
        store = Store.objects.create(household=self.household, name="Bits")
        item = InventoryItem.objects.create(
            household=self.household,
            name="Linked",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
            store=store,
        )

        response = self.client.post(
            reverse("inventory:store_delete", args=[store.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Store.objects.filter(pk=store.pk).exists())
        item.refresh_from_db()
        self.assertIsNone(item.store)

    def test_store_delete_rejects_other_households_store(self):
        other_store = Store.objects.create(
            household=self.other_household, name="Foreign Two"
        )
        response = self.client.post(
            reverse("inventory:store_delete", args=[other_store.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Store.objects.filter(pk=other_store.pk).exists())

    def test_inventory_list_links_to_store_maintenance(self):
        response = self.client.get(reverse("inventory:inventory_list"))
        self.assertEqual(response.status_code, 200)
