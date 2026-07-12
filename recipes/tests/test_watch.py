"""Tests for the recipe watch feature."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from instructions.models import Instruction
from recipes.models import Recipe, RecipeWatchSegment, RecipeWatchSession
from recipes.watch_service import (
    _best_matching_step,
    _fetch_transcript_items,
    _group_items_into_segments,
    _normalize_words,
    process_recipe_watch,
)


User = get_user_model()


class WatchSegmentGroupingTests(TestCase):
    def test_group_items_into_segments_empty(self):
        self.assertEqual(_group_items_into_segments([]), [])

    def test_group_items_into_segments_single_item(self):
        items = [
            {"start": Decimal("0"), "duration": Decimal("2"), "text": "Hello"},
        ]
        segments = _group_items_into_segments(items)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["start"], Decimal("0"))
        self.assertEqual(segments[0]["end"], Decimal("2"))
        self.assertEqual(segments[0]["text"], "Hello")

    def test_group_items_into_segments_by_time(self):
        items = [
            {"start": Decimal("0"), "duration": Decimal("4"), "text": "A"},
            {"start": Decimal("4"), "duration": Decimal("4"), "text": "B"},
            {"start": Decimal("8"), "duration": Decimal("4"), "text": "C"},
            {"start": Decimal("12"), "duration": Decimal("4"), "text": "D"},
        ]
        segments = _group_items_into_segments(
            items,
            target_duration=Decimal("10"),
            target_text_length=1000,
        )
        # Two segments: first covers roughly 0-10s, second covers 12-16s.
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["text"], "A B C")
        self.assertEqual(segments[1]["text"], "D")

    def test_group_items_into_segments_by_target_duration(self):
        items = [
            {"start": Decimal(i), "duration": Decimal("1"), "text": f"word{i}"}
            for i in range(10)
        ]
        segments = _group_items_into_segments(
            items, target_duration=Decimal("5")
        )
        self.assertEqual(len(segments), 2)


class TranscriptItemFetchingTests(TestCase):
    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_fetch_transcript_items_handles_object_style_snippets(self, mock_api_cls):
        class Snippet:
            def __init__(self, start, duration, text):
                self.start = start
                self.duration = duration
                self.text = text

        mock_api_cls.get_transcript.return_value = [
            Snippet(0.0, 2.0, "Hello there"),
            Snippet(2.0, 3.0, "Welcome to the recipe"),
        ]

        items = _fetch_transcript_items("abcdefghijk")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["start"], Decimal("0"))
        self.assertEqual(items[0]["duration"], Decimal("2"))
        self.assertEqual(items[0]["text"], "Hello there")
        self.assertEqual(items[1]["text"], "Welcome to the recipe")

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_fetch_transcript_items_skips_empty_text(self, mock_api_cls):
        mock_api_cls.get_transcript.return_value = [
            {"start": 0.0, "duration": 2.0, "text": "   "},
            {"start": 2.0, "duration": 3.0, "text": "Keep this"},
        ]

        items = _fetch_transcript_items("abcdefghijk")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["text"], "Keep this")


class WatchInstructionMatchingTests(TestCase):
    def test_best_matching_step_no_overlap(self):
        instructions = [
            Instruction(step_number=1, text="Chop onions"),
            Instruction(step_number=2, text="Boil water"),
        ]
        self.assertIsNone(_best_matching_step("Preheat oven", instructions))

    def test_best_matching_step_finds_overlap(self):
        instructions = [
            Instruction(step_number=1, text="Chop the onions finely"),
            Instruction(step_number=2, text="Boil water in a large pot"),
        ]
        step = _best_matching_step(
            "Now finely chop all of the onions",
            instructions,
        )
        self.assertEqual(step, 1)

    def test_normalize_words_filters_stop_words(self):
        words = _normalize_words("The quick brown fox")
        self.assertIn("quick", words)
        self.assertIn("brown", words)
        self.assertIn("fox", words)
        self.assertNotIn("the", words)


class RecipeWatchSessionModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Watch Household")
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Watchable Recipe",
            video_url="https://www.youtube.com/watch?v=abcdefghijk",
        )

    def test_session_string_and_url(self):
        session = RecipeWatchSession.objects.create(
            recipe=self.recipe,
            status=RecipeWatchSession.Status.READY,
        )
        self.assertIn("Watchable Recipe", str(session))
        self.assertEqual(
            session.get_absolute_url(),
            reverse("recipes:recipe_watch", args=[self.recipe.pk]),
        )

    def test_segment_display_time(self):
        session = RecipeWatchSession.objects.create(
            recipe=self.recipe,
            status=RecipeWatchSession.Status.READY,
        )
        segment = RecipeWatchSegment.objects.create(
            session=session,
            start_time=Decimal("75.5"),
            end_time=Decimal("80.0"),
            text="Mix gently",
        )
        self.assertEqual(segment.start_time_display, "01:15")


class RecipeWatchViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="View Household")
        self.user = User.objects.create_user(
            username="watch-user",
            email="watch@example.com",
            password="pass1234",
            household=self.household,
        )
        self.other_household = Household.objects.create(name="Other View")
        self.other_user = User.objects.create_user(
            username="other-watch-user",
            email="other-watch@example.com",
            password="pass1234",
            household=self.other_household,
        )
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Viewable Recipe",
            video_url="https://www.youtube.com/watch?v=abcdefghijk",
        )
        self.client.force_login(self.user)

    def test_get_watch_view_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse("recipes:recipe_watch", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_watch_view_for_owner(self):
        response = self.client.get(
            reverse("recipes:recipe_watch", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Watch Recipe")
        self.assertContains(response, "Generate Watch View")

    def test_get_watch_view_forbidden_for_other_household(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("recipes:recipe_watch", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_post_watch_view_triggers_processing(self):
        with patch("recipes.views.process_recipe_watch") as mock_process:
            response = self.client.post(
                reverse("recipes:recipe_watch", args=[self.recipe.pk])
            )
            mock_process.assert_called_once_with(self.recipe)
        self.assertRedirects(
            response, reverse("recipes:recipe_watch", args=[self.recipe.pk])
        )

    def test_post_watch_view_handles_error(self):
        with patch(
            "recipes.views.process_recipe_watch",
            side_effect=RuntimeError("Network down"),
        ) as mock_process:
            response = self.client.post(
                reverse("recipes:recipe_watch", args=[self.recipe.pk])
            )
            mock_process.assert_called_once_with(self.recipe)
        self.assertRedirects(
            response, reverse("recipes:recipe_watch", args=[self.recipe.pk])
        )

    def test_get_ready_view_shows_segments(self):
        session = RecipeWatchSession.objects.create(
            recipe=self.recipe,
            status=RecipeWatchSession.Status.READY,
        )
        RecipeWatchSegment.objects.create(
            session=session,
            start_time=Decimal("5"),
            end_time=Decimal("10"),
            text="Saute the vegetables",
        )
        Instruction.objects.create(
            recipe=self.recipe,
            step_number=1,
            text="Saute vegetables",
        )
        response = self.client.get(
            reverse("recipes:recipe_watch", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saute the vegetables")
        self.assertContains(response, "00:05")
        self.assertContains(response, "Saute vegetables")

    def test_watch_view_no_video_url(self):
        self.recipe.video_url = ""
        self.recipe.save()
        response = self.client.get(
            reverse("recipes:recipe_watch", args=[self.recipe.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No video URL")


class ProcessRecipeWatchServiceTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Service Household")
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Service Recipe",
            video_url="https://www.youtube.com/watch?v=abcdefghijk",
        )

    @patch("recipes.watch_service._fetch_transcript_items")
    @patch("recipes.watch_service._download_video")
    @patch("recipes.watch_service._extract_frame")
    @patch("recipes.watch_service.default_storage.save")
    def test_process_recipe_watch_creates_segments(
        self, mock_save, mock_extract, mock_download, mock_fetch
    ):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        mock_fetch.return_value = [
            {
                "start": Decimal("0"),
                "duration": Decimal("4"),
                "text": "First chunk",
            },
            {
                "start": Decimal("4"),
                "duration": Decimal("4"),
                "text": "Second chunk",
            },
        ]
        mock_save.return_value = "watch/recipe_1/frame_0001.jpg"

        with TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "video.mp4"
            video_path.write_bytes(b"fake video")
            mock_download.return_value = video_path

            # _extract_frame is expected to create the output file; do that
            # with a tiny JPEG header so the image field can inspect it later.
            def fake_extract(video_path, timestamp, output_path):
                output_path.write_bytes(
                    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
                )

            mock_extract.side_effect = fake_extract

            process_recipe_watch(self.recipe, max_segments=10)

        session = self.recipe.watch_session
        self.assertEqual(session.status, RecipeWatchSession.Status.READY)
        segments = list(session.segments.order_by("start_time"))
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "First chunk Second chunk")
        self.assertEqual(segments[0].image, "watch/recipe_1/frame_0001.jpg")
        mock_download.assert_called_once()


class ProcessRecipeWatchCommandTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Cmd Household")
        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Command Recipe",
            video_url="https://www.youtube.com/watch?v=abcdefghijk",
        )

    @patch("recipes.management.commands.process_recipe_watch.process_recipe_watch")
    def test_command_processes_single_recipe(self, mock_process):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command(
            "process_recipe_watch",
            str(self.recipe.pk),
            stdout=out,
            stderr=out,
        )
        mock_process.assert_called_once()
        output = out.getvalue()
        self.assertIn("Processing recipe", output)
