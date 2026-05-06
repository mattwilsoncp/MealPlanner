from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from household.models import Household
from instructions.models import Instruction
from recipes.models import Recipe


class InstructionModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Instruction Test Home")
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Test Recipe",
            needs_review=False,
        )

    def test_create_instruction(self):
        step = Instruction.objects.create(
            recipe=self.recipe,
            step_number=1,
            text="Preheat oven to 350F",
        )
        self.assertEqual(step.recipe, self.recipe)
        self.assertEqual(step.step_number, 1)
        self.assertEqual(step.text, "Preheat oven to 350F")

    def test_str_returns_step_number(self):
        step = Instruction.objects.create(
            recipe=self.recipe,
            step_number=1,
            text="Boil water",
        )
        self.assertEqual(str(step), "Step 1")

    def test_str_with_high_step_number(self):
        step = Instruction.objects.create(
            recipe=self.recipe,
            step_number=99,
            text="Final plating",
        )
        self.assertEqual(str(step), "Step 99")

    def test_ordering_by_step_number(self):
        step3 = Instruction.objects.create(
            recipe=self.recipe, step_number=3, text="Step 3"
        )
        step1 = Instruction.objects.create(
            recipe=self.recipe, step_number=1, text="Step 1"
        )
        step2 = Instruction.objects.create(
            recipe=self.recipe, step_number=2, text="Step 2"
        )
        # Default ordering should be by step_number
        steps = list(Instruction.objects.filter(recipe=self.recipe))
        self.assertEqual([s.step_number for s in steps], [1, 2, 3])

    def test_recipe_cascade_deletes_instructions(self):
        Instruction.objects.create(
            recipe=self.recipe, step_number=1, text="Step 1"
        )
        Instruction.objects.create(
            recipe=self.recipe, step_number=2, text="Step 2"
        )
        self.assertEqual(Instruction.objects.filter(recipe=self.recipe).count(), 2)
        self.recipe.delete()
        self.assertEqual(Instruction.objects.count(), 0)

    def test_same_recipe_can_have_many_steps(self):
        for i in range(1, 6):
            Instruction.objects.create(
                recipe=self.recipe, step_number=i, text=f"Step {i}"
            )
        self.assertEqual(Instruction.objects.filter(recipe=self.recipe).count(), 5)

    def test_different_recipes_have_independent_instructions(self):
        other_recipe = Recipe.objects.create(
            household=self.household,
            title="Other Recipe",
            needs_review=False,
        )
        Instruction.objects.create(
            recipe=self.recipe, step_number=1, text="Recipe 1 Step"
        )
        Instruction.objects.create(
            recipe=other_recipe, step_number=1, text="Recipe 2 Step"
        )
        self.assertEqual(Instruction.objects.filter(recipe=self.recipe).count(), 1)
        self.assertEqual(
            Instruction.objects.filter(recipe=other_recipe).count(), 1
        )

    def test_step_number_allows_zero(self):
        step = Instruction.objects.create(
            recipe=self.recipe, step_number=0, text="Zero-indexed step"
        )
        self.assertEqual(step.step_number, 0)

    def test_text_field_accepts_long_content(self):
        long_text = "A" * 1000
        step = Instruction.objects.create(
            recipe=self.recipe, step_number=1, text=long_text
        )
        step.refresh_from_db()
        self.assertEqual(step.text, long_text)

    def test_text_cannot_be_blank(self):
        step = Instruction(recipe=self.recipe, step_number=1, text="")
        with self.assertRaises(ValidationError):
            step.full_clean()

    def test_step_number_required(self):
        step = Instruction(recipe=self.recipe, text="Missing step number")
        with self.assertRaises(ValidationError):
            step.full_clean()

    def test_image_field_is_blankable(self):
        step = Instruction.objects.create(
            recipe=self.recipe, step_number=1, text="No image"
        )
        self.assertFalse(step.image)  # Empty ImageFieldFile is falsy
