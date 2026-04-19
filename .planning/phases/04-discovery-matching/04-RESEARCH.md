# Phase 4 Research: Discovery & Matching

**Phase:** 4 — Discovery & Matching  
**Date:** 2026-04-19  
**Status:** Ready for planning

## Scope Focus

Implement remaining matching requirements for the "What Can I Make?" flow:
- MATCH-03 sort by match percentage
- MATCH-04 show progress bars + missing ingredient badges
- MATCH-05 highlight expiring/expired inventory impact in results
- MATCH-06 surface recipes using urgent ingredients

## Existing Foundation Confirmed

- `shopping/services.py::compute_meal_match()` already computes `available_count`, `total_count`, and `match_percentage` (MATCH-01/02 baseline).
- `inventory.models.InventoryItem` includes `expiration_date` and household scoping, and `household.models.Household` includes `expiring_threshold_days`.
- `shopping/views.py` and `templates/shopping/shopping_week.html` establish server-rendered + selective JS pattern for shopping domain features.

## Implementation Direction

1. Keep matching logic in `shopping/services.py` (service-layer pattern already established in Phase 3).
2. Add a dedicated discovery view/template in `shopping` app (same bounded context as matching + shopping generation).
3. Build match detail payload per recipe:
   - counts + percentage
   - missing ingredient list
   - urgent ingredient indicators from household expiration threshold
4. Sort results by urgency first (has urgent ingredients), then by descending match percentage.

## Constraints and Pitfalls to Enforce

- Household isolation on all recipe/inventory reads.
- Ingredient matching must stay normalized (`casefold().strip()` conventions already used).
- Avoid free-text-only display data; include machine-usable flags (`is_urgent`, `is_expired`) for deterministic UI/test checks.
- Keep feature server-rendered (no SPA rewrite), aligned with project architecture.

## Verification Targets

- Automated tests for service matching output shape and ordering.
- Automated tests for discovery page response + sorted context data.
- `manage.py check` and targeted test module passes.
