import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


UPC_LOOKUP_URL = "https://api.upcitemdb.com/prod/trial/lookup"
REQUEST_TIMEOUT_SECONDS = 3


def lookup_upc(barcode: str) -> dict:
    query = urlencode({"upc": barcode})
    request = Request(f"{UPC_LOOKUP_URL}?{query}")

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": "upc_lookup_failed",
            "message": f"UPC lookup failed: {exc}",
        }

    item = (payload.get("items") or [None])[0]
    if not item:
        return {
            "ok": False,
            "error": "upc_not_found",
            "message": "No UPC result found for this barcode.",
        }

    images = item.get("images") or []
    return {
        "ok": True,
        "title": item.get("title", "").strip(),
        "brand": item.get("brand", "").strip(),
        "size": item.get("size", "").strip(),
        "image_url": images[0] if images else "",
        "category": item.get("category", "").strip(),
        "barcode": barcode,
    }
