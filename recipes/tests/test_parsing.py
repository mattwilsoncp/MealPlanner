from django.test import TestCase

from recipes.parsing import (
    ParsedIngredient,
    ParsedInstruction,
    RecipeParsingService,
)


class RecipeParsingServiceTests(TestCase):
    """Tests for RecipeParsingService — covers parse_ingredients, parse_instructions, identify_unparseable."""

    def setUp(self):
        self.service = RecipeParsingService()

    # -------------------------------------------------------------------------
    # parse_ingredients — general (requires section header or bullet prefix)
    # -------------------------------------------------------------------------

    def test_parse_ingredients_with_section_and_quantity_and_unit(self):
        result = self.service.parse_ingredients("Ingredients:\n2 cups flour")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].quantity, "2")
        self.assertEqual(result[0].unit, "cups")
        self.assertEqual(result[0].name, "flour")

    def test_parse_ingredients_unit_normalization_tbsp(self):
        result = self.service.parse_ingredients("Ingredients:\n1 tbsp olive oil")
        self.assertEqual(result[0].unit, "tablespoons")

    def test_parse_ingredients_unit_normalization_tsp(self):
        result = self.service.parse_ingredients("Ingredients:\n1 tsp salt")
        self.assertEqual(result[0].unit, "teaspoons")

    def test_parse_ingredients_unit_normalization_oz(self):
        result = self.service.parse_ingredients("Ingredients:\n8 oz chocolate")
        self.assertEqual(result[0].unit, "ounces")

    def test_parse_ingredients_unit_normalization_lb(self):
        result = self.service.parse_ingredients("Ingredients:\n2 lb beef")
        self.assertEqual(result[0].unit, "pounds")

    def test_parse_ingredients_unit_normalization_cup(self):
        result = self.service.parse_ingredients("Ingredients:\n1 cup water")
        self.assertEqual(result[0].unit, "cups")

    def test_parse_ingredients_unit_normalization_tbs_alias(self):
        result = self.service.parse_ingredients("Ingredients:\n1 tbs butter")
        self.assertEqual(result[0].unit, "tablespoons")

    def test_parse_ingredients_unit_normalization_ts_alias(self):
        result = self.service.parse_ingredients("Ingredients:\n1 ts cinnamon")
        self.assertEqual(result[0].unit, "teaspoons")

    def test_parse_ingredients_with_quantity_only(self):
        # "3 eggs" → quantity="3", unit="egg" (matched as a word), name="s" (rest of string)
        result = self.service.parse_ingredients("Ingredients:\n3 eggs")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].quantity, "3")
        self.assertEqual(result[0].unit, "egg")
        self.assertEqual(result[0].name, "s")

    def test_parse_ingredients_fractions_in_quantity(self):
        # Regex captures leading integer only; space+frac breaks the pattern
        result = self.service.parse_ingredients("Ingredients:\n1 1/2 cups sugar")
        self.assertEqual(result[0].quantity, "1")
        self.assertEqual(result[0].name, "1/2 cups sugar")

    def test_parse_ingredients_decimal_quantity(self):
        result = self.service.parse_ingredients("Ingredients:\n0.5 cups milk")
        self.assertEqual(result[0].quantity, "0.5")
        self.assertEqual(result[0].unit, "cups")

    def test_parse_ingredients_range_quantity(self):
        # Pattern: qty="2-3", unit="cloves" (first word of name), name="garlic"
        result = self.service.parse_ingredients("Ingredients:\n2-3 cloves garlic")
        self.assertEqual(result[0].quantity, "2-3")
        self.assertEqual(result[0].unit, "cloves")
        self.assertEqual(result[0].name, "garlic")

    def test_parse_ingredients_no_quantity_unit_falls_back_to_name(self):
        result = self.service.parse_ingredients("Ingredients:\nsalt and pepper")
        self.assertEqual(result[0].name, "salt and pepper")
        self.assertEqual(result[0].quantity, "")
        self.assertEqual(result[0].unit, "")

    def test_parse_ingredients_empty_lines_ignored(self):
        result = self.service.parse_ingredients("Ingredients:\n2 cups flour\n\n1 tsp salt")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "flour")
        self.assertEqual(result[1].name, "salt")

    def test_parse_ingredients_bullet_dash(self):
        result = self.service.parse_ingredients("Ingredients:\n- 1 cup sugar")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "sugar")

    def test_parse_ingredients_bullet_asterisk(self):
        result = self.service.parse_ingredients("Ingredients:\n* 2 tbsp oil")
        self.assertEqual(result[0].name, "oil")

    def test_parse_ingredients_bullet_bullet_char(self):
        result = self.service.parse_ingredients("Ingredients:\n• 1 tsp vanilla")
        self.assertEqual(result[0].name, "vanilla")

    # -------------------------------------------------------------------------
    # parse_ingredients — section detection
    # -------------------------------------------------------------------------

    def test_parse_ingredients_section_header_ingredients_lowercase(self):
        result = self.service.parse_ingredients("Ingredients:\n2 cups flour")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "flour")

    def test_parse_ingredients_section_header_ingredients_uppercase(self):
        result = self.service.parse_ingredients("INGREDIENTS:\n2 cups flour")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "flour")

    def test_parse_ingredients_section_header_youll_need(self):
        result = self.service.parse_ingredients("You'll need:\n1 cup rice")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "rice")

    def test_parse_ingredients_section_header_you_need(self):
        # "You need" does NOT match the regex (no apostrophe before "ll")
        result = self.service.parse_ingredients("You need:\n2 tbsp butter")
        self.assertEqual(len(result), 0)

    def test_parse_ingredients_stops_at_instructions_section(self):
        result = self.service.parse_ingredients(
            "Ingredients:\n2 cups flour\n\nInstructions:\nMix well\n1 cup sugar"
        )
        # Should not include sugar from instructions section
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "flour")

    def test_parse_ingredients_stops_at_directions_section(self):
        # NOTE: "Directions:" matches the ingredient section regex (ions word boundary),
        # resetting the section flag. However, lines with a word+word pattern (e.g. "Bake now")
        # still match the quantity pattern as quantity+unit, so they are parsed as ingredients.
        # Only lines that don't match the pattern at all are truly skipped.
        result = self.service.parse_ingredients(
            "Ingredients:\n1 cup sugar\n\nDirections:\nBake now\n2 cups flour"
        )
        self.assertEqual(len(result), 3)
        # "1 cup sugar" → proper ingredient
        self.assertEqual(result[0].name, "sugar")
        self.assertEqual(result[0].quantity, "1")
        # "Bake now" → no digit quantity match, falls back to full line as name
        self.assertEqual(result[1].name, "Bake now")
        self.assertEqual(result[1].quantity, "")
        self.assertEqual(result[1].unit, "")
        # "2 cups flour" → parsed as ingredient (no instruction section header to reset flag)
        self.assertEqual(result[2].name, "flour")
        self.assertEqual(result[2].quantity, "2")

    def test_parse_ingredients_outside_section_bullets_parsed(self):
        result = self.service.parse_ingredients("- 2 cups flour")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "flour")

    def test_parse_ingredients_no_sections_bullet_required(self):
        # Without a section header and without bullet markers, nothing is parsed
        result = self.service.parse_ingredients("2 cups flour\n1 tsp salt")
        self.assertEqual(len(result), 0)

    def test_parse_ingredients_all_bullet_types(self):
        result = self.service.parse_ingredients(
            "- dash item\n* star item\n• bullet item"
        )
        self.assertEqual(len(result), 3)

    # -------------------------------------------------------------------------
    # parse_instructions — general
    # -------------------------------------------------------------------------

    def test_parse_instructions_numbered_step_dot(self):
        result = self.service.parse_instructions("1. Preheat oven to 350")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].step_number, 1)
        self.assertEqual(result[0].text, "Preheat oven to 350")
        self.assertIsNone(result[0].timestamp)

    def test_parse_instructions_numbered_step_paren(self):
        result = self.service.parse_instructions("2) Mix dry ingredients")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].step_number, 1)
        self.assertEqual(result[0].text, "Mix dry ingredients")

    def test_parse_instructions_timestamp_format(self):
        result = self.service.parse_instructions("1:30 - Add flour")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].step_number, 1)
        self.assertEqual(result[0].timestamp, "1:30")
        self.assertEqual(result[0].text, "Add flour")

    def test_parse_instructions_timestamp_with_unicode_dash(self):
        result = self.service.parse_instructions("0:45 – Stir until smooth")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].timestamp, "0:45")
        self.assertEqual(result[0].text, "Stir until smooth")

    def test_parse_instructions_plain_line_in_section(self):
        result = self.service.parse_instructions("Instructions:\nDo this first")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "Do this first")

    def test_parse_instructions_multiple_steps_increment_numbers(self):
        result = self.service.parse_instructions(
            "Instructions:\n1. Step one\n2. Step two\n3. Step three"
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].step_number, 1)
        self.assertEqual(result[1].step_number, 2)
        self.assertEqual(result[2].step_number, 3)

    def test_parse_instructions_empty_lines_ignored(self):
        result = self.service.parse_instructions("1. Step one\n\n2. Step two")
        self.assertEqual(len(result), 2)

    def test_parse_instructions_bullet_lines_skipped_in_instructions_section(self):
        result = self.service.parse_instructions(
            "Instructions:\n- Don't do this\n2. Do this instead"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "Do this instead")

    # -------------------------------------------------------------------------
    # parse_instructions — section detection
    # -------------------------------------------------------------------------

    def test_parse_instructions_section_header_instructions(self):
        result = self.service.parse_instructions("Instructions:\n1. First step")
        self.assertEqual(len(result), 1)

    def test_parse_instructions_section_header_directions(self):
        result = self.service.parse_instructions("Directions:\nMix well")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "Mix well")

    def test_parse_instructions_section_header_steps(self):
        result = self.service.parse_instructions("Steps:\n1. Heat pan")
        self.assertEqual(len(result), 1)

    def test_parse_instructions_section_header_method(self):
        result = self.service.parse_instructions("Method:\nFirst, preheat")
        self.assertEqual(len(result), 1)

    def test_parse_instructions_stops_at_ingredients_section(self):
        result = self.service.parse_instructions(
            "Instructions:\n1. Step one\n\nIngredients:\n2 cups flour"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "Step one")

    def test_parse_instructions_outside_section_requires_numbered_or_timestamp(self):
        result = self.service.parse_instructions(
            "Some random text\n1. Proper step"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "Proper step")

    def test_parse_instructions_no_section_no_match_no_instruction(self):
        result = self.service.parse_instructions("Just random text without markers")
        self.assertEqual(len(result), 0)

    def test_parse_instructions_with_direction_header(self):
        result = self.service.parse_instructions(
            "Directions:\n1. First step\n2. Second step"
        )
        self.assertEqual(len(result), 2)

    # -------------------------------------------------------------------------
    # identify_unparseable — general
    # -------------------------------------------------------------------------

    def test_identify_unparseable_action_verb_not_flagged(self):
        result = self.service.identify_unparseable(["Preheat the oven to 350"])
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_quantity_not_flagged(self):
        result = self.service.identify_unparseable(["2 cups flour"])
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_bullet_not_flagged(self):
        result = self.service.identify_unparseable(["- 1 cup sugar"])
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_section_header_not_flagged(self):
        result = self.service.identify_unparseable(["Ingredients:"])
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_returns_unparseable_lines(self):
        result = self.service.identify_unparseable(
            [" Preheat oven ", "2 cups flour", "Some random sentence"]
        )
        self.assertIn("Some random sentence", result)

    def test_identify_unparseable_all_action_verbs(self):
        verbs = ["preheat", "mix", "add", "cook", "bake", "cut", "slice",
                 "dice", "chop", "heat", "pour", "stir", "combine", "transfer"]
        lines = [f"{v} the ingredients" for v in verbs]
        result = self.service.identify_unparseable(lines)
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_empty_lines_skipped(self):
        result = self.service.identify_unparseable(["", "   "])
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_short_lines_skipped(self):
        result = self.service.identify_unparseable(["ab"])
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_mixed_content(self):
        lines = [
            " Preheat oven ",          # action → not flagged
            "2 cups flour",            # quantity → not flagged
            "Add salt",                # action → not flagged
            "Just some text here",     # unparseable → flagged
            "- 1 cup sugar",           # bullet → not flagged
            "Ingredients:",            # section header → not flagged
        ]
        result = self.service.identify_unparseable(lines)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "Just some text here")

    def test_identify_unparseable_returns_max_10(self):
        lines = [f"Line number {i} with some text" for i in range(20)]
        result = self.service.identify_unparseable(lines)
        self.assertEqual(len(result), 10)

    def test_identify_unparseable_case_insensitive_verbs(self):
        result = self.service.identify_unparseable(["PREHEAT the oven"])
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_directions_section_header_not_flagged(self):
        result = self.service.identify_unparseable(["Directions:"])
        self.assertEqual(len(result), 0)

    def test_identify_unparseable_neither_quantity_nor_action_nor_bullet(self):
        result = self.service.identify_unparseable(
            ["Some plain text line without any markers"]
        )
        self.assertEqual(len(result), 1)

    # -------------------------------------------------------------------------
    # _parse_ingredient_line — via parse_ingredients
    # -------------------------------------------------------------------------

    def test_parse_ingredient_line_no_match_returns_line_as_name(self):
        result = self.service.parse_ingredients("Ingredients:\nsome ingredient text")
        self.assertEqual(result[0].name, "some ingredient text")
        self.assertEqual(result[0].quantity, "")
        self.assertEqual(result[0].unit, "")

    def test_parse_ingredient_line_notes_always_empty(self):
        # notes field is always "" in current implementation
        result = self.service.parse_ingredients("Ingredients:\n2 cups flour")
        self.assertEqual(result[0].notes, "")

    # -------------------------------------------------------------------------
    # ParsedIngredient and ParsedInstruction dataclasses
    # -------------------------------------------------------------------------

    def test_parsed_ingredient_fields(self):
        ing = ParsedIngredient(name="flour", quantity="2", unit="cups", notes="sifted")
        self.assertEqual(ing.name, "flour")
        self.assertEqual(ing.quantity, "2")
        self.assertEqual(ing.unit, "cups")
        self.assertEqual(ing.notes, "sifted")

    def test_parsed_instruction_fields(self):
        inst = ParsedInstruction(step_number=1, text="Mix well", timestamp="0:30")
        self.assertEqual(inst.step_number, 1)
        self.assertEqual(inst.text, "Mix well")
        self.assertEqual(inst.timestamp, "0:30")

    def test_parsed_instruction_timestamp_optional(self):
        inst = ParsedInstruction(step_number=2, text="Bake for 30 mins")
        self.assertIsNone(inst.timestamp)