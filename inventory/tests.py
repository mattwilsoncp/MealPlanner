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
