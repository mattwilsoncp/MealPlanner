from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import InventoryItem


class InventoryListView(LoginRequiredMixin, ListView):
    """List all inventory items for the user's household."""

    model = InventoryItem
    template_name = "inventory/inventory_list.html"
    context_object_name = "items"

    def get_queryset(self):
        return InventoryItem.objects.filter(
            household=self.request.user.household
        ).order_by("name")


@method_decorator(csrf_exempt, name="dispatch")
class InventoryCreateAPIView(LoginRequiredMixin, CreateView):
    """Create inventory item via JSON API."""

    model = InventoryItem
    fields = [
        "name",
        "quantity",
        "unit",
        "category",
        "location",
        "expiration_date",
        "notes",
    ]
    template_name = "inventory/inventory_form.html"

    def get_success_url(self):
        return reverse_lazy("inventory:inventory_list")

    def form_valid(self, form):
        form.instance.household = self.request.user.household
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        if request.headers.get("Content-Type") == "application/json":
            import json

            try:
                data = json.loads(request.body)
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
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=400)
        return super().post(request, *args, **kwargs)
