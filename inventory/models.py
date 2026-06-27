from django.db import models
from household.models import Household


class Store(models.Model):
    """A retailer or vendor where household inventory items can be purchased."""

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="stores"
    )
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = (("household", "name"),)

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    """Inventory item for tracking household food supplies."""

    CATEGORY_CHOICES = [
        ("produce", "Produce"),
        ("dairy", "Dairy"),
        ("meat", "Meat & Seafood"),
        ("frozen", "Frozen"),
        ("pantry", "Pantry"),
        ("beverages", "Beverages"),
        ("condiments", "Condiments & Sauces"),
        ("snacks", "Snacks"),
        ("bakery", "Bakery"),
        ("other", "Other"),
    ]

    LOCATION_CHOICES = [
        ("pantry", "Pantry"),
        ("refrigerator", "Refrigerator"),
        ("freezer", "Freezer"),
        ("counter", "Counter"),
        ("cabinet", "Cabinet"),
    ]

    UNIT_CHOICES = [
        ("oz", "ounce"),
        ("lb", "pound"),
        ("cup", "cup"),
        ("tbsp", "tablespoon"),
        ("tsp", "teaspoon"),
        ("g", "gram"),
        ("kg", "kilogram"),
        ("ml", "milliliter"),
        ("l", "liter"),
        ("piece", "piece"),
        ("dozen", "dozen"),
        ("pack", "pack"),
        ("box", "box"),
        ("can", "can"),
        ("bottle", "bottle"),
        ("bag", "bag"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="inventory_items"
    )
    name = models.CharField(max_length=200, db_index=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="piece")
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="other"
    )
    location = models.CharField(
        max_length=20, choices=LOCATION_CHOICES, default="pantry"
    )
    expiration_date = models.DateField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_items",
    )
    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to="inventory/%Y/%m/%d/", blank=True, null=True)
    barcode = models.CharField(max_length=50, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["household", "name"]),
            models.Index(fields=["household", "expiration_date"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"
