# Research Summary: AI Meal Suggestions

**Milestone:** v1.2 — AI Meal Suggestions
**Date:** 2026-05-31

---

## Key Findings

### API Integration
- **opencode.ai/zen/v1** provides free, OpenAI-compatible chat completions
- No API key required currently (cost: $0)
- Available models: deepseek-v4-flash-free (recommended), mimo-v2.5-free, nemotron-3-super-free
- Standard chat completions format with `response_format: { type: "json_object" }` for structured output
- ~3-10s response time for meal plan generation

### Recommended Stack Additions
- **httpx** for HTTP requests from Django
- **MealPreferences** model (one-to-one with Household)
- **AIMealService** service class for API orchestration
- No Celery/Redis needed for v1.2 — use synchronous requests with loading spinner

### Feature Design
- Table stakes: preference config, one-click generation, accept/reject/regenerate
- Differentiator: inventory-aware planning that prefers expiring ingredients
- Anti-features: no nutrition tracking, no image generation, no multi-user

### Architecture
- **Phase 1:** MealPreferences model + preferences UI
- **Phase 2:** AI service + opencode.ai API integration
- **Phase 3:** AI generation view + preview UI
- **Phase 4:** Accept/regenerate/reject workflow + shopping list integration

### Watch Out For
| Risk | Fix |
|------|-----|
| JSON parsing failures | Use `response_format: json_object` + fallback |
| AI ignores dietary restrictions | Validate in prompt AND output |
| Overwriting existing plans | Separate "AI suggestions" layer that doesn't touch DB until accepted |
| API rate limits | Request-level throttling + retry with backoff |
| Repetitive suggestions | Prompt variety constraints + ingredient diversity |

---

## Implementation Path

**Short version for REQUIREMENTS.md:** Four phases, starting with user preference configuration, then API integration for generation, then the review + save workflow.

**AI prompt pattern:**
```
System: You are a meal planning assistant. Create a weekly meal plan for {servings} people.
Generate novel recipes based on the user's preferences and available inventory.
Output valid JSON with the following structure: {days: [{date, meal_type, title, description, cook_time_minutes, ingredients}]}

User preferences:
- Cuisines: {cuisines}
- Dietary restrictions: {restrictions}
- Cooking effort: {effort}
- Excluded ingredients: {excluded}

Available inventory (use these first, especially items near expiry):
- Perishable: {items}
- Pantry: {items}
```
