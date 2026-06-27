from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from inventory.models import InventoryItem
from inventory.services.receipt_barcode_enrichment import (
    BARCODE_PATTERN,
    enrich_receipt_items,
)
from inventory.services.upc_lookup import lookup_upc


def _item(**overrides):
    base = {
        "receipt_description": "MLK 2CT",
        "name": "",
        "quantity": "1",
        "unit": "piece",
        "category": "other",
        "location": "pantry",
        "price": "5.99",
        "barcode": "",
        "confidence": "low",
    }
    base.update(overrides)
    return base


class EnrichmentServiceTests(TestCase):
    def test_barcode_pattern_requires_eight_to_fourteen_digits(self):
        self.assertTrue(BARCODE_PATTERN.match("12345678"))
        self.assertTrue(BARCODE_PATTERN.match("1234567890123"))
        self.assertFalse(BARCODE_PATTERN.match("1234567"))
        self.assertFalse(BARCODE_PATTERN.match("abc12345"))
        self.assertFalse(BARCODE_PATTERN.match(" 12345678 "))

    def test_no_barcode_leaves_enrichment_empty(self):
        items = [_item(barcode=""), _item(barcode="")]

        with patch("inventory.services.receipt_barcode_enrichment.lookup_upc") as mock:
            enrichment_map, enriched = enrich_receipt_items(items)

        self.assertEqual(mock.call_count, 0)
        self.assertEqual(enrichment_map, {"0": None, "1": None})
        self.assertIsNone(enriched[0]["barcode_enrichment"])

    def test_malformed_barcode_does_not_trigger_upc_lookup(self):
        items = [_item(barcode="not-a-barcode")]

        with patch("inventory.services.receipt_barcode_enrichment.lookup_upc") as mock:
            enrichment_map, enriched = enrich_receipt_items(items)

        self.assertEqual(mock.call_count, 0)
        self.assertIsNone(enriched[0]["barcode_enrichment"])
        self.assertEqual(enrichment_map, {"0": None})

    def test_valid_barcode_calls_open_food_facts_first(self):
        items = [_item(barcode="012345678905")]
        with patch(
            "inventory.services.receipt_barcode_enrichment.lookup_upc"
        ) as mock_lookup:
            mock_lookup.return_value = {
                "ok": True,
                "title": "Greek Yogurt",
                "brand": "Acme",
                "size": "32 oz",
                "image_url": "https://example.com/yogurt.jpg",
                "category": "Dairy, Yogurt",
                "barcode": "012345678905",
                "source": "Open Food Facts",
            }
            enrichment_map, enriched = enrich_receipt_items(items)

        mock_lookup.assert_called_once_with("012345678905")
        enrichment = enriched[0]["barcode_enrichment"]
        self.assertEqual(enrichment["status"], "upc")
        self.assertEqual(enrichment["title"], "Greek Yogurt")
        self.assertEqual(enrichment["brand"], "Acme")
        self.assertEqual(enrichment["size"], "32 oz")
        self.assertEqual(enrichment["source"], "Open Food Facts")
        self.assertEqual(enrichment_map["0"]["title"], "Greek Yogurt")

    def test_local_inventory_match_short_circuits_upc_lookup(self):
        household = Household.objects.create(name="Enrich Local")
        InventoryItem.objects.create(
            household=household,
            name="Local Oats",
            quantity=Decimal("1.00"),
            unit="box",
            category="pantry",
            location="pantry",
            barcode="012345678905",
            notes="Brand: Quaker\nSize: 18 oz",
        )
        items = [_item(barcode="012345678905")]

        with patch(
            "inventory.services.receipt_barcode_enrichment.lookup_upc"
        ) as mock_lookup:
            enrichment_map, enriched = enrich_receipt_items(
                items, inventory_items=InventoryItem.objects.filter(household=household)
            )

        mock_lookup.assert_not_called()
        enrichment = enriched[0]["barcode_enrichment"]
        self.assertEqual(enrichment["status"], "local")
        self.assertEqual(enrichment["title"], "Local Oats")
        self.assertEqual(enrichment["brand"], "Quaker")
        self.assertEqual(enrichment["size"], "18 oz")
        self.assertIsNotNone(enrichment["inventory_item_id"])
        self.assertEqual(enrichment_map["0"]["status"], "local")

    def test_duplicate_barcode_in_receipt_is_lookup_only_once(self):
        items = [
            _item(barcode="012345678905"),
            _item(barcode="012345678905"),
        ]
        with patch(
            "inventory.services.receipt_barcode_enrichment.lookup_upc"
        ) as mock_lookup:
            mock_lookup.return_value = {
                "ok": True,
                "title": "Greek Yogurt",
                "brand": "Acme",
                "size": "32 oz",
                "image_url": "",
                "category": "yogurt",
                "barcode": "012345678905",
                "source": "Open Food Facts",
            }
            enrichment_map, enriched = enrich_receipt_items(items)

        self.assertEqual(mock_lookup.call_count, 1)
        self.assertEqual(enriched[0]["barcode_enrichment"]["status"], "upc")
        self.assertEqual(enriched[1]["barcode_enrichment"]["status"], "upc")
        self.assertEqual(
            enrichment_map["0"]["title"], enrichment_map["1"]["title"]
        )

    def test_not_found_status_records_message(self):
        items = [_item(barcode="0000000000000")]
        with patch(
            "inventory.services.receipt_barcode_enrichment.lookup_upc"
        ) as mock_lookup:
            mock_lookup.return_value = {
                "ok": False,
                "error": "upc_not_found",
                "message": "No product found for this barcode.",
            }
            enrichment_map, enriched = enrich_receipt_items(items)

        enrichment = enriched[0]["barcode_enrichment"]
        self.assertEqual(enrichment["status"], "not_found")
        self.assertEqual(enrichment["title"], "")
        self.assertIn("No product found", enrichment["message"])
        self.assertEqual(enrichment_map["0"]["status"], "not_found")

    def test_unknown_off_category_normalizes_to_blank(self):
        # _normalize_category is private but our mapping uses it indirectly via the
        # service; assert the public contract: UPC categories that don't match any
        # keyword come through blank so the view doesn't override user choices.
        items = [_item(barcode="012345678905")]
        with patch(
            "inventory.services.receipt_barcode_enrichment.lookup_upc"
        ) as mock_lookup:
            mock_lookup.return_value = {
                "ok": True,
                "title": "Mystery Item",
                "brand": "Acme",
                "size": "",
                "image_url": "",
                "category": "Some Unmapped Tag",
                "barcode": "012345678905",
                "source": "Open Food Facts",
            }
            _, enriched = enrich_receipt_items(items)

        enrichment = enriched[0]["barcode_enrichment"]
        self.assertEqual(enrichment["category"], "")

    def test_yogurt_off_category_normalizes_to_dairy(self):
        items = [_item(barcode="012345678905")]
        with patch(
            "inventory.services.receipt_barcode_enrichment.lookup_upc"
        ) as mock_lookup:
            mock_lookup.return_value = {
                "ok": True,
                "title": "Greek Yogurt",
                "brand": "Acme",
                "size": "32 oz",
                "image_url": "",
                "category": "Fermented dairy products",
                "barcode": "012345678905",
                "source": "Open Food Facts",
            }
            _, enriched = enrich_receipt_items(items)

        self.assertEqual(enriched[0]["barcode_enrichment"]["category"], "dairy")


class ReceiptImportReviewViewEnrichmentTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Receipt Enrichment Home")
        self.user = user_model.objects.create_user(
            username="receipt-enrich-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def _seed_session(self, items, enrichment_map):
        session = self.client.session
        session["receipt_import"] = {
            "store": "Test Mart",
            "purchased_at": "2026-06-01",
            "items": items,
            "barcode_enrichment": enrichment_map,
        }
        session.save()

    def test_review_view_exposes_enrichment_in_context(self):
        items = [{**_item(barcode="012345678905"), "barcode_enrichment": {
            "status": "upc",
            "title": "Greek Yogurt",
            "brand": "Acme",
            "size": "32 oz",
            "category": "dairy",
            "image_url": "",
            "source": "Open Food Facts",
        }}]
        enrichment_map = {"0": items[0]["barcode_enrichment"]}
        self._seed_session(items, enrichment_map)

        response = self.client.get(reverse("inventory:receipt_import_review"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("barcode_enrichment", response.context)
        self.assertEqual(
            response.context["barcode_enrichment"]["0"]["title"], "Greek Yogurt"
        )
        self.assertEqual(response.context["items"][0]["barcode_enrichment"]["status"], "upc")

    def test_review_view_handles_missing_enrichment_gracefully(self):
        items = [_item(barcode="012345678905")]
        self._seed_session(items, {})

        response = self.client.get(reverse("inventory:receipt_import_review"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["barcode_enrichment"], {})
        self.assertIsNone(response.context["items"][0]["barcode_enrichment"])

    def test_post_falls_back_to_enrichment_title_when_name_blank(self):
        items = [{"receipt_description": "MLK 2CT", "name": "", "quantity": "1",
                  "unit": "piece", "category": "dairy", "location": "refrigerator",
                  "price": "5.99", "barcode": "012345678905", "confidence": "high"}]
        enrichment = {
            "status": "upc",
            "title": "Greek Yogurt",
            "brand": "Acme",
            "size": "32 oz",
            "category": "dairy",
            "image_url": "https://example.com/y.jpg",
            "source": "Open Food Facts",
            "inventory_item_id": None,
            "message": "",
        }
        self._seed_session(items, {"0": enrichment})

        response = self.client.post(
            reverse("inventory:receipt_import_review"),
            data={
                "items-0-include": "on",
                "items-0-name": "",
                "items-0-receipt_description": "MLK 2CT",
                "items-0-quantity": "1",
                "items-0-unit": "piece",
                "items-0-category": "other",
                "items-0-location": "pantry",
                "items-0-barcode": "012345678905",
                "items-0-price": "5.99",
            },
        )

        self.assertEqual(response.status_code, 302)
        created = InventoryItem.objects.get(barcode="012345678905")
        self.assertEqual(created.name, "Greek Yogurt")
        self.assertEqual(created.category, "dairy")
        self.assertEqual(created.household, self.household)
        self.assertIn("Brand: Acme", created.notes)
        self.assertIn("Size: 32 oz", created.notes)

    def test_post_does_not_overwrite_user_supplied_name(self):
        items = [{"receipt_description": "MLK 2CT", "name": "", "quantity": "1",
                  "unit": "piece", "category": "dairy", "location": "refrigerator",
                  "price": "5.99", "barcode": "012345678905", "confidence": "high"}]
        enrichment = {
            "status": "upc",
            "title": "Greek Yogurt",
            "brand": "Acme",
            "size": "32 oz",
            "category": "dairy",
            "image_url": "",
            "source": "Open Food Facts",
            "inventory_item_id": None,
            "message": "",
        }
        self._seed_session(items, {"0": enrichment})

        self.client.post(
            reverse("inventory:receipt_import_review"),
            data={
                "items-0-include": "on",
                "items-0-name": "My Custom Yogurt",
                "items-0-receipt_description": "MLK 2CT",
                "items-0-quantity": "1",
                "items-0-unit": "piece",
                "items-0-category": "dairy",
                "items-0-location": "pantry",
                "items-0-barcode": "012345678905",
                "items-0-price": "5.99",
            },
        )

        created = InventoryItem.objects.get(barcode="012345678905")
        self.assertEqual(created.name, "My Custom Yogurt")

    def test_post_with_local_match_skipped_when_existing_item_selected(self):
        existing = InventoryItem.objects.create(
            household=self.household,
            name="Existing Oats",
            quantity=Decimal("1.00"),
            unit="box",
            category="pantry",
            location="pantry",
            barcode="012345678905",
        )
        items = [{"receipt_description": "OATS 18OZ", "name": "Existing Oats",
                  "quantity": "1", "unit": "box", "category": "pantry",
                  "location": "pantry", "price": "4.50", "barcode": "012345678905",
                  "confidence": "high"}]
        enrichment = {
            "status": "local",
            "title": "Existing Oats",
            "brand": "Quaker",
            "size": "18 oz",
            "category": "pantry",
            "image_url": "",
            "source": "local",
            "inventory_item_id": existing.id,
            "message": "",
        }
        self._seed_session(items, {"0": enrichment})

        before_qty = existing.quantity
        response = self.client.post(
            reverse("inventory:receipt_import_review"),
            data={
                "items-0-include": "on",
                "items-0-existing_item": str(existing.id),
                "items-0-name": "",
                "items-0-receipt_description": "OATS 18OZ",
                "items-0-quantity": "2",
                "items-0-unit": "box",
                "items-0-category": "pantry",
                "items-0-location": "pantry",
                "items-0-barcode": "012345678905",
                "items-0-price": "4.50",
            },
        )

        self.assertEqual(response.status_code, 302)
        existing.refresh_from_db()
        self.assertEqual(existing.quantity, before_qty + Decimal("2"))
        self.assertIn("Brand: Quaker", existing.notes)
        self.assertNotIn("Receipt price", existing.notes)
        self.assertIsNone(existing.price)

    def test_post_writes_price_and_store_to_fields_when_creating(self):
        items = [{"receipt_description": "MLK 2CT", "name": "Greek Yogurt",
                  "quantity": "1", "unit": "piece", "category": "dairy",
                  "location": "refrigerator", "price": "4.50",
                  "barcode": "012345678905", "confidence": "high"}]
        self._seed_session(items, {"0": None})
        session = self.client.session
        session["receipt_import"]["store"] = "Acme Market"
        session.save()

        response = self.client.post(
            reverse("inventory:receipt_import_review"),
            data={
                "items-0-include": "on",
                "items-0-name": "Greek Yogurt",
                "items-0-receipt_description": "MLK 2CT",
                "items-0-quantity": "1",
                "items-0-unit": "piece",
                "items-0-category": "dairy",
                "items-0-location": "refrigerator",
                "items-0-barcode": "012345678905",
                "items-0-price": "4.50",
            },
        )

        self.assertEqual(response.status_code, 302)
        created = InventoryItem.objects.get(barcode="012345678905")
        self.assertEqual(created.price, Decimal("4.50"))
        self.assertEqual(created.store.name, "Acme Market")
        self.assertNotIn("Receipt price", created.notes)

    def test_post_skips_row_with_no_name_and_no_enrichment(self):
        items = [{"receipt_description": "???", "name": "", "quantity": "1",
                  "unit": "piece", "category": "other", "location": "pantry",
                  "price": "", "barcode": "bad-value", "confidence": "low"}]
        self._seed_session(items, {"0": None})

        response = self.client.post(
            reverse("inventory:receipt_import_review"),
            data={
                "items-0-include": "on",
                "items-0-name": "",
                "items-0-receipt_description": "???",
                "items-0-quantity": "1",
                "items-0-unit": "piece",
                "items-0-category": "other",
                "items-0-location": "pantry",
                "items-0-barcode": "bad-value",
                "items-0-price": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(InventoryItem.objects.count(), 0)


class ReceiptImportViewCallsEnrichmentTests(TestCase):
    """Smoke-test that ReceiptImportView writes enrichment into session."""

    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Receipt Import Smoke Home")
        self.user = user_model.objects.create_user(
            username="receipt-import-user",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

    def test_form_valid_writes_enrichment_for_extracted_barcodes(self):
        from inventory.views import ReceiptImportView

        with patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "test-key"},
        ), patch(
            "inventory.views.OpenAI"
        ) as mock_openai, patch(
            "inventory.views.enrich_receipt_items"
        ) as mock_enrich, patch.object(
            ReceiptImportView, "_normalize_items"
        ) as mock_normalize:
            fake_response = type(
                "R",
                (),
                {
                    "choices": [
                        type(
                            "C",
                            (),
                            {"message": type("M", (), {"content": "{}"})()},
                        )()
                    ]
                },
            )()
            mock_openai.return_value.chat.completions.create.return_value = fake_response
            mock_enrich.return_value = ({}, [])
            mock_normalize.return_value = [
                {"receipt_description": "X", "name": "Milk", "barcode": "012345678905"}
            ]

            from PIL import Image as PILImage
            from io import BytesIO

            image_file = BytesIO()
            PILImage.new("RGB", (10, 10), "white").save(image_file, format="JPEG")
            image_file.name = "receipt.jpg"
            image_file.seek(0)

            response = self.client.post(
                reverse("inventory:receipt_import"),
                data={"image": image_file, "model": "google/gemini-2.0-flash-001"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("inventory:receipt_import_review"))
        mock_enrich.assert_called_once()
        positional_args = mock_enrich.call_args.args
        self.assertEqual(positional_args[0], [
            {"receipt_description": "X", "name": "Milk", "barcode": "012345678905"}
        ])
