"""USDA FoodData Central lookup service.

Tiny wrapper around the public FDC ``/v1/foods/search`` endpoint used to
link an Ingredient row to the canonical USDA entry and import a
kcal / protein / carbs / fat snapshot per 100 g. The endpoint is gated
by an ``api_key`` query parameter — see :data:`USDA_FDC_API_KEY` in
``meal_planner/settings.py``.

The service mirrors the process-wide TTL cache pattern used by
``meal_planner_app.services.ai_settings.OpenRouterCatalog`` so the
settings + recipe pages do not hammer the upstream on every request.

Nutrient-id mapping (from the FDC standard reference):

* calories_kcal → ``1008`` (Energy), with ``2047`` (Energy Atwater
  General Factors) accepted as a fallback when the Foundation dataset
  reports energy under that newer id.
* protein_g → ``1003`` (Protein).
* carbs_g → ``1005`` (Carbohydrate, by difference).
* fat_g → ``1004`` (Total lipid (fat)).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)


# FDC nutrient ids we know how to import.
FDC_NUTRIENT_ENERGY_KCAL = 1008
FDC_NUTRIENT_ENERGY_ATWATER = 2047
FDC_NUTRIENT_PROTEIN = 1003
FDC_NUTRIENT_FAT = 1004
FDC_NUTRIENT_CARBS = 1005


class USDAAPIError(Exception):
    """Raised when the USDA FDC API call fails or returns malformed data.

    The view translates this into a friendly form error so the user can
    retry without the upstream blip taking down the whole page.
    """


@dataclass(frozen=True)
class USDAMatch:
    """A single USDA FoodData Central entry, projected for the UI."""

    fdc_id: int
    description: str
    data_type: str
    brand_name: str
    calories_kcal: Decimal | None
    protein_g: Decimal | None
    carbs_g: Decimal | None
    fat_g: Decimal | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "USDAMatch":
        return cls(
            fdc_id=int(payload.get("fdcId") or 0),
            description=str(payload.get("description") or "").strip(),
            data_type=str(payload.get("dataType") or "").strip(),
            brand_name=str(payload.get("brandName") or "").strip(),
            calories_kcal=_pick_energy_kcal(payload.get("foodNutrients") or []),
            protein_g=_pick_nutrient(payload.get("foodNutrients") or [], FDC_NUTRIENT_PROTEIN),
            carbs_g=_pick_nutrient(payload.get("foodNutrients") or [], FDC_NUTRIENT_CARBS),
            fat_g=_pick_nutrient(payload.get("foodNutrients") or [], FDC_NUTRIENT_FAT),
        )

    def has_macros(self) -> bool:
        return any(
            v is not None
            for v in (self.calories_kcal, self.protein_g, self.carbs_g, self.fat_g)
        )


class USFACatalog:
    """Process-wide TTL cache of USDA FoodData Central search results.

    Cache is keyed by ``(query, page_size, data_types)`` so the same
    recipe-page refresh doesn't repeat identical searches. The lock
    makes the cache safe under Django's threaded dev server.
    """

    _lock = threading.Lock()
    _cache: dict[tuple[str, int, tuple[str, ...] | None], tuple[float, list[USDAMatch]]] = {}

    @classmethod
    def reset(cls) -> None:
        """Drop the in-memory cache (used by tests)."""
        with cls._lock:
            cls._cache = {}

    @classmethod
    def get_ttl_seconds(cls) -> int:
        try:
            return int(getattr(settings, "USDA_FDC_CACHE_TTL_SECONDS", 3600))
        except (TypeError, ValueError):
            return 3600

    @classmethod
    def get_timeout(cls) -> float:
        try:
            return float(getattr(settings, "USDA_FDC_TIMEOUT", 20))
        except (TypeError, ValueError):
            return 20.0

    @classmethod
    def get_base_url(cls) -> str:
        return getattr(settings, "USDA_FDC_SEARCH_URL", "https://api.nal.usda.gov/fdc/v1/foods/search")

    @classmethod
    def search(
        cls,
        query: str,
        *,
        page_size: int = 10,
        data_types: list[str] | None = None,
        api_key: str | None = None,
        force_refresh: bool = False,
    ) -> list[USDAMatch]:
        """Return matches for ``query``.

        ``data_types``, when provided, filters the upstream to those
        datasets (e.g. ``["Foundation"]``). Empty/missing macros don't
        filter the result out — they just leave the macro display blank.
        """
        query = (query or "").strip()
        if not query:
            return []

        cache_key = (
            query.casefold(),
            int(page_size),
            tuple(dt.strip() for dt in (data_types or []) if dt.strip()) or None,
        )
        ttl = cls.get_ttl_seconds()
        now = time.monotonic()
        if not force_refresh:
            with cls._lock:
                cached = cls._cache.get(cache_key)
            if cached is not None:
                fetched_at, matches = cached
                if now - fetched_at < ttl:
                    return matches

        key = (api_key or "").strip() or resolve_usda_api_key(None)
        try:
            matches = cls._download(query, page_size, data_types, key)
        except Exception as exc:
            logger.warning("USDA FDC search failed for %r: %s", query, exc)
            with cls._lock:
                cached = cls._cache.get(cache_key)
                if cached is not None:
                    # Serve last good value if available.
                    return cached[1]
            raise

        with cls._lock:
            cls._cache[cache_key] = (now, matches)
        return matches

    @classmethod
    def _download(
        cls,
        query: str,
        page_size: int,
        data_types: list[str] | None,
        api_key: str,
    ) -> list[USDAMatch]:
        url = cls.get_base_url()
        params: dict[str, Any] = {
            "query": query,
            "pageSize": max(1, min(int(page_size) or 10, 50)),
            "api_key": api_key,
        }
        if data_types:
            params["dataType"] = data_types

        timeout = cls.get_timeout()
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise USDAAPIError(f"USDA search failed: {exc}") from exc
        except ValueError as exc:
            raise USDAAPIError("USDA search returned non-JSON") from exc

        foods = data.get("foods") if isinstance(data, dict) else None
        if not isinstance(foods, list):
            raise USDAAPIError("USDA search payload was not a list of foods")

        matches: list[USDAMatch] = []
        for entry in foods:
            if not isinstance(entry, dict):
                continue
            try:
                matches.append(USDAMatch.from_api(entry))
            except (TypeError, ValueError) as exc:
                logger.debug("Skipping malformed USDA entry: %s", exc)
                continue
        return matches


def _pick_nutrient(nutrients: list[dict[str, Any]], nutrient_id: int) -> Decimal | None:
    """Return the value for ``nutrient_id`` from a FDC foodNutrients list, or None."""
    for entry in nutrients:
        if not isinstance(entry, dict):
            continue
        if int(entry.get("nutrientId") or 0) == nutrient_id:
            value = entry.get("value")
            if value is None:
                return None
            try:
                d = Decimal(str(value))
            except Exception:
                return None
            # Drop very-near zero to keep the snapshot column null when the
            # upstream says "0" with a unit we don't import.
            return d if d != 0 else Decimal("0")
    return None


def _pick_energy_kcal(nutrients: list[dict[str, Any]]) -> Decimal | None:
    """Pick energy in KCAL across both classic (1008) and Foundation (2047) ids."""
    primary = _pick_nutrient(nutrients, FDC_NUTRIENT_ENERGY_KCAL)
    if primary is not None:
        return primary
    fallback = _pick_nutrient(nutrients, FDC_NUTRIENT_ENERGY_ATWATER)
    if fallback is not None:
        return fallback
    # Walk the list looking for an entry with unitName == "KCAL". This
    # covers cases where FDC adds new energy ids in future.
    for entry in nutrients:
        if not isinstance(entry, dict):
            continue
        unit = str(entry.get("unitName") or "").upper()
        if unit != "KCAL":
            continue
        value = entry.get("value")
        if value is None:
            continue
        try:
            return Decimal(str(value))
        except Exception:
            continue
    return None


def resolve_usda_api_key(household: Any | None = None) -> str:
    """Return the USDA FDC API key for the calling household.

    Precedence (highest first):

    1. Per-household ``AISettings.usda_fdc_api_key_override`` (so a
       single household can route ingredient lookups through their own
       FDC account when the free DEMO_KEY rate-limit is too tight).
    2. ``USDA_FDC_API_KEY`` env binding (set by the operator).
    3. ``"DEMO_KEY"`` literal — the upstream default for unauthenticated
       development usage.

    The ``household`` argument is optional so CLI callers and tests can
    omit it without ceremony; the resolver then skips step 1.
    """
    if household is not None:
        try:
            from meal_planner_app.models import AISettings

            settings_row, _ = AISettings.objects.get_or_create(household=household)
            override = (settings_row.usda_fdc_api_key_override or "").strip()
            if override:
                return override
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to read AISettings USDA override: %s", exc)

    return getattr(settings, "USDA_FDC_API_KEY", "DEMO_KEY")
