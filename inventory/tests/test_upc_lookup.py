import pytest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

from inventory.services.upc_lookup import lookup_upc, UPC_LOOKUP_URL, REQUEST_TIMEOUT_SECONDS


class TestLookupUpc:
    """Tests for the lookup_upc function."""

    def _build_response(self, data: dict, status: int = 200):
        """Helper to build a mock HTTP response."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items": []}'  # default
        if data:
            mock_response.read.return_value = str(data).replace("'", '"').encode("utf-8")
        return mock_response

    # ---- Success cases ----

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_success_with_all_fields(self, mock_urlopen):
        """Full response with all fields returns ok=True and all keys."""
        payload = {
            "items": [
                {
                    "title": "  Organic Oat Milk  ",
                    "brand": "  Califa  ",
                    "size": " 64 oz ",
                    "images": ["https://example.com/img.jpg", "https://example.com/img2.jpg"],
                    "category": " Food & Beverage ",
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items": [{"title":"  Organic Oat Milk  ","brand":"  Califa  ","size":" 64 oz ","images":["https://example.com/img.jpg","https://example.com/img2.jpg"],"category":" Food & Beverage "}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = lookup_upc("012345678901")

        assert result["ok"] is True
        assert result["title"] == "Organic Oat Milk"
        assert result["brand"] == "Califa"
        assert result["size"] == "64 oz"
        assert result["image_url"] == "https://example.com/img.jpg"
        assert result["category"] == "Food & Beverage"
        assert result["barcode"] == "012345678901"

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_success_with_empty_images(self, mock_urlopen):
        """Success but images list is empty -> image_url is empty string."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items":[{"title":"Milk","brand":"","size":"","images":[],"category":"Dairy"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = lookup_upc("111")

        assert result["ok"] is True
        assert result["image_url"] == ""

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_success_with_no_images_key(self, mock_urlopen):
        """Success but 'images' key is absent -> image_url is empty string."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items":[{"title":"Milk","brand":"","size":"","category":"Dairy"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = lookup_upc("222")

        assert result["ok"] is True
        assert result["image_url"] == ""

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_success_with_only_title(self, mock_urlopen):
        """Response with only title; brand/size/category blank -> stripped to empty."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items":[{"title":"  Coffee  "}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = lookup_upc("333")

        assert result["ok"] is True
        assert result["title"] == "Coffee"
        assert result["brand"] == ""
        assert result["size"] == ""
        assert result["category"] == ""
        assert result["image_url"] == ""

    # ---- UPC not found cases ----

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_items_null(self, mock_urlopen):
        """payload['items'] is None -> upc_not_found."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items":null}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = lookup_upc("000")

        assert result["ok"] is False
        assert result["error"] == "upc_not_found"
        assert "No UPC result found" in result["message"]

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_items_empty_list(self, mock_urlopen):
        """payload['items'] is empty list -> upc_not_found."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"items":[]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = lookup_upc("000")

        assert result["ok"] is False
        assert result["error"] == "upc_not_found"
        assert "No UPC result found" in result["message"]

    # ---- Exception cases ----

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_http_error(self, mock_urlopen):
        """HTTPError returns ok=False with upc_lookup_failed."""
        mock_urlopen.side_effect = HTTPError(
            url="https://api.upcitemdb.com",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        result = lookup_upc("999")

        assert result["ok"] is False
        assert result["error"] == "upc_lookup_failed"
        assert "UPC lookup failed" in result["message"]

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_url_error(self, mock_urlopen):
        """URLError returns ok=False with upc_lookup_failed."""
        mock_urlopen.side_effect = URLError("Connection refused")

        result = lookup_upc("999")

        assert result["ok"] is False
        assert result["error"] == "upc_lookup_failed"
        assert "UPC lookup failed" in result["message"]

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_timeout_error(self, mock_urlopen):
        """TimeoutError returns ok=False with upc_lookup_failed."""
        mock_urlopen.side_effect = TimeoutError("timed out")

        result = lookup_upc("999")

        assert result["ok"] is False
        assert result["error"] == "upc_lookup_failed"
        assert "UPC lookup failed" in result["message"]

    @patch("inventory.services.upc_lookup.urlopen")
    def test_lookup_upc_json_decode_error(self, mock_urlopen):
        """Invalid JSON returns ok=False with upc_lookup_failed."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = lookup_upc("999")

        assert result["ok"] is False
        assert result["error"] == "upc_lookup_failed"
        assert "UPC lookup failed" in result["message"]

    # ---- Module constants ----

    def test_constants(self):
        """Verify module-level constants are set correctly."""
        assert UPC_LOOKUP_URL == "https://api.upcitemdb.com/prod/trial/lookup"
        assert REQUEST_TIMEOUT_SECONDS == 3