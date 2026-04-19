from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import InventoryItemForm
from .models import InventoryItem


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
    template_name = "inventory/inventory_list.html"
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


class InventoryExpiredView(LoginRequiredMixin, ListView):
    model = InventoryItem
    template_name = "inventory/inventory_list.html"
    context_object_name = "items"

    def get_queryset(self):
        today = timezone.localdate()
        return InventoryItem.objects.filter(
            household=self.request.user.household,
            expiration_date__lt=today,
        ).order_by("expiration_date", "name")


@method_decorator(csrf_exempt, name="dispatch")
class InventoryQuickAddAPIView(LoginRequiredMixin, CreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/inventory_form.html"
    success_url = reverse_lazy("inventory:inventory_list")

    def form_valid(self, form):
        form.instance.household = self.request.user.household
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        if request.headers.get("Content-Type") == "application/json":
            import json

            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON payload"}, status=400)

            item = InventoryItem.objects.create(
                household=request.user.household,
                name=data.get("name"),
                quantity=data.get("quantity", 1),
                unit=data.get("unit", "piece"),
                category=data.get("category", "other"),
                location=data.get("location", "pantry"),
                expiration_date=data.get("expiration_date"),
                notes=data.get("notes", ""),
            )
            return JsonResponse({"id": item.id, "name": item.name}, status=201)

        return super().post(request, *args, **kwargs)
