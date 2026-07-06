from django.db import models
from django.db.models import F
from django.utils import timezone

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


class UpcLookupUsage(models.Model):
    """Daily per-service counter of outbound UPC barcode lookups.

    Tracks how many HTTP requests the server sends to the third-party
    barcode services so admins can monitor the UPC Item DB trial quota
    (default 100 req/day). One row per (service, date).
    """

    SERVICE_CHOICES = [
        ("openfoodfacts", "Open Food Facts"),
        ("upcitemdb", "UPC Item DB"),
    ]

    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    date = models.DateField()
    count = models.PositiveIntegerField(default=0)
    last_call_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = (("service", "date"),)
        indexes = [models.Index(fields=["service", "-date"])]

    def __str__(self):
        return f"{self.get_service_display()} · {self.date} · {self.count}"

    @classmethod
    def record(cls, service: str) -> int:
        """Increment today's counter for the given service and return new count.

        Uses an atomic ``F('count') + 1`` so concurrent updates don't lose
        increments. Tracking failures are swallowed — never let monitoring
        break a real UPC lookup.
        """
        try:
            today = timezone.localdate()
            now = timezone.now()
            row, created = cls.objects.get_or_create(
                service=service,
                date=today,
                defaults={"count": 1, "last_call_at": now},
            )
            if not created:
                cls.objects.filter(pk=row.pk).update(
                    count=F("count") + 1,
                    last_call_at=now,
                )
                row.refresh_from_db(fields=["count", "last_call_at"])
            return row.count
        except Exception:
            return -1

    @classmethod
    def today_count(cls, service: str) -> int:
        try:
            return cls.objects.get(
                service=service, date=timezone.localdate()
            ).count
        except cls.DoesNotExist:
            return 0

    @classmethod
    def recent(cls, days: int = 30):
        from datetime import timedelta

        cutoff = timezone.localdate() - timedelta(days=days - 1)
        return cls.objects.filter(date__gte=cutoff)

    @classmethod
    def reset_today(cls, service: str) -> int:
        """Test helper: zero out today's counter for a given service."""
        return cls.objects.filter(
            service=service, date=timezone.localdate()
        ).update(count=0)


class InventoryCategory(models.Model):
    """User-editable inventory category.

    Replaces the static ``InventoryItem.CATEGORY_CHOICES`` tuple so the
    categories offered on the inventory list page, add/edit form, and
    AJAX-assign dropdown can be added, renamed, and removed at runtime
    via the inventory settings page (``/inventory/settings/categories/``).

    The ``InventoryItem`` still stores ``category`` as a slug CharField
    so we don't need a destructive FK migration; the slug is the stable
    join key. The display label comes from this table.

    Conventions
    -----------
    * ``slug`` is the immutable key used by ``InventoryItem.category``
      and the JS assign-category endpoint. Renaming a category edits
      ``name`` only; the slug never changes.
    * ``is_protected`` categories cannot be deleted (currently: only
      the ``"other"`` Uncategorized fallback bucket). POSTing a delete
      on them returns 409.
    * Items currently in a deleted category are reassigned to
      ``"other"`` so no rows are lost.
    """

    slug = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    sort_order = models.PositiveIntegerField(default=100)
    is_protected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "slug"]
        verbose_name_plural = "inventory categories"

    def __str__(self):
        return self.name

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        """Live ``(slug, name)`` pairs from this table, falling back to
        ``InventoryItem.CATEGORY_CHOICES`` if the table is empty
        (e.g. before the seeding migration runs).
        """
        rows = list(cls.objects.all().values_list("slug", "name"))
        if rows:
            return rows
        return list(InventoryItem.CATEGORY_CHOICES)

    @classmethod
    def is_protected_slug(cls, slug: str) -> bool:
        """A category is protected if it's the ``other`` fallback bucket
        or it's marked ``is_protected`` on the row. Both forms reach
        the same ``"cannot be deleted"`` answer.
        """
        if slug == "other":
            return True
        try:
            return cls.objects.get(slug=slug).is_protected
        except cls.DoesNotExist:
            return False

    @classmethod
    def add(
        cls,
        slug: str,
        name: str,
        sort_order: int = 100,
        is_protected: bool = False,
    ) -> "InventoryCategory":
        """Create-or-update a category by ``slug``.

        Slugs are immutable keys. Re-adding the same slug only updates
        ``name``/``sort_order`` so the rename flow on the settings
        page is idempotent. ``is_protected`` is only honoured on the
        initial create — once a category is protected, no caller can
        unlock it without going through the admin or a custom fixup.
        """
        row, _ = cls.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "sort_order": sort_order,
                "is_protected": is_protected,
            },
        )
        updated = False
        if row.name != name:
            row.name = name
            updated = True
        if row.sort_order != sort_order:
            row.sort_order = sort_order
            updated = True
        if updated:
            row.save(update_fields=["name", "sort_order", "updated_at"])
        return row
