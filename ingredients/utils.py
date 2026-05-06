"""
Unit conversion utilities for the meal planner app.

Uses grams (g) as the canonical base unit for weight.
Uses milliliters (ml) as the canonical base unit for volume.
"""

from decimal import Decimal
from typing import Union

# Conversion factors → grams (canonical weight)
# 1 oz = 28.3495g, 1 lb = 453.592g, 1 kg = 1000g
WEIGHT_TO_GRAMS = {
    "oz": Decimal("28.3495"),
    "lb": Decimal("453.592"),
    "kg": Decimal("1000"),
    "g": Decimal("1"),
}

# Conversion factors → milliliters (canonical volume)
# 1 l = 1000ml, 1 cup ≈ 236.588ml (US customary)
VOLUME_TO_ML = {
    "l": Decimal("1000"),
    "ml": Decimal("1"),
    "cup": Decimal("236.588"),
    "tbsp": Decimal("14.7868"),   # 1 tbsp ≈ 14.7868ml
    "tsp": Decimal("4.92892"),    # 1 tsp ≈ 4.92892ml
}

# Piece-based / count units — not convertible to mass/volume
COUNT_UNITS = {"piece", "clove", "slice", "bunch", "can", "whole"}


def convert_to_grams(value: Union[Decimal, float, str, int], unit: str) -> Decimal:
    """
    Convert a value from any supported unit to grams.

    Non-weight, non-volume units (piece, clove, etc.) return the value unchanged —
    they are count-based and not convertible to mass.

    Returns Decimal for precision.
    """
    value = Decimal(str(value))
    unit = unit.strip().lower()

    if unit in WEIGHT_TO_GRAMS:
        return (value * WEIGHT_TO_GRAMS[unit]).quantize(Decimal("0.01"))
    if unit in VOLUME_TO_ML:
        # Volume-to-grams assumes water-like density (1ml ≈ 1g).
        # This is an approximation — real conversion requires knowing density.
        return (value * VOLUME_TO_ML[unit]).quantize(Decimal("0.01"))
    if unit in COUNT_UNITS:
        return value
    return value  # Unknown unit — return as-is


def normalize_unit_key(name: str, unit: str) -> tuple[str, str]:
    """
    Return a (name, canonical_unit) key for inventory/recipe ingredient matching.

    Weights are normalized to 'g' (grams). Volumes are normalized to 'ml'.
    Count-based units are left as-is. This ensures '100g flour' matches '3oz flour'
    when computing available inventory against recipe needs.
    """
    name_key = (name or "").strip().casefold()
    unit = unit.strip().lower()

    if unit in WEIGHT_TO_GRAMS:
        return (name_key, "g")
    if unit in VOLUME_TO_ML:
        return (name_key, "ml")
    return (name_key, unit)


def convert_from_grams(grams: Decimal, to_unit: str) -> Decimal:
    """
    Convert a gram value back to a target unit.
    Used when aggregating mismatched units for display (e.g. total flour needed).
    """
    grams = Decimal(str(grams))
    unit = to_unit.strip().lower()

    if unit in WEIGHT_TO_GRAMS and WEIGHT_TO_GRAMS[unit] != 0:
        return (grams / WEIGHT_TO_GRAMS[unit]).quantize(Decimal("0.01"))
    if unit in VOLUME_TO_ML and VOLUME_TO_ML[unit] != 0:
        return (grams / VOLUME_TO_ML[unit]).quantize(Decimal("0.01"))
    return grams  # Unknown/count unit — return as-is
