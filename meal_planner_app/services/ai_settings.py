"""Per-household AI model resolution + OpenRouter catalog lookup.

The settings page at ``/tools/ai-models/`` lets a household pick a model
from the live OpenRouter catalog for each AI-using feature. This module
knows the feature list, populates the form dropdowns, and resolves the
right model id at call time.

Resolution precedence (highest first):
1. Caller-provided ``override`` (the per-request form field, if any).
2. ``AISettings.model_bindings[<feature_key>].model_id`` for the household.
3. ``FEATURE_DEFAULTS[<feature_key>]`` baked-in fallback.

The OpenRouter catalog is fetched from a public endpoint and cached in
process memory for ``OPENROUTER_CATALOG_TTL_SECONDS`` so the settings
page does not hammer the upstream on every request.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)


# Stable feature slugs used in URLs, JSON, and call-site arguments.
FEATURE_KEYS: dict[str, dict[str, Any]] = {
    "meal_plan_generation": {
        "label": "AI Meal Plan Generator",
        "needs_image": False,
        "default_model": "openrouter/free",
        "help": "Generates the weekly meal plan from your preferences + inventory.",
    },
    "recipe_import_text": {
        "label": "Recipe Import (URL / text)",
        "needs_image": False,
        "default_model": "google/gemini-2.0-flash-001",
        "help": "Extracts structured recipe data from a YouTube URL or pasted text.",
    },
    "recipe_import_image": {
        "label": "Recipe Import (photo)",
        "needs_image": True,
        "default_model": "google/gemini-2.0-flash-001",
        "help": "Reads a recipe photo and returns parsed ingredients / steps.",
    },
    "receipt_barcode": {
        "label": "Receipt / Barcode Enrichment",
        "needs_image": True,
        "default_model": "google/gemini-2.0-flash-001",
        "help": "Parses a grocery receipt photo and matches items to UPC.",
    },
}


# Public OpenRouter endpoint — no auth required for listing models.
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True)
class CatalogModel:
    """Trimmed projection of an OpenRouter model entry for the settings UI."""

    id: str
    name: str
    description: str
    is_free: bool
    supports_image_input: bool
    context_length: int

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "CatalogModel":
        pricing = payload.get("pricing") or {}
        # OpenRouter reports free models as the literal string "0". Anything
        # else is a paid model.
        prompt_price = str(pricing.get("prompt", ""))
        completion_price = str(pricing.get("completion", ""))
        is_free = prompt_price == "0" and completion_price == "0"

        architecture = payload.get("architecture") or {}
        input_modalities = architecture.get("input_modalities") or []
        supports_image = "image" in input_modalities

        return cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("id") or ""),
            description=str(payload.get("description") or ""),
            is_free=is_free,
            supports_image_input=supports_image,
            context_length=int(payload.get("context_length") or 0),
        )


class OpenRouterCatalog:
    """Process-wide cache of the OpenRouter /v1/models catalog."""

    _lock = threading.Lock()
    _cache: tuple[float, list[CatalogModel]] | None = None

    @classmethod
    def reset(cls) -> None:
        """Drop the in-memory cache (used by tests and the Refresh button)."""
        with cls._lock:
            cls._cache = None

    @classmethod
    def get_ttl_seconds(cls) -> int:
        try:
            return int(getattr(settings, "OPENROUTER_CATALOG_TTL_SECONDS", 600))
        except (TypeError, ValueError):
            return 600

    @classmethod
    def fetch(cls, *, force_refresh: bool = False) -> list[CatalogModel]:
        """Return the cached catalog, refreshing it when stale or forced."""
        ttl = cls.get_ttl_seconds()
        now = time.monotonic()
        with cls._lock:
            if not force_refresh and cls._cache is not None:
                fetched_at, models = cls._cache
                # Refresh slightly before TTL so we never serve a fully-stale
                # catalog on a long-running server.
                if now - fetched_at < ttl:
                    return models

        try:
            models = cls._download_catalog()
        except Exception as exc:  # pragma: no cover - network failures
            logger.warning("Failed to refresh OpenRouter catalog: %s", exc)
            with cls._lock:
                if cls._cache is not None:
                    # Serve last good value if the upstream blip is short-lived.
                    return cls._cache[1]
            raise

        with cls._lock:
            cls._cache = (now, models)
        return models

    @classmethod
    def _download_catalog(cls) -> list[CatalogModel]:
        """Hit the public /v1/models endpoint and project it."""
        timeout = float(getattr(settings, "OPENROUTER_CATALOG_TIMEOUT", 30))
        with httpx.Client(timeout=timeout) as client:
            response = client.get(OPENROUTER_MODELS_URL)
            response.raise_for_status()
            data = response.json()

        # OpenRouter may return {"data": [...]} or a bare list depending on
        # endpoint version. Normalize to a list of CatalogModel.
        entries = data.get("data") if isinstance(data, dict) else data
        if not isinstance(entries, list):
            raise ValueError("OpenRouter /v1/models returned an unexpected shape")

        catalog: list[CatalogModel] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                catalog.append(CatalogModel.from_api(entry))
            except (TypeError, ValueError) as exc:
                logger.debug("Skipping malformed catalog entry: %s", exc)
                continue
        # Stable order: free first (alphabetical), then paid (alphabetical).
        catalog.sort(key=lambda m: (not m.is_free, m.name.lower()))
        return catalog

    @classmethod
    def for_feature(cls, feature_key: str, *, force_refresh: bool = False) -> list[CatalogModel]:
        """Return catalog entries that the given feature can use."""
        spec = FEATURE_KEYS.get(feature_key)
        if spec is None:
            raise KeyError(f"Unknown AI feature key: {feature_key!r}")
        if not spec["needs_image"]:
            return cls.fetch(force_refresh=force_refresh)
        return [m for m in cls.fetch(force_refresh=force_refresh) if m.supports_image_input]


def resolve_model(
    household: Any | None,
    feature_key: str,
    override: str | None = None,
) -> str:
    """Pick the model id for *feature_key*.

    Precedence: ``override`` (per-request form value) → per-household binding →
    baked-in default.
    """
    if override and override.strip():
        return override.strip()

    if household is not None:
        try:
            from meal_planner_app.models import AISettings

            settings_row, _ = AISettings.objects.get_or_create(household=household)
            binding = settings_row.get_model(feature_key)
            if binding and binding.get("model_id"):
                return str(binding["model_id"])
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to read AISettings binding for %s: %s", feature_key, exc)

    spec = FEATURE_KEYS.get(feature_key)
    if spec is None:
        raise KeyError(f"Unknown AI feature key: {feature_key!r}")
    return str(spec["default_model"])


def resolve_openrouter_api_key(household: Any | None) -> str:
    """Return the OpenRouter key for this household, falling back to env."""
    if household is not None:
        try:
            from meal_planner_app.models import AISettings

            settings_row, _ = AISettings.objects.get_or_create(household=household)
            override = (settings_row.openrouter_api_key_override or "").strip()
            if override:
                return override
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to read AISettings API override: %s", exc)

    import os

    return os.environ.get("OPENROUTER_API_KEY", "").strip()
