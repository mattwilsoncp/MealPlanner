import json
import re
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View
from django.views.generic.base import TemplateView

from .forms import InventoryItemForm, InventoryQuickAddForm
from .models import InventoryItem
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

    def get_queryset(self):
        return InventoryItem.objects.filter(household=self.request.user.household)


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
