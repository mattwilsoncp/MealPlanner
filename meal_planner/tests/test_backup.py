"""Tests for the backup/export system including watch session data."""

import io
import json
import zipfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from household.models import Household
from recipes.models import Recipe, RecipeWatchSegment, RecipeWatchSession


User = get_user_model()


class BackupWatchDataTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Backup Household")
        self.user = User.objects.create_user(
            username="backup-user",
            email="backup@example.com",
            password="pass1234",
            household=self.household,
        )
        self.client.force_login(self.user)

        self.recipe = Recipe.objects.create(
            household=self.household,
            title="Backup Watch Recipe",
            video_url="https://www.youtube.com/watch?v=abcdefghijk",
        )
        self.session = RecipeWatchSession.objects.create(
            recipe=self.recipe,
            status=RecipeWatchSession.Status.READY,
            error_message="",
        )
        self.segment = RecipeWatchSegment.objects.create(
            session=self.session,
            start_time=Decimal("5.000"),
            end_time=Decimal("10.000"),
            text="Mix the ingredients",
            step_number=1,
        )
        # Save a tiny valid JPEG to the segment's image field
        tiny_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x09\x09\x08"
            b"\x0a\x0c\x14\x0d\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d"
            b"\x1a\x1c\x1c\x20\x24\x2e\x27\x20\x22\x2c\x23\x1c\x1c\x28\x37\x29\x2c\x30"
            b"\x31\x34\x34\x34\x1f\x27\x39\x3d\x38\x32\x3c\x2e\x33\x34\x32\xff\xc0\x00"
            b"\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05"
            b"\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04"
            b"\x05\x06\x07\x08\x09\x0a\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02"
            b"\x04\x03\x05\x05\x04\x04\x00\x00\x01\x7d\x01\x02\x03\x00\x04\x11\x05\x12"
            b"\x21\x31\x41\x06\x13\x51\x61\x07\x22\x71\x14\x32\x81\x91\xa1\x08\x23\x42"
            b"\xb1\xc1\x15\x52\xd1\xf0\x24\x33\x62\x72\x82\x09\x0a\x16\x17\x18\x19\x1a"
            b"\x25\x26\x27\x28\x29\x2a\x34\x35\x36\x37\x38\x39\x3a\x43\x44\x45\x46\x47"
            b"\x48\x49\x4a\x53\x54\x55\x56\x57\x58\x59\x5a\x63\x64\x65\x66\x67\x68\x69"
            b"\x6a\x73\x74\x75\x76\x77\x78\x79\x7a\x83\x84\x85\x86\x87\x88\x89\x8a\x92"
            b"\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2"
            b"\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2"
            b"\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea"
            b"\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc4\x00\x1f\x01\x00\x03\x01"
            b"\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04"
            b"\x05\x06\x07\x08\x09\x0a\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04"
            b"\x03\x04\x07\x05\x04\x04\x00\x01\x02\x77\x00\x01\x02\x03\x11\x04\x05\x21"
            b"\x31\x06\x12\x41\x51\x07\x61\x71\x13\x22\x32\x81\x08\x14\x42\x91\xa1\xb1"
            b"\xc1\x09\x23\x33\x52\xf0\x15\x62\x72\xd1\x0a\x16\x24\x34\xe1\x25\xf1\x17"
            b"\x18\x19\x1a\x26\x27\x28\x29\x2a\x35\x36\x37\x38\x39\x3a\x43\x44\x45\x46"
            b"\x47\x48\x49\x4a\x53\x54\x55\x56\x57\x58\x59\x5a\x63\x64\x65\x66\x67\x68"
            b"\x69\x6a\x73\x74\x75\x76\x77\x78\x79\x7a\x82\x83\x84\x85\x86\x87\x88\x89"
            b"\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9"
            b"\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9"
            b"\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9"
            b"\xea\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00"
            b"\x3f\x00\x37\x07\xff\xd9"
        )
        self.segment.image.save("frame.jpg", io.BytesIO(tiny_jpeg), save=True)

    def tearDown(self):
        # Clean up the saved image file to avoid leaking files between tests
        if self.segment.image:
            self.segment.image.delete(save=False)

    def test_export_includes_watch_session_data(self):
        response = self.client.get(reverse("backup_export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        data = json.loads(zf.read("backup.json").decode("utf-8"))

        self.assertEqual(data["version"], 3)
        recipe_data = data["recipes"][0]
        self.assertIn("watch_session", recipe_data)
        self.assertEqual(
            recipe_data["watch_session"]["status"], RecipeWatchSession.Status.READY
        )
        self.assertEqual(len(recipe_data["watch_session"]["segments"]), 1)
        segment_data = recipe_data["watch_session"]["segments"][0]
        self.assertEqual(segment_data["text"], "Mix the ingredients")
        self.assertEqual(segment_data["step_number"], 1)
        self.assertIsNotNone(segment_data["frame_filename"])

        # The frame image should be in the watch_frames/ directory
        frame_path = f"watch_frames/{segment_data['frame_filename']}"
        self.assertIn(frame_path, zf.namelist())
        self.assertGreater(len(zf.read(frame_path)), 0)

    def test_import_restores_watch_session_and_images(self):
        # Export from the first household
        export_response = self.client.get(reverse("backup_export"))
        zf = zipfile.ZipFile(io.BytesIO(export_response.content))
        data = json.loads(zf.read("backup.json").decode("utf-8"))
        recipe_data = data["recipes"][0]
        frame_path = f"watch_frames/{recipe_data['watch_session']['segments'][0]['frame_filename']}"
        frame_bytes = zf.read(frame_path)

        # Create a new household and import
        new_household = Household.objects.create(name="Import Household")
        new_user = User.objects.create_user(
            username="import-user",
            email="import@example.com",
            password="pass1234",
            household=new_household,
        )
        self.client.force_login(new_user)

        import_file = io.BytesIO(export_response.content)
        import_file.name = "backup.zip"
        response = self.client.post(
            reverse("backup_import"),
            {"backup_file": import_file},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["stats"]["recipes_imported"], 1)

        recipe = Recipe.objects.get(household=new_household, title="Backup Watch Recipe")
        self.assertTrue(hasattr(recipe, "watch_session"))
        session = recipe.watch_session
        self.assertEqual(session.status, RecipeWatchSession.Status.READY)
        segments = list(session.segments.order_by("start_time"))
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "Mix the ingredients")
        self.assertEqual(segments[0].step_number, 1)
        self.assertTrue(segments[0].image)
        segments[0].image.open("rb")
        imported_bytes = segments[0].image.read()
        segments[0].image.close()
        self.assertEqual(imported_bytes, frame_bytes)
