---
phase: 05-phase1-gap-remediation
plan: '02'
subsystem: recipes
tags: [ingredients, nutrition, usda, django-templates, reconciliation]
requires:
  - phase: 01-foundation-recipes
    provides: Recipe and ingredient domain models with review flow baseline
provides:
  - Household-safe ingredient-to-inventory reconciliation persistence
  - USDA identifier and nutrition snapshot persistence on Ingredient
  - Recipe detail nutrition rendering with explicit empty-state messaging
affects: [reviews, inventory, requirements-traceability]
tech-stack:
  added: []
  patterns: [household-scoped reconciliation validation, nutrition snapshot display]
key-files:
  created:
    - ingredients/tests/test_links_and_nutrition.py
    - ingredients/forms.py
    - ingredients/migrations/0003_ingredient_nutrition_fields.py
    - reviews/tests/test_review_queue.py
  modified:
    - ingredients/models.py
    - recipes/views.py
    - templates/reviews/reconcile.html
    - templates/recipes/recipe_detail.html
key-decisions:
  - "Used Ingredient-level nutrition snapshot fields for deterministic recipe detail rendering."
  - "Validated reconciliation inventory selections with a household-aware form to enforce trust boundary constraints."
patterns-established:
  - "Review reconciliation writes must validate posted inventory IDs against request.user.household."
  - "Recipe detail ingredient rows always show USDA linkage and nutrition/empty-state text."
requirements-completed: [ING-03, ING-04, ING-06]
duration: 61 min
completed: 2026-04-19
---

# Phase 05 Plan 02: Ingredient Link + Nutrition Gap Remediation Summary

**Ingredient reconciliation now persists household-safe inventory links while recipe detail surfaces USDA references and per-ingredient nutrition snapshots.**

## Performance

- **Duration:** 61 min
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- Added RED-to-GREEN coverage for ING-03/04/06 including cross-household rejection checks.
- Implemented Ingredient USDA/nutrition persistence fields with validation and migration support.
- Rendered USDA/nutrition details and empty states in recipe detail, and clarified linking intent in reconciliation UI.

## Task Commits

1. **Task 1: Add failing tests for ingredient inventory links, USDA references, and nutrition visibility** - `9a3c73e` (test)
2. **Task 2: Implement ingredient persistence and view plumbing for ING-03/04/06** - `5c6e8cd` (feat)
3. **Task 3: Render linking and nutrition fields in reconciliation/detail templates** - `e3ed9df` (feat)

## Files Created/Modified
- `ingredients/tests/test_links_and_nutrition.py` - Integration tests for reconciliation persistence, USDA id retrieval, nutrition visibility.
- `ingredients/models.py` - Added nutrition snapshot fields and recipe related_name for ingredient links.
- `ingredients/forms.py` - Added USDA/nutrition form and household-safe reconciliation validation form.
- `ingredients/migrations/0003_ingredient_nutrition_fields.py` - Adds nutrition columns and related_name alter migration.
- `recipes/views.py` - Adds household-filtered ingredient nutrition payload to recipe detail context.
- `templates/reviews/reconcile.html` - Clarifies per-row inventory linking and fixed save action URL.
- `templates/recipes/recipe_detail.html` - Displays USDA ref + macro snapshot with fallback empty-state copy.
- `reviews/tests/test_review_queue.py` - Adds reconciliation/render smoke coverage required by plan verification command.

## Decisions Made
- Stored nutrition fields directly on `Ingredient` to keep recipe detail deterministic without external API dependency at render time.
- Enforced reconciliation household boundary via form-level validation rather than trusting posted IDs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added missing `reviews.tests.test_review_queue` module for verification command**
- **Found during:** Task 3 verification
- **Issue:** Plan verification referenced `reviews.tests.test_review_queue` but file/module did not exist.
- **Fix:** Added `reviews/tests/test_review_queue.py` with queue/reconcile coverage.
- **Files modified:** `reviews/tests/test_review_queue.py`
- **Verification:** `.venv/bin/python manage.py test reviews.tests.test_review_queue -v 2`
- **Committed in:** `e3ed9df`

**2. [Rule 1 - Bug] Fixed malformed reconcile template URL tag**
- **Found during:** Task 3 verification
- **Issue:** `reconcile.html` had malformed `{% url %}` syntax causing `TemplateSyntaxError`.
- **Fix:** Corrected `action` to `{% url 'reviews:save_reconciliation' object.pk %}`.
- **Files modified:** `templates/reviews/reconcile.html`
- **Verification:** Full task verification command passed.
- **Committed in:** `e3ed9df`

**3. [Rule 3 - Blocking] Created migration as `0003` due pre-existing `0002`**
- **Found during:** Task 2 implementation
- **Issue:** Plan specified `0002_ingredient_nutrition_fields.py`, but repository already had `0002_ingredientlink_inventory_item.py`.
- **Fix:** Created `ingredients/migrations/0003_ingredient_nutrition_fields.py` with correct dependency chain.
- **Files modified:** `ingredients/migrations/0003_ingredient_nutrition_fields.py`
- **Verification:** Ingredient test suite applies migrations and passes.
- **Committed in:** `5c6e8cd`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** All deviations were required for correctness and successful verification; no scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ING-03, ING-04, and ING-06 behaviors are now explicitly implemented and tested.
- Ready for next remediation plan.

## Self-Check: PASSED
