"""Enrich receipt-import items with barcode lookup data.

Builds on ``inventory.services.upc_lookup.lookup_upc`` (Open Food Facts first,
UPC Item DB fallback) to attach canonical product metadata — title, brand,
size, image, category — to any AI-extracted receipt item that has a valid
8–14 digit barcode. The result is rendered in the receipt review template
and used as a fallback when the user leaves review fields blank.
"""

import logging
import re

from inventory.services.upc_lookup import lookup_upc


logger = logging.getLogger(__name__)

# Matches the same pattern BarcodeLookupView / views.BARCODE_PATTERN uses.
BARCODE_PATTERN = re.compile(r"^\d{8,14}$")


def enrich_receipt_items(items, inventory_items=None):
    """Return ``(enrichment_map, enriched_items)`` for the given receipt items.

    ``items`` is the normalized list produced by ``ReceiptImportView._normalize_items``.
    ``inventory_items`` is an optional ``Iterable[InventoryItem]``; when provided,
    already-in-household matches are preferred over a fresh remote lookup so the
    review screen can flag them as "already in your inventory" exactly like the
    standalone barcode scan view does.

    Returns a dict keyed by receipt-item index (string) plus the same items list
    annotated with ``barcode_enrichment`` per item for convenience.
    """
    inventory_by_barcode = {}
    if inventory_items is not None:
        for inv_item in inventory_items:
            barcode = (inv_item.barcode or "").strip()
            if BARCODE_PATTERN.match(barcode):
                # First match per barcode wins so duplicates don't shadow each other.
                inventory_by_barcode.setdefault(barcode, inv_item)

    seen_barcodes = set()
    enriched_items = []
    enrichment_cache = {}
    for index, item in enumerate(items):
        enrichment = None
        raw_barcode = (item.get("barcode") or "").strip()

        if BARCODE_PATTERN.match(raw_barcode):
            if raw_barcode in seen_barcodes:
                # Repeat barcodes on a receipt hit the same product once.
                enrichment = enrichment_cache[raw_barcode]
            else:
                seen_barcodes.add(raw_barcode)
                enrichment = _build_enrichment(raw_barcode, inventory_by_barcode)
                enrichment_cache[raw_barcode] = enrichment

        enriched_items.append({**item, "barcode_enrichment": enrichment})

    enrichment_map = {
        str(index): entry["barcode_enrichment"]
        for index, entry in enumerate(enriched_items)
    }
    return enrichment_map, enriched_items


def _build_enrichment(barcode, inventory_by_barcode):
    local_item = inventory_by_barcode.get(barcode)
    if local_item is not None:
        return {
            "status": "local",
            "barcode": barcode,
            "title": local_item.name,
            "brand": _brand_from_notes(local_item.notes),
            "size": _size_from_notes(local_item.notes),
            "category": local_item.category,
            "image_url": local_item.image.url if local_item.image else "",
            "source": "local",
            "inventory_item_id": local_item.id,
            "message": "",
        }

    try:
        upc_result = lookup_upc(barcode)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Barcode enrichment lookup crashed for %s: %s", barcode, exc)
        return {
            "status": "error",
            "barcode": barcode,
            "title": "",
            "brand": "",
            "size": "",
            "category": "",
            "image_url": "",
            "source": "",
            "inventory_item_id": None,
            "message": "Lookup failed unexpectedly.",
        }

    if upc_result.get("ok"):
        return {
            "status": "upc",
            "barcode": barcode,
            "title": upc_result.get("title", ""),
            "brand": upc_result.get("brand", ""),
            "size": upc_result.get("size", ""),
            "category": _normalize_category(upc_result.get("category", "")),
            "image_url": upc_result.get("image_url", ""),
            "source": upc_result.get("source", "Open Food Facts"),
            "inventory_item_id": None,
            "message": "",
        }

    return {
        "status": "not_found",
        "barcode": barcode,
        "title": "",
        "brand": "",
        "size": "",
        "category": "",
        "image_url": "",
        "source": "",
        "inventory_item_id": None,
        "message": upc_result.get("message", "No product found for this barcode."),
    }


def _brand_from_notes(notes):
    if not notes:
        return ""
    for line in (notes or "").splitlines():
        if line.startswith("Brand:"):
            return line.split(":", 1)[1].strip()
    return ""


def _size_from_notes(notes):
    if not notes:
        return ""
    for line in (notes or "").splitlines():
        if line.startswith("Size:"):
            return line.split(":", 1)[1].strip()
    return ""


_CATEGORY_KEYWORDS = (
    ("produce", ("fruit", "vegetable", "produce", "plant")),
    ("dairy", ("dairy", "milk", "yogurt", "yoghurt", "cheese", "butter")),
    ("meat", ("meat", "beef", "pork", "chicken", "fish", "seafood")),
    ("frozen", ("frozen",)),
    ("pantry", ("pasta", "rice", "flour", "sugar", "salt", "spice", "sauce", "canned", "cereal", "oat")),
    ("beverages", ("beverage", "drink", "juice", "water", "soda", "tea", "coffee", "beer", "wine")),
    ("condiments", ("condiment", "oil", "vinegar", "ketchup", "mustard", "mayo")),
    ("snacks", ("snack", "chip", "cracker", "cookie", "candy", "chocolate")),
    ("bakery", ("bread", "bakery", "cake", "pastry")),
)


def _normalize_category(raw_category):
    category_tokens = [token.strip().lower() for token in (raw_category or "").split(",") if token.strip()]
    text_to_scan = " ".join(category_tokens)
    for value, keywords in _CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in text_to_scan:
                return value
    return ""
