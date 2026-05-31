# Phase 3 Summary: AI Plan Review & Acceptance

**Phase:** 03-ai-plan-review-acceptance
**Plan:** 01 (Session-based Review Flow)
**Completed:** 2026-05-31
**Tests:** 115 total (all pass), 22 new review-specific test cases

---

## What Was Built

### Views (meal_planner_app/views.py)

| View | Method | Purpose |
|------|--------|---------|
| `GenerateAiPlanView` | POST | Refactored — generates plan, stores in session as `ai_pending_plan_{pk}_{week_start}`, redirects to review page with `?week_start=YYYY-MM-DD` |
| `AiPlanReviewView` | GET | Reads session data, renders day cards with accept/reject/regenerate per-day actions |
| `AiPlanDayActionView` | POST | Handles `accept`, `reject`, `regenerate` actions per day index, updates session status |
| `AiPlanSaveView` | POST | Saves all accepted days as `MealPlan` records, clears session |
| `AiPlanCancelView` | POST | Clears session data, redirects to planner |
| `_normalize_meal_type()` | Helper | Maps meal type aliases (`brunch→lunch`, `supper→dinner`, etc.) |

### URLs (meal_planner_app/urls.py)

| Route | View | Name |
|-------|------|------|
| `ai-plan/review/` | `AiPlanReviewView` | `ai_plan_review` |
| `ai-plan/day-action/` | `AiPlanDayActionView` | `ai_plan_day_action` |
| `ai-plan/save/` | `AiPlanSaveView` | `ai_plan_save` |
| `ai-plan/cancel/` | `AiPlanCancelView` | `ai_plan_cancel` |

### Templates

- **`meal_planner/ai_plan_review.html`** — Full review page with:
  - Status summary bar (accepted/pending/rejected counts)
  - Day cards with meal details (type, title, description, cook time, ingredients)
  - Per-day action buttons (Accept Day, Regenerate, Reject / Undo Accept)
  - Save Accepted Days and Discard & Cancel bulk actions
  - Alpine.js for client-side state management
  - Empty-state redirect when no data

### Session Architecture

- **Key format:** `ai_pending_plan_{household_pk}_{week_start}`
- **Structure:**
  ```python
  {
      "week_start": "2026-06-01",
      "days": [
          {
              "index": 0,
              "date": "2026-06-01",
              "status": "pending|accepted|rejected|skipped",
              "day_name": "Monday",
              "formatted_date": "Jun 1",
              "meals": [
                  {
                      "meal_type": "breakfast",
                      "title": "Oatmeal",
                      "description": "...",
                      "cook_time_minutes": 10,
                      "ingredients": ["oats", "milk"],
                  }
              ]
          }
      ]
  }
  ```
- **Week pinning:** Review page accepts `?week_start=YYYY-MM-DD` to preserve the generated week across day actions
- **Save behavior:** Only days with `status == "accepted"` are saved; skipped/full days create no records

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Session-based (not DB) pending plan | Avoid orphan records; natural expiry on logout |
| Explicit `.exists()` slot check | PostgreSQL unique constraint allows NULL `recipe` rows for skipped slots |
| `week_start` query param | Pins the user to the generated week through multi-step review |
| `_normalize_meal_type()` | Maps LLM output variations to canonical meal types |
| Inline day cards (no partial) | Cards are simple enough that a partial added indirection without benefit |

---

## Test Coverage

### Review Workflow Tests (22 new cases)

**AiPlanReviewViewTests:**
- Requires authentication
- No `week_start` → redirects to planner
- No session data → redirects with info message
- Renders review page with day cards (asserts "Monday", "Tuesday", meals present)
- Shows correct accepted/pending/rejected counts
- Empty days list → redirects with info message

**AiPlanDayActionViewTests:**
- Requires authentication
- Missing params → redirects with error
- Invalid day index → error message
- Accept action updates status in session
- Reject action updates status
- Regenerate action (placeholder)
- Session not found → redirects to planner

**AiPlanSaveViewTests:**
- Requires authentication
- Missing `week_start` → redirects
- No session → redirects
- Saves only accepted days as MealPlan records
- Clears session after save
- Creates SideDish records from meal ingredients
- Skips empty meals gracefully
- Handles `week_start` as date string in session

**AiPlanCancelViewTests:**
- Requires authentication
- Missing `week_start` → redirects
- No session → redirects
- Clears session and redirects to planner

### Overall Test Stats
- **Total tests:** 115 (was 93 at Phase 2)
- **Pass rate:** 100%

---

## Files Modified

| File | Status | Notes |
|------|--------|-------|
| `meal_planner_app/views.py` | Modified | Added 5 new views + helper (~8KB added) |
| `meal_planner_app/urls.py` | Modified | Added 4 new routes |
| `meal_planner_app/tests.py` | Modified | Added 22 new test cases |
| `meal_planner_app/templates/meal_planner/ai_plan_review.html` | Created | Full review page with Alpine.js |
| `meal_planner_app/templates/meal_planner/planner.html` | Modified | Updated confirmation text |

---

## Git

- **Based on:** `19e6d41` (Phase 2 complete)
- **Plan committed:** `d25f31d`
- **Phase 3 code:** Committed as part of Phase 3 closure
