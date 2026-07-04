"""Tests for ``summarize_linked_nutrition`` + the recipe-detail summary card."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from ingredients.utils import (
    COUNT_UNITS,
    UNCONVERTIBLE_UNITS,
    summarize_linked_nutrition,
)
from ingredients.models import Ingredient, IngredientLink
from recipes.models import Recipe
from instructions.models import Instruction


class SummarizeLinkedNutritionUnitTests(TestCase):
    """Pure math: does scaling + per-100g semantics hold across units?"""

    def test_weight_oz_factor_matches_grams(self):
        # Per-100g: 100 kcal, 10g protein, 0 carb, 0 fat.
        # 8 oz ≈ 226.8 g → factor ≈ 2.268 → kcal ≈ 226.8.
        class _Ing:
            name = "Test Ing"
            usda_food_id = "X"
            calories_kcal = Decimal("100")
            protein_g = Decimal("10")
            carbs_g = Decimal("0")
            fat_g = Decimal("0")

        class _Link:
            quantity = Decimal("8")
            unit = "oz"
            ingredient = _Ing()

        summary = summarize_linked_nutrition([_Link()])
        self.assertEqual(summary.linked_count, 1)
        self.assertEqual(summary.total_count, 1)
        # 8 × 28.3495 = 226.796, factor = 2.26796, kcal = 226.80 (rounded .01).
        self.assertAlmostEqual(summary.calories_kcal, Decimal("226.80"), places=2)
        self.assertAlmostEqual(summary.protein_g, Decimal("22.68"), places=2)

    def test_volume_cup_treated_as_water_density(self):
        # Per-100g: 50 kcal, 0 protein, 10g carbs, 0 fat.
        # 1 cup ≈ 236.588 ml → 236.588 g → factor ≈ 2.366 → kcal ≈ 118.30.
        class _Ing:
            name = "Test Ing"
            usda_food_id = "X"
            calories_kcal = Decimal("50")
            protein_g = Decimal("0")
            carbs_g = Decimal("10")
            fat_g = Decimal("0")

        class _Link:
            quantity = Decimal("1")
            unit = "cup"
            ingredient = _Ing()

        summary = summarize_linked_nutrition([_Link()])
        self.assertEqual(summary.linked_count, 1)
        self.assertAlmostEqual(summary.calories_kcal, Decimal("118.30"), places=2)

    def test_count_unit_is_skipped_not_silently_dropped(self):
        class _Ing:
            name = "Garlic"
            usda_food_id = "X"
            calories_kcal = Decimal("100")
            protein_g = Decimal("10")
            carbs_g = Decimal("0")
            fat_g = Decimal("0")

        class _Link:
            quantity = Decimal("3")
            unit = "clove"
            ingredient = _Ing()

        summary = summarize_linked_nutrition([_Link()])
        self.assertEqual(summary.linked_count, 0)
        self.assertEqual(summary.needs_attention_count, 1)
        self.assertEqual(summary.calories_kcal, Decimal("0"))
        self.assertEqual(len(summary.skipped), 1)
        self.assertEqual(summary.skipped[0]["reason"], "count unit")
        self.assertEqual(summary.skipped[0]["name"], "Garlic")
        self.assertIn("clove", COUNT_UNITS)
        self.assertIn("clove", UNCONVERTIBLE_UNITS)
        # Empty printable card means "nothing to say"; count-unit skip
        # is something the UI must surface, so the card should render.
        self.assertFalse(summary.is_empty)

    def test_unlinked_ingredient_is_skipped(self):
        class _Ing:
            name = "Flour"
            usda_food_id = ""
            calories_kcal = Decimal("100")
            protein_g = Decimal("10")
            carbs_g = Decimal("0")
            fat_g = Decimal("0")

        class _Link:
            quantity = Decimal("1")
            unit = "g"
            ingredient = _Ing()

        summary = summarize_linked_nutrition([_Link()])
        self.assertEqual(summary.linked_count, 0)
        self.assertEqual(summary.needs_attention_count, 0)
        self.assertEqual(summary.total_count, 1)
        # No attempt to link at all → nothing to say.
        self.assertTrue(summary.is_empty)

    def test_partial_macro_data_still_counts_row(self):
        # Macro field missing → just skip that field, still mark row as contributed if any field rolled up.
        class _Ing:
            name = "Partial Ing"
            usda_food_id = "X"
            calories_kcal = Decimal("50")
            protein_g = None
            carbs_g = Decimal("0")
            fat_g = None

        class _Link:
            quantity = Decimal("100")
            unit = "g"
            ingredient = _Ing()

        summary = summarize_linked_nutrition([_Link()])
        self.assertEqual(summary.linked_count, 1)
        self.assertEqual(summary.needs_attention_count, 0)
        self.assertEqual(summary.calories_kcal, Decimal("50.00"))
        self.assertFalse(summary.is_empty)

    def test_no_macros_anywhere_is_skipped(self):
        class _Ing:
            name = "Empty Ing"
            usda_food_id = "X"
            calories_kcal = None
            protein_g = None
            carbs_g = None
            fat_g = None

        class _Link:
            quantity = Decimal("100")
            unit = "g"
            ingredient = _Ing()

        summary = summarize_linked_nutrition([_Link()])
        self.assertEqual(summary.linked_count, 0)
        self.assertEqual(summary.needs_attention_count, 1)
        # Still surfaced so UI can explain why it isn't in the totals.
        self.assertEqual(summary.skipped[-1]["reason"], "no macros on file")
        # Card should render with the skip entry.
        self.assertFalse(summary.is_empty)

    def test_multi_row_sum(self):
        # oats: 50 g → factor 0.5 → 50 kcal + 2.5 P + 10 C + 1 F
        # butter: 1 tbsp ≈ 14.7868 g. ``convert_to_grams`` quantizes
        # to 2 dp so we feed 14.79 into the per-100g scaling.
        #   → 700 × (14.79/100) = 700 × 0.1479 = 103.53 kcal
        #   → 80  × 0.1479 = 11.83 fat
        # total kcal = 50 + 103.53 = 153.53
        # total fat = 1.00 + 11.83 = 12.83
        # total protein = 2.50
        class _Oats:
            name = "Oats"
            usda_food_id = "X1"
            calories_kcal = Decimal("100")
            protein_g = Decimal("5")
            carbs_g = Decimal("20")
            fat_g = Decimal("2")

        class _Butter:
            name = "Butter"
            usda_food_id = "X2"
            calories_kcal = Decimal("700")
            protein_g = Decimal("0")
            carbs_g = Decimal("0")
            fat_g = Decimal("80")

        oats_link = type("L", (), {"quantity": Decimal("50"), "unit": "g", "ingredient": _Oats()})()
        butter_link = type("L", (), {"quantity": Decimal("1"), "unit": "tbsp", "ingredient": _Butter()})()

        summary = summarize_linked_nutrition([oats_link, butter_link])
        self.assertEqual(summary.linked_count, 2)
        self.assertEqual(summary.total_count, 2)
        self.assertEqual(summary.calories_kcal, Decimal("153.53"))
        self.assertEqual(summary.fat_g, Decimal("12.83"))
        self.assertEqual(summary.protein_g, Decimal("2.50"))

    def test_rows_include_every_ingredient_with_status_flag(self):
        # 50 g oats (linked, contributing), 1 tbsp butter (linked, contributing),
        # 2 cloves garlic (linked, NOT contributing because of count unit),
        # 100 g flour (no usda_food_id, never linked).
        class _Flour:
            name = "Flour"
            usda_food_id = ""
            calories_kcal = Decimal("0")
            protein_g = Decimal("0")
            carbs_g = Decimal("0")
            fat_g = Decimal("0")

        # Re-author each link so this test is self-contained.
        class _Oats:
            name = "Rolled Oats"
            usda_food_id = "X"
            calories_kcal = Decimal("100")
            protein_g = Decimal("5")
            carbs_g = Decimal("20")
            fat_g = Decimal("2")

        class _Butter:
            name = "Butter"
            usda_food_id = "X2"
            calories_kcal = Decimal("700")
            protein_g = Decimal("0")
            carbs_g = Decimal("0")
            fat_g = Decimal("80")

        class _Garlic:
            name = "Garlic"
            usda_food_id = "X3"
            calories_kcal = Decimal("100")
            protein_g = Decimal("5")
            carbs_g = Decimal("20")
            fat_g = Decimal("0")

        oats_link = type("L", (), {"quantity": Decimal("50"), "unit": "g", "ingredient": _Oats()})()
        butter_link = type("L", (), {"quantity": Decimal("1"), "unit": "tbsp", "ingredient": _Butter()})()
        garlic_link = type("L", (), {"quantity": Decimal("2"), "unit": "clove", "ingredient": _Garlic()})()
        flour_link = type("L", (), {"quantity": Decimal("100"), "unit": "g", "ingredient": _Flour()})()

        summary = summarize_linked_nutrition([oats_link, butter_link, garlic_link, flour_link])

        self.assertEqual(len(summary.rows), 4)
        # Each row carries a status flag + scalar numerator marks whether
        # the row contributed to the totals.
        oats_row = summary.rows[0]
        self.assertEqual(oats_row["name"], "Rolled Oats")
        self.assertTrue(oats_row["linked"])
        self.assertTrue(oats_row["included"])
        self.assertIsNone(oats_row["reason"])
        self.assertEqual(oats_row["calories_kcal"], Decimal("50.00"))
        self.assertEqual(oats_row["protein_g"], Decimal("2.50"))

        butter_row = summary.rows[1]
        self.assertEqual(butter_row["name"], "Butter")
        self.assertTrue(butter_row["included"])
        # butter 1 tbsp rounds to 14.79 g → factor 0.1479 → 700 × 0.1479 = 103.53
        self.assertEqual(butter_row["calories_kcal"], Decimal("103.53"))

        garlic_row = summary.rows[2]
        self.assertEqual(garlic_row["name"], "Garlic")
        self.assertTrue(garlic_row["linked"])         # link exists
        self.assertFalse(garlic_row["included"])       # but clove is a count unit
        self.assertEqual(garlic_row["reason"], "count unit")
        self.assertIsNone(garlic_row["calories_kcal"])

        flour_row = summary.rows[3]
        self.assertEqual(flour_row["name"], "Flour")
        self.assertFalse(flour_row["linked"])
        self.assertEqual(flour_row["reason"], "not linked")
        self.assertIsNone(flour_row["calories_kcal"])

    def test_rows_preserve_input_order(self):
        # Order matters — the recipe page lists rows in the order they
        # appear in <ul>ingredients</ul>; the helper must not re-sort.
        class _Ing:
            def __init__(self, name):
                self.name = name
                self.usda_food_id = ""
                self.calories_kcal = None
                self.protein_g = None
                self.carbs_g = None
                self.fat_g = None

        names = ["A", "B", "C", "D"]
        links = [
            type("L", (), {"quantity": Decimal("1"), "unit": "g", "ingredient": _Ing(n)})()
            for n in names
        ]
        summary = summarize_linked_nutrition(links)
        self.assertEqual([r["name"] for r in summary.rows], names)


class RecipeDetailNutritionSummaryViewTests(TestCase):
    """Integration: the summary card is wired into the recipe detail page."""

    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Nut Sum HH")
        self.user = user_model.objects.create_user(
            username="nut-sum-user",
            email="nut@example.com",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Oats & Butter",
            description="Quick.",
            needs_review=False,
        )
        # Add an instruction so the recipe isn't flagged pending.
        Instruction.objects.create(
            recipe=self.recipe, step_number=1, text="Mix ingredients."
        )
        self.oats = Ingredient.objects.create(
            household=self.household,
            name="Rolled Oats",
            usda_food_id="USDA-1001",
            calories_kcal=Decimal("100"),
            protein_g=Decimal("5"),
            carbs_g=Decimal("20"),
            fat_g=Decimal("2"),
        )
        self.butter = Ingredient.objects.create(
            household=self.household,
            name="Butter",
            usda_food_id="USDA-2202",
            calories_kcal=Decimal("700"),
            protein_g=Decimal("0"),
            carbs_g=Decimal("0"),
            fat_g=Decimal("80"),
        )
        # 50g oats + 1 tbsp butter + 2 cloves garlic (count unit).
        # Garlic is linked but has no macros so its ingredient row hits
        # the "Nutrition unavailable for this ingredient." empty state.
        self.garlic = Ingredient.objects.create(
            household=self.household,
            name="Garlic",
            usda_food_id="USDA-3333",
            calories_kcal=None,
            protein_g=None,
            carbs_g=None,
            fat_g=None,
        )
        IngredientLink.objects.create(
            recipe=self.recipe, ingredient=self.oats,
            quantity=Decimal("50"), unit="g", order=0,
        )
        IngredientLink.objects.create(
            recipe=self.recipe, ingredient=self.butter,
            quantity=Decimal("1"), unit="tbsp", order=1,
        )
        IngredientLink.objects.create(
            recipe=self.recipe, ingredient=self.garlic,
            quantity=Decimal("2"), unit="clove", order=2,
        )

    def test_summary_in_context_and_echoed_in_template(self):
        response = self.client.get(reverse("recipes:recipe_detail", args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        summary = response.context["nutrition_summary"]
        self.assertEqual(summary.linked_count, 2)
        self.assertEqual(summary.needs_attention_count, 1)
        self.assertEqual(summary.total_count, 3)
        # oats 50g × 100 kcal/100g = 50.00; butter 1 tbsp (rounds to 14.79g) × 700 = 103.53; total 153.53
        self.assertEqual(summary.calories_kcal, Decimal("153.53"))
        self.assertEqual(summary.fat_g, Decimal("12.83"))
        # Rendered eyebrows + counts visible.
        self.assertContains(response, "Nutrition totals")
        # oats + butter contributed; garlic skipped. The subtitle surfaces
        # both halves so the user knows what is and isn't included.
        self.assertContains(response, "2 of 3 ingredients in totals")
        self.assertContains(response, "1 linked but not measurable below")
        # Garlic skipped card visible — quantity renders with .00 because
        # Django formats ``DecimalField`` to 2 decimal places by default.
        self.assertContains(response, "Not in totals")
        self.assertContains(response, "2.00 clove Garlic")

    def test_summary_card_present_when_only_skipped_items_linked(self):
        """User did link a row, but it was unmeasurable → card explains why."""
        # Untie the actually-contributing rows (oats + butter) so the only
        # linked row left is the count-unit garlic. Mirrors the live
        # recipe 46 scenario as reported by the user.
        Ingredient.objects.filter(household=self.household).exclude(
            name="Garlic"
        ).update(
            usda_food_id="",
            calories_kcal=None,
            protein_g=None,
            carbs_g=None,
            fat_g=None,
        )
        response = self.client.get(reverse("recipes:recipe_detail", args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        summary = response.context["nutrition_summary"]
        self.assertEqual(summary.linked_count, 0)
        self.assertEqual(summary.needs_attention_count, 1)
        self.assertEqual(summary.total_count, 3)
        # Card must render even though there's nothing to roll up.
        self.assertFalse(summary.is_empty)
        self.assertContains(response, "Nutrition totals")
        self.assertContains(response, "1 of 3 ingredients linked but not measurable")
        self.assertContains(response, "Why nothing rolled up")
        # Macro cells (Protein/Carbs/Fat) should NOT render — there's no data.
        self.assertNotContains(response, ">Protein<")
        self.assertNotContains(response, ">Carbs<")
        self.assertNotContains(response, ">Fat<")

    def test_summary_card_absent_when_zero_linked(self):
        Ingredient.objects.filter(household=self.household).update(
            usda_food_id="",
            calories_kcal=None,
            protein_g=None,
            carbs_g=None,
            fat_g=None,
        )
        response = self.client.get(reverse("recipes:recipe_detail", args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Nutrition totals")
        self.assertNotContains(response, "kcal</span>")

    def test_existing_literals_preserved_with_summary(self):
        # The summary card must coexist with the existing per-row line
        # containing Protein …· Carbs …· Fat and kcal.
        # Garlic has no macros, so it should still trigger the
        # "Nutrition unavailable for this ingredient." empty-state literal.
        response = self.client.get(reverse("recipes:recipe_detail", args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "USDA Ref:")
        # Oats line still contains full "Protein 5.00g · Carbs 20.00g · Fat 2.00g" string.
        self.assertContains(response, "Protein 5.00g")
        self.assertContains(response, "Carbs 20.00g")
        self.assertContains(response, "Fat 2.00g")
        # Garlic row's macro section still uses the empty-state literal.
        self.assertContains(response, "Nutrition unavailable for this ingredient.")

    def test_per_ingredient_breakdown_table_renders(self):
        response = self.client.get(reverse("recipes:recipe_detail", args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)
        # Section header for the breakdown.
        self.assertContains(response, "Per-ingredient breakdown")
        # Every ingredient in the recipe must appear as a row.
        for name in ("Rolled Oats", "Butter", "Garlic"):
            self.assertContains(response, name)
        # Status-cell variants:
        # - oats + butter: "in totals"
        # - garlic: "count unit"
        self.assertContains(response, "in totals")
        self.assertContains(response, "count unit")
        # Oats 50 g × 100 kcal/100g = 50.00, formatted: contributed value visible.
        # The '50.00' substring only matches in the per-ingredient row, not
        # elsewhere on the page.
        self.assertContains(response, "50.00")
        # 50 g × 5 protein/100g = 2.5 → formatted 2.50
        self.assertContains(response, "2.50")
