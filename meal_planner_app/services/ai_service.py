"""
AI Meal Suggestions - Service layer for talking to the OpenRouter API.

Provides AIService for generating weekly meal plans via OpenAI-compatible
chat completions at https://openrouter.ai/api/v1. Model selection and the
API key are resolved per call from
``meal_planner_app.services.ai_settings`` so every household can pick
its own model per feature from the settings page.
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


class _AIContentTruncatedError(Exception):
    """Raised when a reasoning model empties its token budget before emitting content.

    Distinct from a generic parse failure so the retry logic can retry with a
    larger budget instead of giving up on the same payload.
    """


# Reasoning models (e.g. deepseek-v4-flash) burn tokens on chain-of-thought that
# land in `reasoning_content`, leaving little room for the visible answer in
# `content`. 8192 leaves comfortable headroom for a 7-day plan; if that is
# still not enough we double once and cap at 16384 instead of retrying the
# same payload.
AI_MAX_TOKENS_DEFAULT = 8192
AI_MAX_TOKENS_FLOOR = 16384


class AIService:
    """Service for talking to OpenRouter to generate meal plans.

    Model selection and API key are resolved per call from
    ``meal_planner_app.services.ai_settings``: the constructor accepts
    a ``household`` so the per-household ``AISettings`` row is honored,
    plus an optional OpenRouter model ``override`` that wins over the
    saved binding.
    """

    def __init__(
        self,
        household: Any | None = None,
        *,
        feature: str = "meal_plan_generation",
        model_override: str | None = None,
        progress_callback=None,
    ) -> None:
        self.base_url = settings.AI_API_BASE_URL
        self.timeout = settings.AI_REQUEST_TIMEOUT
        self.max_retries = settings.AI_MAX_RETRIES
        self.household = household
        self.feature = feature
        self.model_override = model_override
        # Optional callback the view wires up so the generator can
        # stream progress events to the planner page as the model runs.
        # Signature: ``progress_callback(label, detail=None, kind="progress")``
        # — ``kind`` lets the view distinguish progress from terminal states
        # if it wants a single callback for both.
        self._progress = progress_callback

    def _report(self, label: str, detail: str | None = None, kind: str = "progress") -> None:
        """Push a progress event to the optional callback.

        All exceptions inside the callback are swallowed so a bad listener
        cannot fail the underlying generation.
        """
        if self._progress is None:
            return
        try:
            self._progress(label, detail, kind)
        except Exception:  # pragma: no cover - defensive
            logger.debug("progress callback raised", exc_info=True)

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
        # Keep the active household fresh; an instance may have been built
        # without one (e.g. CLI callers) so prefer the call-site argument.
        if household is not None:
            self.household = household

        # Load preferences if not provided
        if preferences is None and self.household is not None:
            from meal_planner_app.models import MealPreferences

            try:
                preferences = MealPreferences.objects.get(household=self.household)
            except MealPreferences.DoesNotExist:
                preferences = None

        # Build the prompt
        num_days = (end_date - start_date).days + 1 if start_date and end_date else 7
        self._report(
            "Preparing prompt",
            f"{num_days} day(s) of meals with your preferences and pantry",
        )
        prompt = self._build_prompt(
            preferences=preferences,
            start_date=start_date,
            end_date=end_date,
            inventory_items=inventory_items or [],
        )

        # Call API with retry — long-running stage, the caller gets
        # sub-progress updates from inside the retry loop.
        self._report(
            "Talking to the model",
            f"Asking the model for a {num_days}-day plan",
        )
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
        max_tokens = AI_MAX_TOKENS_DEFAULT

        for attempt in range(1, self.max_retries + 1):
            try:
                response_data = self._make_api_call(
                    messages, max_tokens=max_tokens, household=self.household
                )
                self._report("Reading model response", "HTTP 200 received")
                meals = parse_weekly_plan(response_data)
                self._report(
                    "Saving review data",
                    f"Parsed {len(meals)} day(s) of meals",
                )
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
                    self._report(
                        "Transient error, retrying",
                        f"HTTP {e.response.status_code}; backing off and retrying",
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
                self._report(
                    "Network hiccup, retrying",
                    f"{type(e).__name__}: {e}",
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

            except _AIContentTruncatedError as e:
                last_error = e
                if max_tokens < AI_MAX_TOKENS_FLOOR and attempt < self.max_retries:
                    max_tokens = min(max_tokens * 2, AI_MAX_TOKENS_FLOOR)
                    logger.warning(
                        "AI content empty after reasoning budget (attempt %d/%d); "
                        "retrying with max_tokens=%d: %s",
                        attempt,
                        self.max_retries,
                        max_tokens,
                        e,
                    )
                    self._report(
                        "Model ran out of room, retrying",
                        f"Bumping max_tokens to {max_tokens}",
                    )
                    continue
                self._report("Model ran out of room", "Fatal after retries", kind="error")
                return AIServiceResult(
                    success=False,
                    error=(
                        f"AI response content is empty after {self.max_retries} attempts "
                        f"(finish_reason=length, max_tokens={max_tokens}); the model used "
                        "the full token budget for reasoning before emitting content"
                    ),
                )

            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                self._report(
                    "Could not parse response",
                    f"{type(e).__name__}: {e}",
                    kind="error",
                )
                return AIServiceResult(
                    success=False,
                    error=f"Failed to parse AI response: {e}",
                )

        self._report(
            "AI unreachable",
            f"All {self.max_retries} attempts failed",
            kind="error",
        )
        return AIServiceResult(
            success=False,
            error=f"AI API request failed after {self.max_retries} attempts: {last_error}",
        )

    def _make_api_call(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = AI_MAX_TOKENS_DEFAULT,
        household: Any | None = None,
    ) -> dict[str, Any]:
        """Execute the actual HTTP request to the AI API.

        Resolves the model id and per-household API key from
        ``meal_planner_app.services.ai_settings`` on each call so a
        settings change takes effect without restarting the worker.

        Raises ``_AIContentTruncatedError`` when the API responds 200 OK but the
        model used every token for reasoning and never emitted a visible reply;
        the retry loop handles that with a larger ``max_tokens`` budget.
        """
        from meal_planner_app.services.ai_settings import (
            resolve_model,
            resolve_openrouter_api_key,
        )

        active_household = household if household is not None else self.household
        model_id = resolve_model(active_household, self.feature, self.model_override)
        api_key = resolve_openrouter_api_key(active_household)

        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.8,
        }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        # Extract the response content
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("AI response has no choices")

        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        message = choice.get("message", {})
        content = message.get("content", "")

        if not content:
            # Reasoning models (e.g. deepseek-v4-flash) sometimes burn the
            # entire token budget on chain-of-thought and never emit visible
            # content. Surface that as a retryable, distinct condition so the
            # retry loop can grow the budget instead of failing permanently.
            if finish_reason == "length":
                raise _AIContentTruncatedError(
                    f"AI used all {max_tokens} tokens before emitting content "
                    f"(finish_reason=length)"
                )
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
