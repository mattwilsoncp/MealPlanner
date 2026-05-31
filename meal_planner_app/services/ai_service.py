"""
AI Meal Suggestions - Service layer for interacting with opencode.ai API.

Provides AIService for generating weekly meal plans via OpenAI-compatible
chat completions at https://opencode.ai/zen/v1 using free models.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import httpx

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class AIServiceResult:
    """Result from an AI generation request."""

    success: bool
    meals: list[dict] = field(default_factory=list)
    error: str | None = None


class AIService:
    """Service for interacting with opencode.ai to generate meal plans."""

    def __init__(self) -> None:
        self.base_url = settings.AI_API_BASE_URL
        self.model = settings.AI_MODEL
        self.timeout = settings.AI_REQUEST_TIMEOUT
        self.max_retries = settings.AI_MAX_RETRIES

    def generate_meal_plan(
        self,
        household: Any,
        start_date: date,
        end_date: date,
        preferences: Any | None = None,
        inventory_items: list[dict] | None = None,
    ) -> AIServiceResult:
        """Generate a complete weekly meal plan using AI.

        Args:
            household: The household model instance (for household_id).
            start_date: Start of the planning period.
            end_date: End of the planning period (inclusive).
            preferences: MealPreferences instance (optional, will load if not provided).
            inventory_items: List of available inventory items with name and expiry.

        Returns:
            AIServiceResult with parsed meal plan or error details.
        """
        # Load preferences if not provided
        if preferences is None:
            from meal_planner_app.models import MealPreferences

            try:
                preferences = MealPreferences.objects.get(household=household)
            except MealPreferences.DoesNotExist:
                preferences = None

        # Build the prompt
        prompt = self._build_prompt(
            preferences=preferences,
            start_date=start_date,
            end_date=end_date,
            inventory_items=inventory_items or [],
        )

        # Call API with retry
        return self._call_api_with_retry(prompt)

    def _build_prompt(
        self,
        preferences: Any | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        inventory_items: list[dict] | None = None,
    ) -> list[dict[str, str]]:
        """Build the chat messages for the AI API call."""
        num_days = (end_date - start_date).days + 1 if start_date and end_date else 7

        # Collect preference details
        cuisine_str = "Any"
        dietary_str = "None"
        effort_str = "Moderate (30-60 min)"
        servings = 2
        excluded_str = "None"

        if preferences:
            if prefs := getattr(preferences, "cuisine_preferences", None):
                cuisine_str = ", ".join(str(c) for c in prefs) or "Any"
            if prefs := getattr(preferences, "dietary_restrictions", None):
                dietary_str = ", ".join(str(d) for d in prefs) or "None"
            EFFORT_DISPLAY = {
                "quick": "Quick (<30 min)",
                "moderate": "Moderate (30-60 min)",
                "elaborate": "Elaborate (>60 min)",
            }
            if effort := getattr(preferences, "cooking_effort", None):
                effort_str = EFFORT_DISPLAY.get(effort, effort)
            if svgs := getattr(preferences, "servings_per_meal", None):
                servings = svgs
            if exc := getattr(preferences, "excluded_ingredients", None):
                excluded_str = ", ".join(exc) if exc else "None"

        # Inventory summary
        inventory_summary = ""
        if inventory_items:
            near_expiry = [i for i in inventory_items if i.get("expiring", False)]
            items_list = "\n".join(
                f"  - {i.get('name', 'Unknown')}{' (NEAR EXPIRY)' if i.get('expiring', False) else ''}"
                for i in inventory_items
            )
            inventory_summary = (
                f"\nAvailable inventory items (prioritize using these):\n{items_list}"
            )
            if near_expiry:
                inventory_summary += "\n\nPriority: use near-expiry items first!"

        system_prompt = (
            "You are an expert meal planning chef. "
            "Generate creative, delicious, and practical weekly meal plans. "
            "Create VARIED meals — never repeat the same dish or similar dishes in the same week. "
            "Respect all dietary restrictions and excluded ingredients strictly. "
            "Prioritize using available inventory ingredients, especially near-expiry items. "
            "Generate completely NOVEL recipes — do not suggest existing standard recipes, create new ones. "
            "For each meal, provide realistic cook time estimates and practical ingredient lists."
        )

        user_prompt = (
            f"Generate a {num_days}-day meal plan ({start_date} to {end_date}) "
            f"for {servings} serving(s) per meal.\n\n"
            f"Requirements:\n"
            f"- Cuisine preferences: {cuisine_str}\n"
            f"- Dietary restrictions: {dietary_str}\n"
            f"- Preferred cooking effort: {effort_str}\n"
            f"- Servings per meal: {servings}\n"
            f"- Excluded ingredients: {excluded_str}\n"
            f"- Each day needs meals for: Breakfast, Lunch, Dinner, Snack (4 meals per day)\n"
            f"{inventory_summary}\n\n"
            f"IMPORTANT: Return ONLY valid JSON. No markdown, no code fences, no explanations. "
            f"The response must be a JSON array of objects, one per day:\n"
            f'[\n'
            f'  {{\n'
            f'    "date": "YYYY-MM-DD",\n'
            f'    "meals": [\n'
            f'      {{\n'
            f'        "meal_type": "breakfast|launch|dinner|snack",\n'
            f'        "title": "Meal Name",\n'
            f'        "description": "Brief description",\n'
            f'        "cook_time_minutes": 30,\n'
            f'        "ingredients": ["item1", "item2"]\n'
            f'      }}\n'
            f'    ]\n'
            f'  }}\n'
            f"]"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _call_api_with_retry(self, messages: list[dict[str, str]]) -> AIServiceResult:
        """Call the AI API with exponential backoff retry logic."""
        from meal_planner_app.services.response_parser import parse_weekly_plan

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response_data = self._make_api_call(messages)
                meals = parse_weekly_plan(response_data)
                return AIServiceResult(success=True, meals=meals)

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "AI API transient error (attempt %d/%d): %s",
                        attempt,
                        self.max_retries,
                        e,
                    )
                    if attempt < self.max_retries:
                        time.sleep(2 ** attempt)
                else:
                    return AIServiceResult(
                        success=False,
                        error=f"API returned {e.response.status_code}: {e.response.text[:200]}",
                    )

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    "AI API request failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    e,
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                return AIServiceResult(
                    success=False,
                    error=f"Failed to parse AI response: {e}",
                )

        return AIServiceResult(
            success=False,
            error=f"AI API request failed after {self.max_retries} attempts: {last_error}",
        )

    def _make_api_call(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Execute the actual HTTP request to the AI API."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.8,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        # Extract the response content
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("AI response has no choices")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if not content:
            raise ValueError("AI response content is empty")

        # Parse the content as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re

            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1).strip())

            # Try to find JSON array in text
            array_match = re.search(r"\[.*\]", content, re.DOTALL)
            if array_match:
                return json.loads(array_match.group(0))

            raise
