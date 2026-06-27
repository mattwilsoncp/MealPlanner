import base64
import json
import os
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View, FormView
from django.views.generic.base import TemplateView
from openai import OpenAI

from .forms import InventoryItemForm, InventoryQuickAddForm, ReceiptImportForm
from .models import InventoryItem
from .services.receipt_barcode_enrichment import enrich_receipt_items
from .services.upc_lookup import lookup_upc


BARCODE_PATTERN = re.compile(r"^\d{8,14}$")


class InventoryListView(LoginRequiredMixin, ListView):
    model = InventoryItem
    template_name = "inventory/inventory_list.html"
    context_object_name = "items"

    def get_queryset(self):
        queryset = InventoryItem.objects.filter(household=self.request.user.household)

        query = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip()
        location = self.request.GET.get("location", "").strip()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(notes__icontains=query)
                | Q(barcode__icontains=query)
            )

        if category:
            queryset = queryset.filter(category=category)

        if location:
            queryset = queryset.filter(location=location)

        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grouped_items = {}

        for item in context["items"]:
            category_key = item.category or "other"
            grouped_items.setdefault(category_key, []).append(item)

        context["grouped_items"] = grouped_items
        context["category_choices"] = InventoryItem.CATEGORY_CHOICES
        context["location_choices"] = InventoryItem.LOCATION_CHOICES
        context["filters"] = {
            "q": self.request.GET.get("q", "").strip(),
            "category": self.request.GET.get("category", "").strip(),
            "location": self.request.GET.get("location", "").strip(),
        }
        return context


class InventoryCreateView(LoginRequiredMixin, CreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/inventory_form.html"
    success_url = reverse_lazy("inventory:inventory_list")

    def form_valid(self, form):
        form.instance.household = self.request.user.household
        return super().form_valid(form)


class InventoryUpdateView(LoginRequiredMixin, UpdateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/inventory_form.html"
    pk_url_kwarg = "item_id"
    success_url = reverse_lazy("inventory:inventory_list")

    def get_queryset(self):
        return InventoryItem.objects.filter(household=self.request.user.household)


class InventoryDeleteView(LoginRequiredMixin, DeleteView):
    model = InventoryItem
    pk_url_kwarg = "item_id"
    success_url = reverse_lazy("inventory:inventory_list")
    template_name = "inventory/inventory_list.html"

    @method_decorator(require_POST)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return InventoryItem.objects.filter(household=self.request.user.household)

    def form_valid(self, form):
        item_id = self.object.id
        item_name = self.object.name
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, f"Deleted item: {item_name}")
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "id": item_id, "name": item_name})
        return HttpResponseRedirect(success_url)


class InventoryExpiringView(LoginRequiredMixin, ListView):
    model = InventoryItem
    template_name = "inventory/inventory_expiring.html"
    context_object_name = "items"

    def get_queryset(self):
        today = timezone.localdate()
        threshold_date = today + timedelta(
            days=self.request.user.household.expiring_threshold_days
        )
        return InventoryItem.objects.filter(
            household=self.request.user.household,
            expiration_date__gte=today,
            expiration_date__lte=threshold_date,
        ).order_by("expiration_date", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context["expiring_items"] = context["items"]
        context["expired_items"] = InventoryItem.objects.filter(
            household=self.request.user.household,
            expiration_date__lt=today,
        ).order_by("expiration_date", "name")
        context["is_expired_page"] = False
        return context


class InventoryExpiredView(LoginRequiredMixin, ListView):
    model = InventoryItem
    template_name = "inventory/inventory_expiring.html"
    context_object_name = "items"

    def get_queryset(self):
        today = timezone.localdate()
        return InventoryItem.objects.filter(
            household=self.request.user.household,
            expiration_date__lt=today,
        ).order_by("expiration_date", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        threshold_date = today + timedelta(
            days=self.request.user.household.expiring_threshold_days
        )
        context["expired_items"] = context["items"]
        context["expiring_items"] = InventoryItem.objects.filter(
            household=self.request.user.household,
            expiration_date__gte=today,
            expiration_date__lte=threshold_date,
        ).order_by("expiration_date", "name")
        context["is_expired_page"] = True
        return context


class InventoryQuickAddView(LoginRequiredMixin, View):
    def _get_payload(self, request):
        if "application/json" in request.content_type:
            try:
                return json.loads(request.body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        return request.POST.dict()

    def post(self, request, *args, **kwargs):
        payload = self._get_payload(request)
        if payload is None:
            return JsonResponse(
                {"errors": {"__all__": [{"message": "Invalid JSON payload"}]}},
                status=400,
            )

        form = InventoryQuickAddForm(payload)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

        item = form.save(commit=False)
        item.household = request.user.household
        item.save()

        return JsonResponse(
            {
                "id": item.id,
                "name": item.name,
                "quantity": str(item.quantity),
                "unit": item.unit,
                "category": item.category,
                "location": item.location,
            },
            status=201,
        )


class BarcodeLookupView(LoginRequiredMixin, View):
    def _lookup(self, request, barcode):
        barcode = (barcode or "").strip()

        if not BARCODE_PATTERN.match(barcode):
            return JsonResponse(
                {
                    "error": "invalid_barcode",
                    "message": "Barcode must be 8 to 14 numeric digits.",
                },
                status=400,
            )

        local_item = InventoryItem.objects.filter(
            household=request.user.household,
            barcode=barcode,
        ).first()
        if local_item:
            return JsonResponse(
                {
                    "source": "local",
                    "item": {
                        "id": local_item.id,
                        "name": local_item.name,
                        "barcode": local_item.barcode,
                        "quantity": str(local_item.quantity),
                        "unit": local_item.unit,
                        "category": local_item.category,
                    },
                }
            )

        upc_result = lookup_upc(barcode)
        if not upc_result.get("ok"):
            return JsonResponse(
                {
                    "source": "upc",
                    "error": upc_result.get("error", "upc_lookup_failed"),
                    "message": upc_result.get(
                        "message",
                        "Unable to retrieve data from UPC service.",
                    ),
                },
                status=502,
            )

        return JsonResponse(
            {
                "source": "upc",
                "item": {
                    "title": upc_result.get("title", ""),
                    "brand": upc_result.get("brand", ""),
                    "size": upc_result.get("size", ""),
                    "image_url": upc_result.get("image_url", ""),
                    "category": upc_result.get("category", ""),
                    "barcode": upc_result.get("barcode", barcode),
                },
            }
        )

    def get(self, request, *args, **kwargs):
        return self._lookup(request, request.GET.get("barcode"))

    def post(self, request, *args, **kwargs):
        return self._lookup(request, request.POST.get("barcode"))


class BarcodeScanPageView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/barcode_scan.html"


class BarcodeCreateView(LoginRequiredMixin, View):
    ALLOWED_FIELDS = {"title", "brand", "size", "image_url", "category", "barcode"}

    def _normalize_payload(self, request):
        payload = request.POST.dict()
        return {key: (payload.get(key) or "").strip() for key in self.ALLOWED_FIELDS}

    def post(self, request, *args, **kwargs):
        payload = self._normalize_payload(request)
        barcode = payload.get("barcode", "")

        if not BARCODE_PATTERN.match(barcode):
            return JsonResponse(
                {
                    "error": "invalid_barcode",
                    "message": "Barcode must be 8 to 14 numeric digits.",
                },
                status=400,
            )

        existing_item = InventoryItem.objects.filter(
            household=request.user.household,
            barcode=barcode,
        ).first()
        if existing_item:
            return JsonResponse(
                {
                    "error": "duplicate_barcode",
                    "message": "An inventory item with this barcode already exists.",
                    "item_id": existing_item.id,
                },
                status=409,
            )

        category = payload.get("category")
        category_values = {value for value, _ in InventoryItem.CATEGORY_CHOICES}
        normalized_category = category if category in category_values else "other"

        notes_parts = []
        if payload.get("brand"):
            notes_parts.append(f"Brand: {payload['brand']}")
        if payload.get("size"):
            notes_parts.append(f"Size: {payload['size']}")
        if payload.get("image_url"):
            notes_parts.append(f"Image URL: {payload['image_url']}")

        item = InventoryItem.objects.create(
            household=request.user.household,
            name=payload.get("title") or "Scanned Item",
            barcode=barcode,
            category=normalized_category,
            location="pantry",
            quantity=1,
            unit="piece",
            notes="\n".join(notes_parts),
        )

        return JsonResponse(
            {
                "id": item.id,
                "name": item.name,
                "barcode": item.barcode,
                "category": item.category,
                "source": "upc",
            },
            status=201,
        )


class ReceiptImportView(LoginRequiredMixin, FormView):
    form_class = ReceiptImportForm
    template_name = "inventory/receipt_import.html"

    RECEIPT_PROMPT = """Extract grocery inventory items from this receipt image.
Return only valid JSON with this exact shape:
{
  "store": "string",
  "purchased_at": "YYYY-MM-DD or empty string",
  "items": [
    {
      "receipt_description": "string exactly as shown or best reading",
      "name": "clean pantry inventory name, or empty string if unclear",
      "quantity": "number as string, default 1",
      "unit": "piece|oz|lb|cup|tbsp|tsp|g|kg|ml|l|dozen|pack|box|can|bottle|bag",
      "category": "produce|dairy|meat|frozen|pantry|beverages|condiments|snacks|bakery|other",
      "location": "pantry|refrigerator|freezer|counter|cabinet",
      "price": "item price as string without currency symbol, or empty string",
      "barcode": "8-14 digit barcode if visible, else empty string",
      "confidence": "high|medium|low"
    }
  ]
}
Rules:
- Include groceries and household food items only.
- Exclude taxes, totals, payment lines, coupons, and fees.
- If an abbreviated receipt description is unclear, keep receipt_description, leave name empty, and set confidence to low.
- Use category/location based on food storage common sense.
- If quantity is not clear, use 1 and unit piece.
"""

    def form_valid(self, form):
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            form.add_error("image", "OPENROUTER_API_KEY is not configured.")
            return self.form_invalid(form)

        try:
            image_b64, content_type = self._prepare_image(form.cleaned_data["image"])
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
            response = client.chat.completions.create(
                model=form.cleaned_data.get("model") or "google/gemini-2.0-flash-001",
                messages=[
                    {
                        "role": "system",
                        "content": "You extract structured grocery receipt data and return strict JSON only.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.RECEIPT_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{content_type};base64,{image_b64}"},
                            },
                        ],
                    },
                ],
                temperature=0.1,
                max_tokens=6000,
            )
            parsed = self._extract_json_payload(response.choices[0].message.content or "")
            items = self._normalize_items(parsed.get("items", []))
            household_inventory = InventoryItem.objects.filter(
                household=self.request.user.household
            )
            enrichment_map, enriched_items = enrich_receipt_items(
                items, inventory_items=household_inventory
            )
            self.request.session["receipt_import"] = {
                "store": parsed.get("store", ""),
                "purchased_at": parsed.get("purchased_at", ""),
                "items": enriched_items,
                "barcode_enrichment": enrichment_map,
            }
            self.request.session.modified = True
            return redirect("inventory:receipt_import_review")
        except Exception as exc:
            form.add_error("image", f"Import failed: {exc}")
            return self.form_invalid(form)

    def _prepare_image(self, uploaded_image):
        from io import BytesIO
        from PIL import Image as PILImage

        max_bytes = 3_500_000
        max_dimension = 2048
        img = PILImage.open(uploaded_image)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)
        quality = 85
        while quality >= 20:
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            if buffer.tell() <= max_bytes:
                break
            quality -= 10
        return base64.b64encode(buffer.getvalue()).decode("utf-8"), "image/jpeg"

    def _extract_json_payload(self, raw_text):
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise RuntimeError("AI response was not a JSON object")
        return payload

    def _normalize_items(self, items):
        category_values = {value for value, _ in InventoryItem.CATEGORY_CHOICES}
        location_values = {value for value, _ in InventoryItem.LOCATION_CHOICES}
        unit_values = {value for value, _ in InventoryItem.UNIT_CHOICES}
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            receipt_description = str(item.get("receipt_description") or "").strip()
            name = str(item.get("name") or "").strip()
            if not receipt_description and not name:
                continue
            normalized.append(
                {
                    "receipt_description": receipt_description,
                    "name": name,
                    "quantity": str(item.get("quantity") or "1").strip() or "1",
                    "unit": item.get("unit") if item.get("unit") in unit_values else "piece",
                    "category": item.get("category") if item.get("category") in category_values else "other",
                    "location": item.get("location") if item.get("location") in location_values else "pantry",
                    "price": str(item.get("price") or "").strip(),
                    "barcode": str(item.get("barcode") or "").strip(),
                    "confidence": item.get("confidence") if item.get("confidence") in {"high", "medium", "low"} else "low",
                }
            )
        return normalized


class ReceiptImportReviewView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/receipt_import_review.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        receipt_import = self.request.session.get("receipt_import") or {}
        raw_items = receipt_import.get("items", [])
        enrichment_map = receipt_import.get("barcode_enrichment", {}) or {}
        context["receipt"] = receipt_import
        context["items"] = [
            {**item, "barcode_enrichment": enrichment_map.get(str(index), item.get("barcode_enrichment"))}
            for index, item in enumerate(raw_items)
        ]
        context["barcode_enrichment"] = enrichment_map
        context["category_choices"] = InventoryItem.CATEGORY_CHOICES
        context["location_choices"] = InventoryItem.LOCATION_CHOICES
        context["unit_choices"] = InventoryItem.UNIT_CHOICES
        context["existing_items"] = InventoryItem.objects.filter(
            household=self.request.user.household
        ).order_by("name")
        return context

    def post(self, request, *args, **kwargs):
        receipt_import = request.session.get("receipt_import") or {}
        source_items = receipt_import.get("items", [])
        enrichment_map = receipt_import.get("barcode_enrichment", {}) or {}
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for index, _source_item in enumerate(source_items):
            if not request.POST.get(f"items-{index}-include"):
                skipped_count += 1
                continue

            existing_id = request.POST.get(f"items-{index}-existing_item", "").strip()
            name = request.POST.get(f"items-{index}-name", "").strip()
            quantity = self._parse_decimal(request.POST.get(f"items-{index}-quantity"), Decimal("1"))
            unit = request.POST.get(f"items-{index}-unit") or "piece"
            category = request.POST.get(f"items-{index}-category") or "other"
            location = request.POST.get(f"items-{index}-location") or "pantry"
            barcode = request.POST.get(f"items-{index}-barcode", "").strip()
            price = request.POST.get(f"items-{index}-price", "").strip()
            receipt_description = request.POST.get(f"items-{index}-receipt_description", "").strip()

            enrichment = enrichment_map.get(str(index)) or {}
            enriched_title = (enrichment.get("title") or "").strip()
            enriched_brand = (enrichment.get("brand") or "").strip()
            enriched_size = (enrichment.get("size") or "").strip()
            enriched_image = (enrichment.get("image_url") or "").strip()
            enrichment_status = enrichment.get("status")

            if existing_id:
                item = InventoryItem.objects.filter(
                    household=request.user.household,
                    pk=existing_id,
                ).first()
                if not item:
                    skipped_count += 1
                    continue
                item.quantity = item.quantity + quantity
                item.unit = unit or item.unit
                item.category = category or item.category
                item.location = location or item.location
                if barcode:
                    item.barcode = barcode
                enrichment_notes = self._build_enrichment_notes(
                    enrichment_status,
                    enriched_brand,
                    enriched_size,
                    enriched_image,
                    enrichment_status == "local",
                )
                item.notes = self._merge_notes(
                    self._merge_notes(item.notes, receipt_description, price),
                    enrichment_notes,
                    "",
                )
                item.save()
                updated_count += 1
                continue

            if not name and enriched_title:
                name = enriched_title

            if not name:
                skipped_count += 1
                continue

            category = category if category != "other" else (enrichment.get("category") or category)

            enrichment_notes = self._build_enrichment_notes(
                enrichment_status,
                enriched_brand,
                enriched_size,
                enriched_image,
                False,
            )
            notes = self._merge_notes(
                self._build_notes(receipt_description, price),
                enrichment_notes,
                "",
            )

            InventoryItem.objects.create(
                household=request.user.household,
                name=name,
                quantity=quantity,
                unit=unit,
                category=category,
                location=location,
                barcode=barcode,
                notes=notes,
            )
            created_count += 1

        request.session.pop("receipt_import", None)
        messages.success(
            request,
            f"Receipt import complete: {created_count} created, {updated_count} updated, {skipped_count} skipped.",
        )
        return redirect("inventory:inventory_list")

    def _parse_decimal(self, raw_value, default):
        try:
            return Decimal(str(raw_value or "").strip())
        except (InvalidOperation, ValueError):
            return default

    def _build_notes(self, receipt_description, price):
        notes = []
        if receipt_description:
            notes.append(f"Receipt description: {receipt_description}")
        if price:
            notes.append(f"Receipt price: ${price}")
        return "\n".join(notes)

    def _merge_notes(self, existing_notes, receipt_description, price):
        receipt_notes = self._build_notes(receipt_description, price)
        if existing_notes and receipt_notes:
            return f"{existing_notes}\n{receipt_notes}"
        return existing_notes or receipt_notes

    def _build_enrichment_notes(
        self, status, brand, size, image_url, is_local
    ):
        if not status or status not in {"upc", "local"}:
            return ""
        prefix = "UPC enrichment" if status == "upc" else "UPC match"
        parts = [prefix]
        if brand:
            parts.append(f"Brand: {brand}")
        if size:
            parts.append(f"Size: {size}")
        if image_url and not is_local:
            parts.append(f"Image URL: {image_url}")
        return " · ".join(parts)
