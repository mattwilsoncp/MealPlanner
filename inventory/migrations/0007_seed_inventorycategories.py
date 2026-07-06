"""Seed the ``InventoryCategory`` table from the historical
``InventoryItem.CATEGORY_CHOICES`` defaults.

The inventory settings page is now backed by ``InventoryCategory``
rows rather than a hardcoded ``choices=`` tuple on the model. To
keep pages rendering identically for users on the freshly-migrated
database, we seed each ``(slug, name)`` from the original list and
mark ``other`` as protected so it can never be deleted.

Re-runs of this migration are idempotent (``get_or_create``).
"""

from django.db import migrations


SEED_ROWS = [
    ("produce", "Produce", 10, False),
    ("dairy", "Dairy", 20, False),
    ("meat", "Meat & Seafood", 30, False),
    ("frozen", "Frozen", 40, False),
    ("pantry", "Pantry", 50, False),
    ("beverages", "Beverages", 60, False),
    ("condiments", "Condiments & Sauces", 70, False),
    ("snacks", "Snacks", 80, False),
    ("bakery", "Bakery", 90, False),
    ("other", "Other", 999, True),
]


def seed(apps, schema_editor):
    InventoryCategory = apps.get_model("inventory", "InventoryCategory")
    for slug, name, sort_order, is_protected in SEED_ROWS:
        InventoryCategory.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "sort_order": sort_order,
                "is_protected": is_protected,
            },
        )


def unseed(apps, schema_editor):
    InventoryCategory = apps.get_model("inventory", "InventoryCategory")
    InventoryCategory.objects.filter(
        slug__in=[row[0] for row in SEED_ROWS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_inventorycategory"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
