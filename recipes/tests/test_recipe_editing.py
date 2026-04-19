from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from instructions.models import Instruction
from recipes.models import Recipe
from tags.models import RecipeTag, Tag


class RecipeEditingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.household = Household.objects.create(name="Recipe Home")
        self.user = user_model.objects.create_user(
            username="recipe-editor",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Weeknight Pasta",
            description="Simple dinner",
            needs_review=False,
        )

        self.step_one = Instruction.objects.create(
            recipe=self.recipe,
            step_number=1,
            text="Boil water",
        )
        self.step_two = Instruction.objects.create(
            recipe=self.recipe,
            step_number=2,
            text="Cook pasta",
        )
        self.step_three = Instruction.objects.create(
            recipe=self.recipe,
            step_number=3,
            text="Drain and serve",
        )

    def _recipe_update_payload(self):
        return {
            "title": self.recipe.title,
            "description": self.recipe.description,
            "video_url": "",
            "on_hand_idea": "",
            "leftover_worthy": "",
            "needs_review": "",
        }

    def test_recipe_edit_persists_posted_instruction_order_contiguously(self):
        payload = self._recipe_update_payload()
        payload.update(
            {
                f"instruction_{self.step_one.id}_order": "30",
                f"instruction_{self.step_two.id}_order": "10",
                f"instruction_{self.step_three.id}_order": "20",
            }
        )

        response = self.client.post(
            reverse("recipes:recipe_update", args=[self.recipe.id]),
            data=payload,
        )

        self.assertEqual(response.status_code, 302)
        ordered_steps = list(
            Instruction.objects.filter(recipe=self.recipe).order_by("step_number")
        )
        self.assertEqual([step.step_number for step in ordered_steps], [1, 2, 3])
        self.assertEqual(
            [step.id for step in ordered_steps],
            [self.step_two.id, self.step_three.id, self.step_one.id],
        )

    def test_recipe_edit_can_create_and_attach_new_tag_inline(self):
        payload = self._recipe_update_payload()
        payload.update(
            {
                "new_tag_name": "  Weeknight  ",
                "new_tag_color": "#112233",
            }
        )

        response = self.client.post(
            reverse("recipes:recipe_update", args=[self.recipe.id]),
            data=payload,
        )

        self.assertEqual(response.status_code, 302)
        created_tag = Tag.objects.get(household=self.household, name="Weeknight")
        self.assertEqual(created_tag.color, "#112233")
        self.assertTrue(
            RecipeTag.objects.filter(recipe=self.recipe, tag=created_tag).exists()
        )

    def test_recipe_edit_rejects_duplicate_new_tag_name_within_household(self):
        Tag.objects.create(
            household=self.household,
            name="Quick",
            color="#abcdef",
        )
        payload = self._recipe_update_payload()
        payload.update(
            {
                "new_tag_name": "  quick  ",
                "new_tag_color": "#111111",
            }
        )

        response = self.client.post(
            reverse("recipes:recipe_update", args=[self.recipe.id]),
            data=payload,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Tag.objects.filter(household=self.household, name="Quick").count(), 1
        )
        self.assertIn("new_tag_name", response.context["form"].errors)
