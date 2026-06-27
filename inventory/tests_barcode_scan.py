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


class UpcUsageModelTests(TestCase):
    def test_record_increments_today_counter_atomically(self):
        from inventory.models import UpcLookupUsage

        UpcUsageModelTests._reset()

        count1 = UpcLookupUsage.record("upcitemdb")
        count2 = UpcLookupUsage.record("upcitemdb")
        count3 = UpcLookupUsage.record("upcitemdb")
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 2)
        self.assertEqual(count3, 3)
        self.assertEqual(UpcLookupUsage.today_count("upcitemdb"), 3)

    def test_today_count_returns_zero_when_no_record(self):
        UpcUsageModelTests._reset()
        from inventory.models import UpcLookupUsage
        self.assertEqual(UpcLookupUsage.today_count("openfoodfacts"), 0)
        self.assertEqual(UpcLookupUsage.today_count("upcitemdb"), 0)

    def test_recent_returns_only_window_inclusive(self):
        from datetime import timedelta
        from django.utils import timezone

        from inventory.models import UpcLookupUsage

        UpcUsageModelTests._reset()
        today = timezone.localdate()
        UpcLookupUsage.objects.create(service="upcitemdb", date=today, count=2)
        UpcLookupUsage.objects.create(service="upcitemdb", date=today - timedelta(days=29), count=5)
        UpcLookupUsage.objects.create(service="upcitemdb", date=today - timedelta(days=30), count=99)

        recent = list(UpcLookupUsage.recent(days=30).order_by("date").values_list("date", "count"))
        self.assertEqual(len(recent), 2)
        self.assertIn((today, 2), recent)
        self.assertIn((today - timedelta(days=29), 5), recent)

    def test_record_swallows_exceptions(self):
        from inventory.models import UpcLookupUsage

        UpcUsageModelTests._reset()

        original = UpcLookupUsage.objects.get_or_create
        UpcLookupUsage.objects.get_or_create = lambda **kw: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            self.assertEqual(UpcLookupUsage.record("upcitemdb"), -1)
        finally:
            UpcLookupUsage.objects.get_or_create = original

    @staticmethod
    def _reset():
        from inventory.models import UpcLookupUsage
        UpcLookupUsage.objects.all().delete()


class UpcUsageViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Settings Household")
        self.user = user_model.objects.create_user(
            username="settings-user",
            password="pass1234",
            household=self.household,
        )

    def test_upc_usage_page_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("upc_usage"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_upc_usage_page_renders_with_today_context(self):
        from inventory.models import UpcLookupUsage
        from django.utils import timezone

        UpcLookupUsage.record("upcitemdb")
        UpcLookupUsage.record("upcitemdb")
        UpcLookupUsage.record("openfoodfacts")
        self.client.force_login(self.user)

        response = self.client.get(reverse("upc_usage"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("UPC Item DB", body)
        self.assertIn("Open Food Facts", body)
        self.assertIn('Quota remaining', body)
        self.assertIn("Recent activity", body)
        # Today counts surface in the page
        context = response.context
        self.assertEqual(context["today_count_upcitemdb"], 2)
        self.assertEqual(context["today_count_openfoodfacts"], 1)
        self.assertEqual(context["daily_quota"], 100)
        self.assertEqual(context["quota_remaining"], 98)
        self.assertEqual(context["today"], timezone.localdate())

    def test_upc_lookup_creates_counter_rows_bump_each_call(self):
        from inventory.models import UpcLookupUsage

        UpcLookupUsage.objects.all().delete()
        with patch("inventory.services.upc_lookup.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                b'{"status":1,"product":{"product_name":"X"}}'
            )
            from inventory.services.upc_lookup import lookup_upc
            for _ in range(3):
                result = lookup_upc("0000000000003")
                self.assertTrue(result["ok"])

        self.assertEqual(UpcLookupUsage.today_count("openfoodfacts"), 3)
        # UPC Item DB only triggered when OFF fails
        self.assertEqual(UpcLookupUsage.today_count("upcitemdb"), 0)


class InventoryCreateApiTests(TestCase):
    """Tests for the JSON quick-create API used by the review reconcile modal."""

    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Quick Create Api")
        self.user = user_model.objects.create_user(
            username="quickapi-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)
        InventoryItem.objects.all().delete()

    def test_create_api_requires_location_when_called_as_json(self):
        """The form's `location` field is required because the model has no
        `blank=True`. The reconcile modal must include it in its payload
        (otherwise users see a generic 'Failed to add inventory item: 400')."""
        response = self.client.post(
            reverse("inventory:inventory_create_api"),
            data={"name": "Onion", "quantity": "2", "unit": "piece", "category": "produce"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("errors", body)
        self.assertIn("location", body["errors"])

    def test_create_api_persists_inventory_item_with_all_required_fields(self):
        response = self.client.post(
            reverse("inventory:inventory_create_api"),
            data={
                "name": "Tomato",
                "quantity": "4",
                "unit": "piece",
                "category": "produce",
                "location": "refrigerator",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        created = InventoryItem.objects.get(id=body["id"])
        self.assertEqual(created.name, "Tomato")
        self.assertEqual(created.quantity, Decimal("4"))
        self.assertEqual(created.location, "refrigerator")
        self.assertEqual(created.household, self.household)

    def test_create_api_assigns_inventory_item_to_caller_household(self):
        other_household = Household.objects.create(name="Quick Create Other")
        response = self.client.post(
            reverse("inventory:inventory_create_api"),
            data={
                "name": "Salt",
                "quantity": "1",
                "unit": "piece",
                "category": "pantry",
                "location": "pantry",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        created = InventoryItem.objects.get(name="Salt")
        self.assertEqual(created.household, self.household)
        self.assertNotEqual(created.household, other_household)
