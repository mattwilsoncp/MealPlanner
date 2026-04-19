---
phase: 04-discovery-matching
plan: "02"
subsystem: ui
tags: [django, templates, discovery, matching]
requires:
  - phase: 04-discovery-matching
    provides: discovery matching payloads with urgency flags and deterministic sort order
provides:
  - Auth-protected discovery route wired to household-scoped matching service
  - Discovery UI cards with progress, missing ingredient badges, and urgency cues
  - Navigation entrypoint for "What Can I Make" from desktop and mobile menus
affects: [shopping, discovery-ui, navigation]
tech-stack:
  added: []
  patterns:
    - login-protected template view + service-context composition for discovery screens
    - server-computed urgency flags rendered directly in templates for deterministic behavior
key-files:
  created: []
  modified:
    - shopping/tests/test_discovery_view.py
    - shopping/views.py
    - shopping/urls.py
    - templates/shopping/discovery.html
    - templates/base.html
key-decisions:
  - "Kept urgency and expiration decisions server-driven via build_discovery_matches output to avoid client-derived trust issues."
  - "Surfaced discovery as a top-level authenticated nav item to reduce meal-time navigation friction."
patterns-established:
  - "Discovery template consumes match dictionaries directly (match_percentage, missing_ingredients, has_urgent_match, has_expired_match)."
requirements-completed: [MATCH-03, MATCH-04, MATCH-05, MATCH-06]
duration: 2 min
completed: 2026-04-19
---

# Phase 4 Plan 02: Discovery View + Template Summary

**Shipped an authenticated "What Can I Make?" experience with urgent-first ranked recipe cards, progress visualization, missing ingredient badges, and expiration urgency highlights.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-19T19:37:08Z
- **Completed:** 2026-04-19T19:39:44Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Added RED-phase discovery view tests for authentication, urgent-first ordering, and required template context keys.
- Implemented `DiscoveryView` and `/shopping/discovery/` route wired to `build_discovery_matches(request.user.household)` with `today`, `threshold_days`, and `urgent_count` context.
- Built production discovery template and base navigation links for desktop/mobile access to "What Can I Make".

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing discovery view tests for ordering and urgency display context** - `52b4990` (test)
2. **Task 2: Implement discovery route/view wiring to matching service** - `547b681` (feat)
3. **Task 3: Build discovery template with progress, missing badges, and urgent highlighting** - `f2d9de0` (feat)

## Files Created/Modified
- `shopping/tests/test_discovery_view.py` - Discovery endpoint auth and context ordering regression tests.
- `shopping/views.py` - `DiscoveryView` context assembly from household-scoped discovery matches.
- `shopping/urls.py` - Discovery route registration (`shopping:discovery`).
- `templates/shopping/discovery.html` - Ranked recipe cards with progress bars, missing badges, and urgency indicators.
- `templates/base.html` - Added "What Can I Make" link in authenticated desktop and mobile navigation.

## Decisions Made
- Used `LoginRequiredMixin` and `request.user.household` as the only discovery data boundary to satisfy threat-model isolation requirements.
- Kept urgency rendering based exclusively on `has_urgent_match` / `has_expired_match` service flags.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added a temporary discovery template shell during Task 2**
- **Found during:** Task 2
- **Issue:** View tests failed with `TemplateDoesNotExist` before planned template build task.
- **Fix:** Added a minimal `templates/shopping/discovery.html` scaffold in Task 2, then replaced it with final production UI in Task 3.
- **Files modified:** `templates/shopping/discovery.html`
- **Verification:** `.venv/bin/python manage.py test shopping.tests.test_discovery_view shopping.tests.test_generation -v 2`
- **Committed in:** `547b681`

**2. [Rule 1 - Bug] Fixed invalid login namespace assertion in RED tests**
- **Found during:** Task 2
- **Issue:** Test used `reverse("accounts:login")` but accounts URLs are not namespaced.
- **Fix:** Asserted login redirect using canonical `/accounts/login/` path.
- **Files modified:** `shopping/tests/test_discovery_view.py`
- **Verification:** `.venv/bin/python manage.py test shopping.tests.test_discovery_view -v 2`
- **Committed in:** `547b681`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes were required to keep task verification green and did not expand scope.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Discovery route and UI are in place and regression-tested.
- Ready for additional discovery iteration without changing service contract.

## Self-Check: PASSED

---
*Phase: 04-discovery-matching*
*Completed: 2026-04-19*
