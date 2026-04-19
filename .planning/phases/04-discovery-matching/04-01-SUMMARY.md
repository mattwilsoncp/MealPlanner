---
phase: 04-discovery-matching
plan: "01"
subsystem: api
tags: [django, matching, inventory, sorting]
requires:
  - phase: 03-inventory-shopping
    provides: inventory quantities, expiration metadata, and normalized ingredient matching baseline
provides:
  - Discovery matching service with missing ingredient and urgency metadata
  - Deterministic urgent-first ranking for recipe recommendations
  - Regression tests for ordering, household scoping, and expiration flags
affects: [discovery-ui, shopping, recipe-ranking]
tech-stack:
  added: []
  patterns:
    - batched household-scoped reads for recipe/inventory matching
    - deterministic sort key: urgent first, match percentage desc, title tiebreaker
key-files:
  created:
    - shopping/tests/test_matching.py
  modified:
    - shopping/services.py
key-decisions:
  - "Extended compute_meal_match with optional preloaded links to preserve API while preventing N+1 queries in discovery aggregation."
  - "Urgency/expiration state is derived only from server-side inventory expiration_date and household expiring_threshold_days."
patterns-established:
  - "Discovery match payloads include both UI-display lists and machine-usable flags for deterministic rendering."
requirements-completed: [MATCH-01, MATCH-02, MATCH-03, MATCH-05, MATCH-06]
duration: 1 min
completed: 2026-04-19
---

# Phase 4 Plan 01: Discovery Matching Service Summary

**Household-scoped discovery matching now returns missing ingredients plus urgency/expiration metadata with deterministic urgent-first ranking for UI consumption.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-19T19:34:09Z
- **Completed:** 2026-04-19T19:35:44Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added RED-phase test coverage for discovery matching contract, urgency flags, and deterministic ordering.
- Implemented `build_discovery_matches(household, as_of_date=None)` in `shopping/services.py`.
- Added household-isolation regression coverage to prevent cross-household recipe/inventory leakage.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing tests for discovery-match service contract** - `ac33346` (test)
2. **Task 2: Implement discovery-match aggregation and ordering logic** - `9f15079` (feat)

## Files Created/Modified
- `shopping/tests/test_matching.py` - TDD RED coverage for missing ingredients, urgency metadata, ordering, and household scoping.
- `shopping/services.py` - Discovery aggregation service implementation and deterministic ranking logic.

## Decisions Made
- Preserved existing `compute_meal_match` behavior while adding optional preloaded links for discovery aggregation performance.
- Used household-only ORM filters for recipes and inventory to satisfy threat-model isolation requirements.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Discovery matching service contract is stable and regression-tested.
- Ready for view/template wiring in subsequent plan(s).

## Self-Check: PASSED

---
*Phase: 04-discovery-matching*
*Completed: 2026-04-19*
