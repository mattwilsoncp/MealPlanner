from django.db import migrations, models


def migrate_store_text_to_fk(apps, schema_editor):
    """For each household, create one Store row per distinct non-empty
    ``InventoryItem.store`` value and link the existing items."""

    InventoryItem = apps.get_model("inventory", "InventoryItem")
    Store = apps.get_model("inventory", "Store")

    households_to_store_names = {}
    for item in InventoryItem.objects.exclude(store__exact=""):
        households_to_store_names.setdefault(item.household_id, set()).add(item.store)

    household_to_pk_by_name = {}
    for household_id, names in households_to_store_names.items():
        for name in sorted(names):
            store = Store.objects.create(household_id=household_id, name=name)
            household_to_pk_by_name[(household_id, name)] = store.pk

    for item in InventoryItem.objects.exclude(store__exact=""):
        item.store_fk_id = household_to_pk_by_name[(item.household_id, item.store)]
        item.save(update_fields=["store_fk"])


def reverse_noop(apps, schema_editor):
    # Removing the FK is the reverse of step 4; nothing custom to undo.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("household", "0002_household_expiring_threshold_days"),
        ("inventory", "0003_inventoryitem_price_inventoryitem_store"),
    ]

    operations = [
        migrations.CreateModel(
            name="Store",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "household",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="stores",
                        to="household.household",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="store_fk",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="inventory_items",
                to="inventory.store",
            ),
        ),
        migrations.RunPython(migrate_store_text_to_fk, reverse_noop),
        migrations.RemoveField(
            model_name="inventoryitem",
            name="store",
        ),
        migrations.RenameField(
            model_name="inventoryitem",
            old_name="store_fk",
            new_name="store",
        ),
        migrations.AlterUniqueTogether(
            name="store",
            unique_together={("household", "name")},
        ),
    ]
