from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from household.models import Household
from inventory.models import InventoryItem


class InventoryItemModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Model Test Home")

    def test_str_includes_name_and_quantity_and_unit(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="Almond Milk",
            quantity=Decimal("1.50"),
            unit="l",
            category="dairy",
            location="refrigerator",
        )
        self.assertEqual(str(item), "Almond Milk (1.50 l)")

    def test_str_with_integer_quantity(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="Eggs",
            quantity=Decimal("12"),
            unit="piece",
            category="dairy",
            location="refrigerator",
        )
        self.assertEqual(str(item), "Eggs (12 piece)")

    def test_household_cascade_deletes_items(self):
        InventoryItem.objects.create(
            household=self.household,
            name="Cereal",
            quantity=Decimal("1"),
            unit="box",
            category="pantry",
            location="pantry",
        )
        self.assertEqual(InventoryItem.objects.count(), 1)
        self.household.delete()
        self.assertEqual(InventoryItem.objects.count(), 0)

    def test_cross_household_access_is_denied(self):
        other_household = Household.objects.create(name="Other Home")
        item = InventoryItem.objects.create(
            household=other_household,
            name="Private Stock",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
        )
        # Trying to access via another household's queryset should return nothing
        queryset = InventoryItem.objects.filter(household=self.household)
        self.assertFalse(queryset.filter(id=item.id).exists())


class InventoryItemFormTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Form Test Home")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="inv-form-user",
            email="inv-form@example.com",
            password="pass1234",
            household=self.household,
        )

    def test_form_valid_with_minimal_required_fields(self):
        from inventory.forms import InventoryItemForm

        form = InventoryItemForm(
            data={
                "name": "Rice",
                "quantity": "1",
                "unit": "lb",
                "category": "pantry",
                "location": "pantry",
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_rejects_invalid_category(self):
        from inventory.forms import InventoryItemForm

        form = InventoryItemForm(
            data={
                "name": "Mystery Item",
                "quantity": "1",
                "unit": "piece",
                "category": "not_a_category",
                "location": "pantry",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_form_rejects_invalid_location(self):
        from inventory.forms import InventoryItemForm

        form = InventoryItemForm(
            data={
                "name": "Mystery Item",
                "quantity": "1",
                "unit": "piece",
                "category": "other",
                "location": "not_a_location",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("location", form.errors)

    def test_form_accepts_all_valid_categories(self):
        from inventory.forms import InventoryItemForm

        valid_categories = ["produce", "dairy", "meat", "frozen", "pantry",
                            "beverages", "condiments", "snacks", "bakery", "other"]
        for cat in valid_categories:
            form = InventoryItemForm(
                data={
                    "name": "Item",
                    "quantity": "1",
                    "unit": "piece",
                    "category": cat,
                    "location": "pantry",
                }
            )
            self.assertTrue(form.is_valid(), f"Category '{cat}' should be valid: {form.errors}")

    def test_form_accepts_all_valid_locations(self):
        from inventory.forms import InventoryItemForm

        valid_locations = ["pantry", "refrigerator", "freezer", "counter", "cabinet"]
        for loc in valid_locations:
            form = InventoryItemForm(
                data={
                    "name": "Item",
                    "quantity": "1",
                    "unit": "piece",
                    "category": "other",
                    "location": loc,
                }
            )
            self.assertTrue(form.is_valid(), f"Location '{loc}' should be valid: {form.errors}")

    def test_form_expiration_date_past_is_not_rejected(self):
        from inventory.forms import InventoryItemForm

        past_date = (date.today() - timedelta(days=5)).isoformat()
        form = InventoryItemForm(
            data={
                "name": "Old Stock",
                "quantity": "1",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
                "expiration_date": past_date,
            }
        )
        # Currently no past-date validation — form accepts it
        self.assertTrue(form.is_valid())

    def test_form_expiration_date_future_is_valid(self):
        from inventory.forms import InventoryItemForm

        future_date = (date.today() + timedelta(days=30)).isoformat()
        form = InventoryItemForm(
            data={
                "name": "New Stock",
                "quantity": "1",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
                "expiration_date": future_date,
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_barcode_is_optional(self):
        from inventory.forms import InventoryItemForm

        form = InventoryItemForm(
            data={
                "name": "Stocked Item",
                "quantity": "1",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
                "barcode": "",
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_notes_are_optional(self):
        from inventory.forms import InventoryItemForm

        form = InventoryItemForm(
            data={
                "name": "Stocked Item",
                "quantity": "1",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
                "notes": "",
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_saves_all_fields(self):
        from inventory.forms import InventoryItemForm

        future_date = (date.today() + timedelta(days=7)).isoformat()
        form = InventoryItemForm(
            data={
                "name": "Olive Oil",
                "quantity": "0.50",
                "unit": "l",
                "category": "condiments",
                "location": "pantry",
                "expiration_date": future_date,
                "notes": "Extra virgin",
                "barcode": "123456789012",
            }
        )
        self.assertTrue(form.is_valid())
        item = form.save(commit=False)
        item.household = self.household
        item.save()
        self.assertEqual(item.name, "Olive Oil")
        self.assertEqual(item.quantity, Decimal("0.50"))
        self.assertEqual(item.unit, "l")
        self.assertEqual(item.category, "condiments")
        self.assertEqual(item.location, "pantry")
        self.assertEqual(item.notes, "Extra virgin")
        self.assertEqual(item.barcode, "123456789012")


class InventoryQuickAddFormTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Quick Add Form Home")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="quick-form-user",
            email="quick-form@example.com",
            password="pass1234",
            household=self.household,
        )

    def test_quick_add_form_rejects_negative_quantity(self):
        from inventory.forms import InventoryQuickAddForm

        form = InventoryQuickAddForm(
            data={
                "name": "Milk",
                "quantity": "-1",
                "unit": "piece",
                "category": "dairy",
                "location": "refrigerator",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_quick_add_form_accepts_zero_quantity(self):
        from inventory.forms import InventoryQuickAddForm

        form = InventoryQuickAddForm(
            data={
                "name": "Used Up",
                "quantity": "0",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
            }
        )
        self.assertTrue(form.is_valid())

    def test_quick_add_form_requires_name(self):
        from inventory.forms import InventoryQuickAddForm

        form = InventoryQuickAddForm(
            data={
                "quantity": "1",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_quick_add_form_requires_category(self):
        from inventory.forms import InventoryQuickAddForm

        form = InventoryQuickAddForm(
            data={
                "name": "Item",
                "quantity": "1",
                "unit": "piece",
                "location": "pantry",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_quick_add_form_requires_location(self):
        from inventory.forms import InventoryQuickAddForm

        form = InventoryQuickAddForm(
            data={
                "name": "Item",
                "quantity": "1",
                "unit": "piece",
                "category": "other",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("location", form.errors)


class InventoryViewAccessTests(TestCase):
    """Test CRUD view access patterns and household isolation."""

    def setUp(self):
        self.household = Household.objects.create(name="View Access Home")
        self.other_household = Household.objects.create(name="Other View Home")
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="view-user",
            email="view-user@example.com",
            password="pass1234",
            household=self.household,
        )
        self.other_user = user_model.objects.create_user(
            username="other-view-user",
            email="other-view-user@example.com",
            password="pass1234",
            household=self.other_household,
        )
        self.client.force_login(self.user)

    def test_create_view_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("inventory:inventory_add"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_list_view_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("inventory:inventory_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_create_view_assigns_household_from_user(self):
        response = self.client.post(
            reverse("inventory:inventory_add"),
            data={
                "name": "Created Item",
                "quantity": "1",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(name="Created Item")
        self.assertEqual(item.household, self.household)

    def test_update_view_assigns_household_from_user(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="To Update",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
        )
        response = self.client.post(
            reverse("inventory:inventory_edit", args=[item.id]),
            data={
                "name": "Updated Item",
                "quantity": "2",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
            },
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.name, "Updated Item")
        self.assertEqual(item.quantity, Decimal("2"))

    def test_update_other_household_returns_404(self):
        other_item = InventoryItem.objects.create(
            household=self.other_household,
            name="Other Item",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
        )
        response = self.client.post(
            reverse("inventory:inventory_edit", args=[other_item.id]),
            data={
                "name": "Hacked",
                "quantity": "999",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
            },
        )
        self.assertEqual(response.status_code, 404)
        other_item.refresh_from_db()
        self.assertEqual(other_item.name, "Other Item")

    def test_delete_other_household_returns_404(self):
        other_item = InventoryItem.objects.create(
            household=self.other_household,
            name="To Delete",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
        )
        other_id = other_item.id
        response = self.client.post(
            reverse("inventory:inventory_delete", args=[other_id])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(InventoryItem.objects.filter(id=other_id).exists())

    def test_delete_own_item_succeeds(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="To Delete",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
        )
        item_id = item.id
        response = self.client.post(
            reverse("inventory:inventory_delete", args=[item_id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(InventoryItem.objects.filter(id=item_id).exists())

    def test_list_view_only_shows_own_household_items(self):
        InventoryItem.objects.create(
            household=self.household,
            name="My Item",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
        )
        InventoryItem.objects.create(
            household=self.other_household,
            name="Other Item",
            quantity=Decimal("1"),
            unit="piece",
            category="other",
            location="pantry",
        )
        response = self.client.get(reverse("inventory:inventory_list"))
        self.assertEqual(response.status_code, 200)
        items = list(response.context["items"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "My Item")
