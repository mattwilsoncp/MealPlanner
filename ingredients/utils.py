"""
Unit conversion utilities for the meal planner app.

Uses grams (g) as the canonical base unit for weight.
Uses milliliters (ml) as the canonical base unit for volume.
"""

from dataclasses import dataclass, field
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


# Set of units where we cannot convert to a mass without more info.
# USED by summarize_linked_nutrition to call out skipped rows explicitly
# in the recipe-level summary card rather than silently dropping them.
UNCONVERTIBLE_UNITS = frozenset(COUNT_UNITS)


@dataclass
class LinkedNutritionSummary:
    """Per-100g-style totals rolled up across all USDA-linked rows."""

    linked_count: int = 0                     # contributed to the totals
    needs_attention_count: int = 0            # linked row that could not be measured
    total_count: int = 0                      # every IngredientLink in the recipe
    skipped: list = field(default_factory=list)
    calories_kcal: Decimal = Decimal("0")
    protein_g: Decimal = Decimal("0")
    carbs_g: Decimal = Decimal("0")
    fat_g: Decimal = Decimal("0")

    @property
    def is_empty(self) -> bool:
        """True when there is nothing on the card to surface.

        Considers both contributed and "needs attention" rows so the card
        still appears when the user linked ingredients but none of them
        can be measured (e.g. count units or missing macro data) — that
        way the UI can tell the user *why* their link attempts didn't
        surface as totals. Pure unlinked rows alone are quiet.
        """
        return self.linked_count == 0 and self.needs_attention_count == 0


def summarize_linked_nutrition(ingredient_links) -> LinkedNutritionSummary:
    """Aggregate kcal/protein/carbs/fat for one recipe's IngredientLinks.

    ``ingredient_links`` is an iterable of ``IngredientLink`` whose
    ``ingredient`` carries the per-100g snapshot imported from USDA
    FoodData Central (see ``IngredientNutritionForm``).

    The ingredient row is included only when ``usda_food_id`` is set AND
    any of the four nutrient fields are populated AND the unit is
    convertible to mass (weight or volume-as-water). Count-based units
    (``piece``, ``clove``, ``slice``, etc.) are listed under
    :pyattr:`LinkedNutritionSummary.skipped` so the UI can surface
    them as out-of-scope instead of silently dropping them.
    """
    summary = LinkedNutritionSummary()
    for link in ingredient_links:
        summary.total_count += 1
        ingredient = getattr(link, "ingredient", None)
        if ingredient is None or not getattr(ingredient, "usda_food_id", ""):
            continue
        unit = (link.unit or "").strip().lower()
        if unit in UNCONVERTIBLE_UNITS:
            summary.skipped.append(
                {
                    "name": ingredient.name,
                    "quantity": link.quantity,
                    "unit": unit,
                    "reason": "count unit",
                }
            )
            summary.needs_attention_count += 1
            continue
        # Weight + volume arrive as grams via convert_to_grams; unknown
        # units return value unchanged — treat them as a no-op skip.
        grams = convert_to_grams(link.quantity, unit)
        if grams is None or grams == 0:
            summary.skipped.append(
                {
                    "name": ingredient.name,
                    "quantity": link.quantity,
                    "unit": unit,
                    "reason": "unconvertible unit",
                }
            )
            summary.needs_attention_count += 1
            continue
        # Per-100g scaling: each macro is reported per 100 g of food.
        factor = grams / Decimal("100")
        # Count this row as contributing only when at least one macro is known.
        contributed = False
        for attr, dest in (
            ("calories_kcal", "calories_kcal"),
            ("protein_g", "protein_g"),
            ("carbs_g", "carbs_g"),
            ("fat_g", "fat_g"),
        ):
            value = getattr(ingredient, attr, None)
            if value is None:
                continue
            try:
                contribution = (Decimal(str(value)) * factor).quantize(
                    Decimal("0.01")
                )
            except Exception:
                continue
            setattr(summary, dest, getattr(summary, dest) + contribution)
            contributed = True
        if contributed:
            summary.linked_count += 1
        else:
            summary.skipped.append(
                {
                    "name": ingredient.name,
                    "quantity": link.quantity,
                    "unit": unit,
                    "reason": "no macros on file",
                }
            )
            summary.needs_attention_count += 1
    return summary

