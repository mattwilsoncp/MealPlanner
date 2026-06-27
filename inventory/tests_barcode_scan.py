from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from inventory.models import InventoryItem


class BarcodeLookupTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Barcode Household")
        self.user = user_model.objects.create_user(
            username="barcode-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def test_local_barcode_hit_does_not_call_external_upc_lookup(self):
        InventoryItem.objects.create(
            household=self.household,
            name="Local Oats",
            quantity=Decimal("1.00"),
            unit="box",
            category="pantry",
            location="pantry",
            barcode="012345678905",
        )

        with patch("inventory.views.lookup_upc") as mock_lookup:
            response = self.client.post(
                reverse("inventory:barcode_lookup_api"),
                data={"barcode": "012345678905"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "local")
        self.assertEqual(payload["item"]["name"], "Local Oats")
        self.assertEqual(payload["item"]["barcode"], "012345678905")
        mock_lookup.assert_not_called()

    def test_unknown_barcode_falls_back_to_upc_lookup(self):
        with patch("inventory.views.lookup_upc") as mock_lookup:
            mock_lookup.return_value = {
                "ok": True,
                "title": "Peanut Butter",
                "brand": "Acme",
                "size": "16 oz",
                "image_url": "https://example.com/pb.jpg",
                "category": "pantry",
                "barcode": "098765432109",
            }
            response = self.client.post(
                reverse("inventory:barcode_lookup_api"),
                data={"barcode": "098765432109"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "upc")
        self.assertEqual(payload["item"]["title"], "Peanut Butter")
        self.assertEqual(payload["item"]["brand"], "Acme")
        self.assertEqual(payload["item"]["size"], "16 oz")
        self.assertEqual(payload["item"]["barcode"], "098765432109")
        mock_lookup.assert_called_once_with("098765432109")

    def test_upc_lookup_failure_returns_structured_error_payload(self):
        with patch("inventory.views.lookup_upc") as mock_lookup:
            mock_lookup.return_value = {
                "ok": False,
                "error": "upc_lookup_failed",
                "message": "Timed out while fetching UPC result.",
            }
            response = self.client.post(
                reverse("inventory:barcode_lookup_api"),
                data={"barcode": "000111222333"},
            )

        self.assertEqual(response.status_code, 502)
        payload = response.json()
        self.assertEqual(payload["source"], "upc")
        self.assertEqual(payload["error"], "upc_lookup_failed")
        self.assertEqual(payload["message"], "Timed out while fetching UPC result.")

    def test_malformed_barcode_is_rejected_with_400(self):
        with patch("inventory.views.lookup_upc") as mock_lookup:
            response = self.client.post(
                reverse("inventory:barcode_lookup_api"),
                data={"barcode": "bad-value"},
            )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"], "invalid_barcode")
        mock_lookup.assert_not_called()


class BarcodeCreateTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Barcode Create Household")
        self.other_household = Household.objects.create(name="Other Household")
        self.user = user_model.objects.create_user(
            username="barcode-create-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def test_barcode_routes_exist(self):
        self.assertEqual(reverse("inventory:barcode_scan"), "/inventory/barcode/")
        self.assertEqual(
            reverse("inventory:barcode_lookup_api"),
            "/inventory/api/barcode/lookup/",
        )
        self.assertEqual(
            reverse("inventory:barcode_create_api"),
            "/inventory/api/barcode/create/",
        )

    def test_create_from_lookup_persists_household_inventory_item(self):
        response = self.client.post(
            reverse("inventory:barcode_create_api"),
            data={
                "title": "Greek Yogurt",
                "brand": "Acme",
                "size": "32 oz",
                "image_url": "https://example.com/yogurt.jpg",
                "category": "dairy",
                "barcode": "123456789012",
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        created = InventoryItem.objects.get(id=payload["id"])
        self.assertEqual(created.household, self.household)
        self.assertEqual(created.name, "Greek Yogurt")
        self.assertEqual(created.barcode, "123456789012")
        self.assertIn("Acme", created.notes)
        self.assertIn("32 oz", created.notes)

    def test_create_duplicate_household_barcode_returns_conflict(self):
        InventoryItem.objects.create(
            household=self.household,
            name="Existing Yogurt",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
            barcode="123456789012",
        )
        InventoryItem.objects.create(
            household=self.other_household,
            name="Other Household Yogurt",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
            barcode="123456789012",
        )

        response = self.client.post(
            reverse("inventory:barcode_create_api"),
            data={
                "title": "Greek Yogurt",
                "brand": "Acme",
                "size": "32 oz",
                "category": "dairy",
                "barcode": "123456789012",
            },
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["error"], "duplicate_barcode")
        self.assertEqual(
            InventoryItem.objects.filter(
                household=self.household,
                barcode="123456789012",
            ).count(),
            1,
        )


class InventoryFormBarcodeLookupTests(TestCase):
    """Verify inventory add/edit pages surface the inline barcode lookup UI."""

    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Form Lookup Household")
        self.other_household = Household.objects.create(name="Other Form Lookup")
        self.user = user_model.objects.create_user(
            username="form-lookup-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def test_add_page_renders_inline_barcode_lookup_component(self):
        response = self.client.get(reverse("inventory:inventory_add"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("x-data=\"inventoryBarcodeLookup()\"", body)
        self.assertIn("inventory-barcode-reader", body)
        self.assertIn(reverse("inventory:barcode_lookup_api"), body)
        self.assertIn("init(null)", body)
        self.assertIn("Start Camera", body)

    def test_edit_page_passes_current_item_id_to_lookup_component(self):
        item = InventoryItem.objects.create(
            household=self.household,
            name="ToEdit",
            quantity=Decimal("1.00"),
            unit="piece",
            category="other",
            location="pantry",
            barcode="012345678905",
        )
        response = self.client.get(reverse("inventory:inventory_edit", args=[item.id]))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("x-data=\"inventoryBarcodeLookup()\"", body)
        self.assertIn("init({})".format(item.id), body)

    def test_add_form_submission_with_existing_household_barcode_is_allowed(self):
        """Adding a SECOND item that shares a barcode with an existing item
        must not block submission — the page only warns about duplicates."""
        InventoryItem.objects.create(
            household=self.household,
            name="Existing Yogurt",
            quantity=Decimal("1.00"),
            unit="piece",
            category="dairy",
            location="refrigerator",
            barcode="123456789012",
        )

        response = self.client.post(
            reverse("inventory:inventory_add"),
            data={
                "name": "Second Yogurt Stock",
                "quantity": "2.00",
                "unit": "piece",
                "category": "dairy",
                "location": "refrigerator",
                "barcode": "123456789012",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            InventoryItem.objects.filter(
                household=self.household,
                barcode="123456789012",
            ).count(),
            2,
        )

    def test_add_form_prefilled_with_upc_lookup_result_persists_to_inventory(self):
        """End-to-end: emulate the user scanning a barcode (server-side lookup)
        then submitting the form with the UPC title/category. The forms
        binding layer must persist all three: banner pre-fill is purely HUD.
        """
        with patch("inventory.views.lookup_upc") as mock_lookup:
            mock_lookup.return_value = {
                "ok": True,
                "title": "Greek Yogurt",
                "brand": "Acme",
                "size": "32 oz",
                "image_url": "https://example.com/yogurt.jpg",
                "category": "dairy",
                "barcode": "123456789012",
            }
            response = self.client.get(reverse("inventory:inventory_add"))
            self.assertEqual(response.status_code, 200)
            mock_lookup.assert_not_called()

        response = self.client.post(
            reverse("inventory:inventory_add"),
            data={
                "name": "Greek Yogurt",
                "quantity": "1.00",
                "unit": "piece",
                "category": "dairy",
                "location": "pantry",
                "barcode": "123456789012",
                "notes": "Brand: Acme\nSize: 32 oz",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = InventoryItem.objects.get(barcode="123456789012", household=self.household)
        self.assertEqual(created.name, "Greek Yogurt")
        self.assertEqual(created.category, "dairy")
        self.assertIn("Acme", created.notes)
