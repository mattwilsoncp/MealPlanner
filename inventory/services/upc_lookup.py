import json
import logging
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi

from inventory.models import UpcLookupUsage


logger = logging.getLogger(__name__)

OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product"
UPC_LOOKUP_URL = "https://api.upcitemdb.com/prod/trial/lookup"
REQUEST_TIMEOUT_SECONDS = 5
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _record(service: str) -> None:
    """Bump today's usage counter for the given service.

    Never raises — quota monitoring is best-effort and must not break a
    real UPC lookup path.
    """
    try:
        UpcLookupUsage.record(service)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to record %s usage: %s", service, exc)


def _lookup_open_food_facts(barcode: str) -> dict | None:
    """Primary lookup via Open Food Facts (free, open source, no key needed)."""
    url = f"{OPEN_FOOD_FACTS_URL}/{barcode}.json"
    request = Request(url)
    request.add_header("User-Agent", "MealPlannerApp/1.0 (personal use)")
    _record("openfoodfacts")

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS, context=_SSL_CONTEXT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Open Food Facts lookup failed for %s: %s", barcode, exc)
        return None

    if payload.get("status") != 1:
        return None

    product = payload.get("product", {})
    if not product:
        return None

    title = (
        product.get("product_name", "")
        or product.get("product_name_en", "")
    ).strip()

    if not title:
        return None

    brand = (product.get("brands") or "").split(",")[0].strip()
    quantity = (product.get("quantity") or "").strip()
    image_url = product.get("image_front_small_url") or product.get("image_url") or ""
    categories = (product.get("categories") or "").split(",")
    category = categories[0].strip() if categories else ""

    return {
        "ok": True,
        "title": title,
        "brand": brand,
        "size": quantity,
        "image_url": image_url,
        "category": category,
        "barcode": barcode,
        "source": "Open Food Facts",
    }


def _lookup_upc_itemdb(barcode: str) -> dict | None:
    """Fallback lookup via UPC Item DB (free trial, 100 req/day)."""
    query = urlencode({"upc": barcode})
    request = Request(f"{UPC_LOOKUP_URL}?{query}")
    _record("upcitemdb")

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS, context=_SSL_CONTEXT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("UPC Item DB lookup failed for %s: %s", barcode, exc)
        return None

    item = (payload.get("items") or [None])[0]
    if not item:
        return None

    images = item.get("images") or []
    return {
        "ok": True,
        "title": item.get("title", "").strip(),
        "brand": item.get("brand", "").strip(),
        "size": item.get("size", "").strip(),
        "image_url": images[0] if images else "",
        "category": item.get("category", "").strip(),
        "barcode": barcode,
        "source": "UPC Item DB",
    }


def lookup_upc(barcode: str) -> dict:
    """Look up a barcode: Open Food Facts first, UPC Item DB as fallback."""
    result = _lookup_open_food_facts(barcode)
    if result:
        return result

    result = _lookup_upc_itemdb(barcode)
    if result:
        return result

    return {
        "ok": False,
        "error": "upc_not_found",
        "message": "No product found for this barcode.",
    }
