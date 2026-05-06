from decimal import Decimal

from django.test import TestCase

from ingredients.utils import (
    convert_to_grams,
    convert_from_grams,
    normalize_unit_key,
    WEIGHT_TO_GRAMS,
    VOLUME_TO_ML,
    COUNT_UNITS,
)


class UnitConversionTests(TestCase):
    # --- convert_to_grams ---

    def test_oz_to_grams(self):
        result = convert_to_grams(1, "oz")
        self.assertEqual(result, Decimal("28.35"))

    def test_lb_to_grams(self):
        result = convert_to_grams(1, "lb")
        self.assertEqual(result, Decimal("453.59"))

    def test_kg_to_grams(self):
        result = convert_to_grams(1, "kg")
        self.assertEqual(result, Decimal("1000.00"))

    def test_g_passthrough(self):
        result = convert_to_grams(100, "g")
        self.assertEqual(result, Decimal("100.00"))

    def test_multiple_oz_to_grams(self):
        result = convert_to_grams(3, "oz")
        self.assertEqual(result, Decimal("85.05"))  # 3 * 28.3495

    def test_cup_to_ml_assumes_water_density(self):
        # 1 cup = 236.588ml; with 1ml ≈ 1g, this is also 236.59g
        result = convert_to_grams(1, "cup")
        self.assertEqual(result, Decimal("236.59"))

    def test_tbsp_to_ml(self):
        result = convert_to_grams(1, "tbsp")
        self.assertEqual(result, Decimal("14.79"))

    def test_tsp_to_ml(self):
        result = convert_to_grams(1, "tsp")
        self.assertEqual(result, Decimal("4.93"))

    def test_ml_passthrough(self):
        result = convert_to_grams(500, "ml")
        self.assertEqual(result, Decimal("500.00"))

    def test_l_to_ml(self):
        result = convert_to_grams(1, "l")
        self.assertEqual(result, Decimal("1000.00"))

    def test_piece_count_not_converted(self):
        result = convert_to_grams(3, "piece")
        self.assertEqual(result, Decimal("3"))

    def test_clove_count_not_converted(self):
        result = convert_to_grams(2, "clove")
        self.assertEqual(result, Decimal("2"))

    def test_unknown_unit_returns_value_unchanged(self):
        result = convert_to_grams(5, "unknown")
        self.assertEqual(result, Decimal("5"))

    def test_decimal_input(self):
        result = convert_to_grams(Decimal("2.5"), "oz")
        self.assertEqual(result, Decimal("70.87"))  # 2.5 * 28.3495 ≈ 70.87

    def test_string_input(self):
        result = convert_to_grams("3", "oz")
        self.assertEqual(result, Decimal("85.05"))

    def test_whitespace_normalized(self):
        result = convert_to_grams("  1  ", "  oz  ")
        self.assertEqual(result, Decimal("28.35"))

    def test_case_insensitive(self):
        result = convert_to_grams(1, "OZ")
        self.assertEqual(result, Decimal("28.35"))
        result = convert_to_grams(1, "Cup")
        self.assertEqual(result, Decimal("236.59"))

    # --- convert_from_grams ---

    def test_grams_to_oz(self):
        result = convert_from_grams(Decimal("28.35"), "oz")
        self.assertAlmostEqual(float(result), 1.0, places=2)

    def test_grams_to_lb(self):
        result = convert_from_grams(Decimal("453.59"), "lb")
        self.assertAlmostEqual(float(result), 1.0, places=1)

    def test_grams_to_kg(self):
        result = convert_from_grams(Decimal("1000"), "kg")
        self.assertEqual(result, Decimal("1.00"))

    def test_grams_to_g(self):
        result = convert_from_grams(Decimal("100"), "g")
        self.assertEqual(result, Decimal("100.00"))

    def test_grams_to_ml(self):
        result = convert_from_grams(Decimal("500"), "ml")
        self.assertEqual(result, Decimal("500.00"))

    def test_count_unit_passthrough(self):
        result = convert_from_grams(Decimal("5"), "piece")
        self.assertEqual(result, Decimal("5"))

    # --- normalize_unit_key ---

    def test_oz_normalizes_to_g(self):
        name, unit = normalize_unit_key("Flour", "oz")
        self.assertEqual(name, "flour")
        self.assertEqual(unit, "g")

    def test_lb_normalizes_to_g(self):
        name, unit = normalize_unit_key("Sugar", "lb")
        self.assertEqual(name, "sugar")
        self.assertEqual(unit, "g")

    def test_kg_normalizes_to_g(self):
        name, unit = normalize_unit_key("Rice", "kg")
        self.assertEqual(name, "rice")
        self.assertEqual(unit, "g")

    def test_g_stays_g(self):
        name, unit = normalize_unit_key("Salt", "g")
        self.assertEqual(unit, "g")

    def test_cup_normalizes_to_ml(self):
        name, unit = normalize_unit_key("Water", "cup")
        self.assertEqual(unit, "ml")

    def test_tbsp_normalizes_to_ml(self):
        name, unit = normalize_unit_key("Oil", "tbsp")
        self.assertEqual(unit, "ml")

    def test_ml_stays_ml(self):
        name, unit = normalize_unit_key("Broth", "ml")
        self.assertEqual(unit, "ml")

    def test_piece_unchanged(self):
        name, unit = normalize_unit_key("Egg", "piece")
        self.assertEqual(unit, "piece")

    def test_name_normalized_to_lowercase(self):
        name, unit = normalize_unit_key("  ROLLED OATS  ", "g")
        self.assertEqual(name, "rolled oats")

    def test_empty_name_handled(self):
        name, unit = normalize_unit_key("", "g")
        self.assertEqual(name, "")

    def test_none_name_handled(self):
        name, unit = normalize_unit_key(None, "g")
        self.assertEqual(name, "")

    # --- integration: oz matches g ---

    def test_flour_oz_matches_flour_g(self):
        # 3oz flour → 85.05g; inventory has 100g flour
        name_g, unit_g = normalize_unit_key("Flour", "g")
        name_oz, unit_oz = normalize_unit_key("Flour", "oz")
        self.assertEqual(name_g, name_oz)
        self.assertEqual(unit_g, unit_oz)  # both normalize to 'g'

        needed = convert_to_grams(3, "oz")
        available = convert_to_grams(100, "g")
        self.assertEqual(needed, Decimal("85.05"))
        self.assertLess(needed, available)  # 3oz < 100g → inventory covers it
