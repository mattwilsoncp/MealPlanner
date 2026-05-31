# Phase 2 Summary — AI Service & API Integration

**Plan:** 01-01-PLAN.md  
**Status:** ✅ Complete  
**Date:** 2026-05-31  
**Tests added:** 33 (5 AIService, 8 ResponseParser, 5 GenerateAiPlanView)

---

## Tasks Completed

| # | Task | Details |
|---|------|---------|
| 1 | AIService | `services/ai_service.py` — prompt builder, httpx client, 3-retry with exponential backoff (1s/2s/4s). Models: `deepseek-v4-flash-free`, `mimo-v2.5-free`, `nemotron-3-super-free`. API endpoint: `https://opencode.ai/zen/v1`. |
| 2 | ResponseParser | `services/response_parser.py` — JSON extraction, dict/list wrapping detection, meal normalization (title/description/cook_time/ingredients), cook_time default (30 min), ingredient split, missing-field resilience |
| 3 | GenerateAiPlanView | `views.py` — POST handler. Validates preferences exist (redirects if not), builds prompt with preferences + inventory, calls AIService, creates MealPlan entries, explicit slot-existence check before insert. |
| 4 | URL route | `urls.py` — `generate-ai-plan/` endpoint wired |
| 5 | AI Plan button | `planner.html` — "✨ AI Plan" form POST with confirm dialog, CSRF token, hidden week_start |
| 6 | Tests | 33 tests: AIService (prompt context, retry on 503, max retries, 4xx no retry, no-preferences fallback), ResponseParser (valid JSON, nested days key, empty, missing date, invalid date, missing title, cook_time default, ingredient string), GenerateAiPlanView (auth, missing week_start, no prefs redirect, success creates meals, API error handled, existing-slot skip) |

## Files Created/Modified

| File | Type | Purpose |
|------|------|---------|
| `meal_planner_app/services/__init__.py` | Created | New package for services |
| `meal_planner_app/services/ai_service.py` | Created | AIService class, prompt builder, httpx integration, retry logic (268 lines) |
| `meal_planner_app/services/response_parser.py` | Created | ResponseParser/parse_weekly_plan with resilient JSON extraction (158 lines) |
| `meal_planner_app/views.py` | Modified | +GenerateAiPlanView (LoginRequiredMixin, POST-only, orchestrates service→parser→model) |
| `meal_planner_app/urls.py` | Modified | +generate-ai-plan/ route |
| `meal_planner/settings.py` | Modified | +AI_API_BASE_URL, AI_MODEL_NAME, AI_TEMPERATURE, AI_MAX_TOKENS env settings |
| `meal_planner_app/templates/meal_planner/planner.html` | Modified | + "✨ AI Plan" button |
| `meal_planner_app/tests.py` | Modified | +33 new tests across 3 test classes |

## Key Design Decisions

1. **Explicit slot check** — Uses `MealPlan.objects.filter(...).exists()` before creating each meal, since `recipe=NULL` in the unique constraint doesn't raise IntegrityError (NULL ≠ NULL in SQL/postgres). IntegrityError handler kept as safety net.
2. **Default cook_time** — AI responses may omit or provide non-numeric cook_time; parser defaults to 30 minutes.
3. **No API key needed** — Endpoint tested without credentials against opencode.ai free models.
4. **Inventory loading** — Simplified to `household=household` filter; InventoryItem stores `name` directly (no ingredient FK) and has no `is_expired` field — expiration is derived from `expiration_date`.

## Verification

- `python manage.py test meal_planner_app` — **90/90 pass** (was 57 before Phase 1)
- All existing tests continue to pass
- Full project test suite TBD (depends on other apps)
