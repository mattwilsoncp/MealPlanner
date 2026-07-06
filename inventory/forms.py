from django import forms

from .models import InventoryItem, InventoryCategory, Store


class BaseInventoryItemForm(forms.ModelForm):
    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household is not None:
            self.fields["store"].queryset = Store.objects.filter(household=household)
        else:
            self.fields["store"].queryset = Store.objects.none()

        # Categories come from the runtime InventoryCategory table,
        # not InventoryItem.CATEGORY_CHOICES, so the inventory
        # settings page can add / remove entries that show up
        # everywhere a category is offered.
        self.fields["category"].choices = InventoryCategory.choices()

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")

        if quantity is not None and quantity < 0:
            raise forms.ValidationError("Quantity cannot be negative.")

        return quantity

    def clean_price(self):
        price = self.cleaned_data.get("price")

        if price is not None and price < 0:
            raise forms.ValidationError("Price cannot be negative.")

        return price


class InventoryItemForm(BaseInventoryItemForm):
    class Meta:
        model = InventoryItem
        fields = [
            "name",
            "quantity",
            "unit",
            "category",
            "location",
            "expiration_date",
            "price",
            "store",
            "notes",
            "image",
            "barcode",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered"}),
            "quantity": forms.NumberInput(
                attrs={"class": "input input-bordered", "step": "0.01", "min": "0"}
            ),
            "unit": forms.Select(attrs={"class": "select select-bordered"}),
            "category": forms.Select(attrs={"class": "select select-bordered"}),
            "location": forms.Select(attrs={"class": "select select-bordered"}),
            "expiration_date": forms.DateInput(
                attrs={"type": "date", "class": "input input-bordered"}
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "input input-bordered",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),
            "store": forms.Select(attrs={"class": "select select-bordered"}),
            "notes": forms.Textarea(attrs={"class": "textarea textarea-bordered"}),
            "image": forms.ClearableFileInput(
                attrs={"class": "file-input file-input-bordered"}
            ),
            "barcode": forms.TextInput(attrs={"class": "input input-bordered"}),
        }


class InventoryQuickAddForm(BaseInventoryItemForm):
    class Meta(InventoryItemForm.Meta):
        pass


class InventoryCategoryForm(forms.ModelForm):
    """Add/edit form for the inventory-settings category table.

    ``slug`` is read-only on edit (it's the immutable join key for
    ``InventoryItem.category``) and editable on add so the user can
    type a fresh identifier. ``is_protected`` is gated to the
    server side — the settings UI never offers it; only the
    seed migration marks ``other`` protected.
    """

    class Meta:
        model = InventoryCategory
        fields = ["slug", "name", "sort_order"]
        widgets = {
            "slug": forms.TextInput(attrs={"class": "input-dark", "maxlength": 32}),
            "name": forms.TextInput(attrs={"class": "input-dark", "maxlength": 64}),
            "sort_order": forms.NumberInput(
                attrs={"class": "input-dark", "min": 0, "max": 9999}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Slug is a join key — keep it read-only on edit so
            # ``InventoryItem.category`` rows don't go stale.
            self.fields["slug"].widget.attrs["readonly"] = "readonly"
            self.fields["slug"].help_text = (
                "Slug is the immutable key used to join inventory "
                "items. Renaming only changes the display label."
            )
            if self.instance.is_protected or self.instance.slug == "other":
                # Lock the row visually so the user understands
                # the label here is the protected bucket.
                self.fields["name"].help_text = (
                    "Protected category — name can still change but "
                    "the slug stays locked so the Other/Uncategorized "
                    "fallback bucket always exists."
                )

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            raise forms.ValidationError("Slug cannot be empty.")
        # Keep slugs lowercase to match the storage convention.
        slug = slug.lower()
        return slug


class ReceiptImportForm(forms.Form):
    image = forms.ImageField(
        label="Receipt Photo",
        widget=forms.FileInput(
            attrs={
                "class": "input-dark",
                "accept": "image/*",
                "capture": "environment",
            }
        ),
    )
    model = forms.ChoiceField(
        label="AI Model",
        choices=[
            ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash (Paid, Fast)"),
            ("anthropic/claude-sonnet-4", "Claude Sonnet 4 (Paid, Best)"),
            ("google/gemini-2.5-pro-preview-06-05", "Gemini 2.5 Pro (Paid, Premium)"),
        ],
        initial="google/gemini-2.0-flash-001",
        required=False,
        widget=forms.Select(attrs={"class": "input-dark"}),
    )
    store = forms.ModelChoiceField(
        label="Receipt From (Optional)",
        queryset=Store.objects.none(),
        required=False,
        empty_label="Auto-detect from receipt",
        widget=forms.Select(attrs={"class": "input-dark"}),
        help_text="Override the AI-detected store; leave on auto-detect to trust the receipt.",
    )

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household is not None:
            self.fields["store"].queryset = Store.objects.filter(household=household)
        else:
            self.fields["store"].queryset = Store.objects.none()
