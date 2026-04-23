#!/usr/bin/env python3
"""
YouTube Recipe Importer Skill

Parse recipe data from YouTube cooking videos and insert into the database.
"""

import os
import sys
import re
import logging
from dataclasses import dataclass
from typing import Optional

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meal_planner.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from recipes.models import Recipe
from ingredients.models import Ingredient, IngredientLink
from instructions.models import Instruction

logger = logging.getLogger(__name__)


@dataclass
class ParsedIngredient:
    name: str
    quantity: str
    unit: str
    notes: str


@dataclass
class ParsedInstruction:
    step_number: int
    text: str


UNIT_NORMALIZATION = {
    "cup": "cups",
    "tbsp": "tablespoons",
    "tsp": "teaspoons",
    "oz": "ounces",
    "lb": "pounds",
}


def parse_ingredients(text: str) -> list[ParsedIngredient]:
    """Parse ingredients from text using pattern matching."""
    ingredients = []
    lines = text.split("\n")
    in_section = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for section headers
        if re.match(
            r"^(?:ingredients|directions|you[' ]?ll need)[\s:]*$", line, re.IGNORECASE
        ):
            in_section = True
            continue
        if re.match(
            r"^(?:instructions|directions|steps|method)[\s:]*$", line, re.IGNORECASE
        ):
            in_section = False
            continue

        if in_section or line.startswith(("-", "*", "•")):
            # Parse quantity
            match = re.match(
                r"^(\d+(?:[\d\/\.]+)?(?:\s*-\s*\d+)?)\s*([a-zA-Z]+)?\s*(.+)",
                line.lstrip("-*• "),
            )
            if match:
                quantity = match.group(1) or ""
                unit = match.group(2) or ""
                name = match.group(3) or line
                unit = UNIT_NORMALIZATION.get(unit.lower(), unit.lower())
                ingredients.append(
                    ParsedIngredient(name=name, quantity=quantity, unit=unit, notes="")
                )
            else:
                ingredients.append(
                    ParsedIngredient(
                        name=line.lstrip("-*• "), quantity="", unit="", notes=""
                    )
                )

    return ingredients


def parse_instructions(text: str) -> list[ParsedInstruction]:
    """Parse instructions from text."""
    instructions = []
    lines = text.split("\n")
    in_section = False
    step_num = 1

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for section headers
        if re.match(
            r"^(?:instructions|directions|steps|method)[\s:]*$", line, re.IGNORECASE
        ):
            in_section = True
            continue
        if re.match(r"^(?:ingredients)[\s:]*$", line, re.IGNORECASE):
            in_section = False
            continue

        # Match numbered steps or timestamps
        timestamp_match = re.match(r"(\d{1,2}:\d{2})\s*[-–]\s*(.+)", line)
        numbered_match = re.match(r"^\d+[.)]\s+(.+)", line)

        if timestamp_match:
            text = timestamp_match.group(2)
            instructions.append(ParsedInstruction(step_number=step_num, text=text))
            step_num += 1
        elif numbered_match:
            text = numbered_match.group(1)
            instructions.append(ParsedInstruction(step_number=step_num, text=text))
            step_num += 1
        elif in_section and not line.startswith(("-", "*", "•")):
            instructions.append(ParsedInstruction(step_number=step_num, text=line))
            step_num += 1

    return instructions[:20]  # Limit to 20 steps


def fetch_youtube_metadata(url: str, api_key: str) -> dict:
    """Fetch metadata from YouTube API."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "google-api-python-client not installed. Run: pip install google-api-python-client"
        )

    # Extract video ID
    match = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        url,
    )
    if not match:
        raise ValueError("Invalid YouTube URL")

    video_id = match.group(1)

    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()

    if not response.get("items"):
        raise ValueError("Video not found")

    snippet = response["items"][0]["snippet"]
    thumbnails = snippet.get("thumbnails", {})

    thumbnail_url = ""
    for quality in ("maxres", "high", "medium", "default"):
        if quality in thumbnails:
            thumbnail_url = thumbnails[quality]["url"]
            break

    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "thumbnail_url": thumbnail_url,
    }


def fetch_transcript(url: str) -> str:
    """Fetch transcript using markitdown."""
    try:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(url)
        return result.text_content or ""
    except ImportError:
        return ""
    except Exception:
        return ""


def import_youtube_recipe(
    youtube_url: str,
    household_id: int = None,
    user_id: int = None,
) -> dict:
    """
    Import a recipe from YouTube URL.

    Args:
        youtube_url: YouTube video URL
        household_id: Household ID (optional, auto-detected if not provided)
        user_id: User ID (optional, for determining household)

    Returns:
        dict with success, recipe_id, title, counts, error
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        api_key = getattr(
            __import__("meal_planner.settings", fromlist=["YOUTUBE_API_KEY"]),
            "YOUTUBE_API_KEY",
            None,
        )

    if not api_key:
        return {
            "success": False,
            "error": "YOUTUBE_API_KEY not configured. Set environment variable or add to settings.",
        }

    try:
        # Fetch metadata
        metadata = fetch_youtube_metadata(youtube_url, api_key)

        # Try to get transcript
        full_text = metadata["description"]
        try:
            transcript = fetch_transcript(youtube_url)
            if transcript:
                full_text = transcript
        except Exception:
            pass

        # Parse ingredients and instructions
        ingredients = parse_ingredients(full_text)
        instructions = parse_instructions(full_text)

        # Get or create household
        Household = None
        household = None
        try:
            from household.models import Household

            if household_id:
                household = Household.objects.get(id=household_id)
            elif user_id:
                User = get_user_model()
                user = User.objects.get(id=user_id)
                household = user.household
        except Exception:
            pass

        if not household:
            # Try to get first household
            try:
                household = Household.objects.first()
            except Exception:
                pass

        if not household:
            return {
                "success": False,
                "error": "No household found. Please create a household first.",
            }

        # Create recipe
        recipe = Recipe.objects.create(
            title=metadata["title"][:200],
            description=full_text[:5000] if full_text else "",
            video_url=youtube_url,
            photo_url=metadata.get("thumbnail_url", ""),
            household=household,
            needs_review=True,  # Always require review
        )

        # Create ingredients
        for ing in ingredients[:30]:  # Limit to 30
            if ing.name:
                ing_obj, _ = Ingredient.objects.get_or_create(
                    household=household,
                    name__iexact=ing.name,
                    defaults={"household": household, "name": ing.name},
                )
                IngredientLink.objects.create(
                    recipe=recipe,
                    ingredient=ing_obj,
                    quantity=float(ing.quantity) if ing.quantity else 1,
                    unit=ing.unit or "piece",
                )

        # Create instructions
        for i, inst in enumerate(instructions[:30], 1):  # Limit to 30
            if inst.text:
                Instruction.objects.create(
                    recipe=recipe,
                    step_number=inst.step_number or i,
                    text=inst.text[:1000],
                )

        return {
            "success": True,
            "recipe_id": recipe.id,
            "title": recipe.title,
            "ingredients_count": len(ingredients),
            "instructions_count": len(instructions),
        }

    except Exception as e:
        logger.exception("Failed to import YouTube recipe")
        return {
            "success": False,
            "error": str(e),
        }


# Skill loader function
def load_skill(skill_name: str = "youtube-recipe-importer"):
    """Load and return the skill callable."""
    if (
        skill_name == "youtube-recipe-importer"
        or skill_name == "youtube-recipe-importer/SKILL.md"
    ):
        return import_youtube_recipe
    raise ValueError(f"Unknown skill: {skill_name}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import YouTube recipe")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--household-id", type=int, help="Household ID")
    parser.add_argument("--user-id", type=int, help="User ID")

    args = parser.parse_args()

    result = import_youtube_recipe(args.url, args.household_id, args.user_id)

    if result["success"]:
        print(f"✓ Imported: {result['title']}")
        print(f"  Recipe ID: {result['recipe_id']}")
        print(f"  Ingredients: {result['ingredients_count']}")
        print(f"  Instructions: {result['instructions_count']}")
    else:
        print(f"✗ Error: {result['error']}")
        sys.exit(1)
