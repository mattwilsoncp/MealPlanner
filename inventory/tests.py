from django.db import models
from django.test import TestCase

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
