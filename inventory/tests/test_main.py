from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from inventory.models import InventoryItem


class InventoryItemModelTests(TestCase):
    def test_inventory_item_has_image_field(self):
        image_field = InventoryItem._meta.get_field("image")

        self.assertIsInstance(image_field, models.ImageField)
        self.assertEqual(image_field.upload_to, "inventory/%Y/%m/%d/")

    def test_inventory_item_keeps_household_indexes(self):
        index_fields = [tuple(index.fields) for index in InventoryItem._meta.indexes]

        self.assertIn(("household", "name"), index_fields)
        self.assertIn(("household", "expiration_date"), index_fields)


class InventoryFormsTests(TestCase):
    def test_inventory_forms_are_exported(self):
        from inventory.forms import InventoryItemForm, InventoryQuickAddForm

        self.assertIsNotNone(InventoryItemForm)
        self.assertIsNotNone(InventoryQuickAddForm)

    def test_negative_quantity_is_rejected(self):
        from inventory.forms import InventoryItemForm

        form = InventoryItemForm(
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

    def test_zero_quantity_is_valid(self):
        from inventory.forms import InventoryItemForm

        form = InventoryItemForm(
            data={
                "name": "Used Up Stock",
                "quantity": "0",
                "unit": "piece",
                "category": "other",
                "location": "pantry",
            }
        )

        self.assertTrue(form.is_valid())


class InventoryViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Primary")
        self.other_household = Household.objects.create(name="Other")
        self.user = user_model.objects.create_user(
            username="inventory-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def test_inventory_urls_exist_for_crud_expiration_and_quick_add(self):
        self.assertEqual(reverse("inventory:inventory_list"), "/inventory/")
        self.assertEqual(reverse("inventory:inventory_add"), "/inventory/add/")
        self.assertEqual(
            reverse("inventory:inventory_edit", args=[42]),
            "/inventory/42/edit/",
        )
        self.assertEqual(
            reverse("inventory:inventory_delete", args=[42]),
            "/inventory/42/delete/",
        )
        self.assertEqual(
            reverse("inventory:inventory_expiring"), "/inventory/expiring/"
        )
        self.assertEqual(reverse("inventory:inventory_expired"), "/inventory/expired/")
        self.assertEqual(
            reverse("inventory:inventory_quick_add"),
            "/inventory/api/quick-add/",
        )

    def test_inventory_list_applies_household_scope_and_combined_filters(self):
        InventoryItem.objects.create(
            household=self.household,
            name="Organic Milk",
            quantity=Decimal("2.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Shelf Milk",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="pantry",
        )
        InventoryItem.objects.create(
            household=self.other_household,
            name="Organic Milk",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
        )

        response = self.client.get(
            reverse("inventory:inventory_list"),
            {
                "q": "organic",
                "category": "dairy",
                "location": "refrigerator",
            },
        )

        self.assertEqual(response.status_code, 200)
        items = list(response.context["items"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].household, self.household)
        self.assertEqual(items[0].name, "Organic Milk")

    def test_edit_and_delete_are_household_scoped(self):
        outsider_item = InventoryItem.objects.create(
            household=self.other_household,
            name="Other Home Eggs",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
        )

        edit_response = self.client.get(
            reverse("inventory:inventory_edit", args=[outsider_item.id])
        )
        delete_response = self.client.post(
            reverse("inventory:inventory_delete", args=[outsider_item.id])
        )

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)

    def test_list_page_renders_quick_delete_form_per_item(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="Quick Delete Apples",
            quantity=Decimal("1.00"),
            unit="piece",
            category="produce",
            location="refrigerator",
        )

        response = self.client.get(reverse("inventory:inventory_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'action="/inventory/{item.id}/delete/"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, "js-inventory-delete-form")
        self.assertContains(response, f'data-item-id="{item.id}"')
        content = response.content.decode()
        self.assertIn("Quick Delete Apples", content)
        self.assertIn("var(--text-light-gray)", content)

    def test_list_page_includes_ajax_delete_handler(self):
        response = self.client.get(reverse("inventory:inventory_list"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("X-Requested-With", content)
        self.assertIn("XMLHttpRequest", content)
        self.assertIn("js-inventory-delete-form", content)

    def test_quick_delete_form_post_redirects_and_removes_item(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="Disposable Item",
            quantity=Decimal("1.00"),
            unit="piece",
            category="other",
            location="pantry",
        )
        item_id = item.id

        response = self.client.post(
            reverse("inventory:inventory_delete", args=[item_id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("inventory:inventory_list"))
        self.assertFalse(InventoryItem.objects.filter(id=item_id).exists())

    def test_ajax_quick_delete_returns_json_without_redirect(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="Ajax Delete Item",
            quantity=Decimal("1.00"),
            unit="piece",
            category="produce",
            location="refrigerator",
        )
        item_id = item.id

        response = self.client.post(
            reverse("inventory:inventory_delete", args=[item_id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["id"], item_id)
        self.assertEqual(payload["name"], "Ajax Delete Item")
        self.assertFalse(InventoryItem.objects.filter(id=item_id).exists())

    def test_ajax_quick_delete_other_household_keeps_item_and_rejects(self):
        outsider = InventoryItem.objects.create(
            household=self.other_household,
            name="Foreign Item",
            quantity=Decimal("1.00"),
            unit="piece",
            category="other",
            location="pantry",
        )

        response = self.client.post(
            reverse("inventory:inventory_delete", args=[outsider.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(InventoryItem.objects.filter(id=outsider.id).exists())

    def test_inventory_delete_get_request_is_rejected(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="Locked Item",
            quantity=Decimal("1.00"),
            unit="piece",
            category="other",
            location="pantry",
        )

        response = self.client.get(
            reverse("inventory:inventory_delete", args=[item.id])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(InventoryItem.objects.filter(id=item.id).exists())

    def test_expiring_and_expired_views_use_household_threshold_rules(self):
        today = date.today()
        self.household.expiring_threshold_days = 5
        self.household.save(update_fields=["expiring_threshold_days"])

        InventoryItem.objects.create(
            household=self.household,
            name="Expiring Soon",
            quantity=Decimal("1.00"),
            unit="piece",
            category="other",
            location="pantry",
            expiration_date=today + timedelta(days=3),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Already Expired",
            quantity=Decimal("1.00"),
            unit="piece",
            category="other",
            location="pantry",
            expiration_date=today - timedelta(days=1),
        )
        InventoryItem.objects.create(
            household=self.household,
            name="Outside Threshold",
            quantity=Decimal("1.00"),
            unit="piece",
            category="other",
            location="pantry",
            expiration_date=today + timedelta(days=8),
        )

        expiring_response = self.client.get(reverse("inventory:inventory_expiring"))
        expired_response = self.client.get(reverse("inventory:inventory_expired"))

        self.assertEqual(expiring_response.status_code, 200)
        self.assertEqual(expired_response.status_code, 200)

        expiring_names = {item.name for item in expiring_response.context["items"]}
        expired_names = {item.name for item in expired_response.context["items"]}

        self.assertIn("Expiring Soon", expiring_names)
        self.assertNotIn("Outside Threshold", expiring_names)
        self.assertIn("Already Expired", expired_names)


class InventoryQuickAddApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Quick Add Home")
        self.user = user_model.objects.create_user(
            username="quick-add-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def test_quick_add_success_returns_created_item_payload(self):
        response = self.client.post(
            reverse("inventory:inventory_quick_add"),
            data={
                "name": "Yogurt",
                "quantity": "2",
                "unit": "piece",
                "category": "dairy",
                "location": "refrigerator",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertIn("id", payload)
        self.assertEqual(payload["name"], "Yogurt")
        self.assertEqual(str(payload["quantity"]), "2")
        self.assertEqual(payload["unit"], "piece")
        self.assertEqual(payload["category"], "dairy")
        self.assertEqual(payload["location"], "refrigerator")

    def test_quick_add_invalid_payload_returns_field_errors(self):
        response = self.client.post(
            reverse("inventory:inventory_quick_add"),
            data={"quantity": "-1"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("errors", payload)
        self.assertIn("name", payload["errors"])

    def test_quick_add_requires_csrf_token(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            reverse("inventory:inventory_quick_add"),
            data={"name": "Milk", "quantity": "1"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
