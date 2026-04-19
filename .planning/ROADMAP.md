# Meal Planner App v2 — Roadmap

**Project:** Meal Planner App v2  
**Phases:** 4  
**Granularity:** Coarse  
**Last Updated:** 2026-04-19

---

## Phase Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Foundation & Recipes | User auth, household context, complete recipe management with review workflow | 25 | 8 |
| 2 | Meal Planning | Weekly planner, meal types, on-hand ideas, cooking reconciliation | 15 | 6 |
| 3 | Inventory & Shopping | Inventory management, barcode scanning, shopping list generation | 17 | 6 |
| 4 | Discovery & Matching | "What Can I Make?" recipe matching with expiration awareness | 6 | 4 |

**Total: 4 phases | 63 requirements | 24 success criteria**

---

## Phase 1: Foundation & Recipes

**Goal:** Complete authentication, household context, and recipe management with review workflow.

### Requirements

- AUTH-01 through AUTH-04 (User authentication)
- HOUSE-01 through HOUSE-02 (Household context)
- REC-01 through REC-12 (Recipe CRUD, list, search, sorting)
- ING-01 through ING-06 (Recipe ingredients)
- INST-01 through INST-03 (Recipe instructions)
- TAG-01 through TAG-02 (Tags)
- RATE-01 through RATE-04 (Ratings)
- REV-01 through REV-07 (Review workflow)
- UI-01 through UI-06 (UI/UX foundation)

### Success Criteria

1. User can register, login, and logout
2. All data is properly scoped to household
3. User can create, view, edit, delete recipes with full details
4. Recipe list shows cards with image, title, rating, tags
5. Search and sort work correctly
6. Recipe review queue shows needs_review recipes with inventory matching
7. User can reconcile ingredients and mark recipes ready
8. UI is styled with Tailwind/DaisyUI, responsive

### Dependencies

- None — this is the foundation

### Plans

- [x] 01-01-PLAN.md — Django project setup, authentication, household model
- [x] 01-02-PLAN.md — Recipe model and CRUD operations
- [x] 01-03-PLAN.md — Ingredient, Instruction, Tag, Rating models
- [x] 01-04-PLAN.md — Recipe search, sorting, needs_review filtering
- [x] 01-05-PLAN.md — Recipe review workflow with reconciliation
- [x] 01-06-PLAN.md — UI polish with responsive design, modals, JSON endpoints

---

## Phase 2: Meal Planning

**Goal:** Complete weekly meal planner with meal types, side dishes, on-hand ideas, leftover tracking, and cooking reconciliation.

### Requirements

- MEAL-01 through MEAL-11 (Meal planning)
- ONHAND-01 through ONHAND-04 (On-hand ideas)
- LEFT-01 through LEFT-03 (Leftover tracking)
- COOK-01 through COOK-08 (Cooking reconciliation)
- SIDE-01 through SIDE-02 (Side dishes — implicit in MEAL-11)

### Success Criteria

1. Weekly planner shows 7 days with meal type sections
2. User can navigate between weeks
3. User can add, edit, delete meals (recipe-linked or custom)
4. On-hand ideas modal works for quick meal insertion
5. Cooking reconciliation page tracks inventory usage
6. Leftover-worthy recipes surface appropriately

### Dependencies

- Requires Phase 1 (recipes must exist to plan meals)

### Plans

- [x] 02-01-PLAN.md — MealPlan model and weekly planner view
- [x] 02-02-PLAN.md — Meal CRUD operations (add, edit, delete, rate)
- [x] 02-03-PLAN.md — Recipe linking and side dishes
- [x] 02-04-PLAN.md — On-hand ideas and leftover tracking
- [x] 02-05-PLAN.md — Cooking reconciliation

---

## Phase 3: Inventory & Shopping

**Goal:** Complete inventory management, barcode scanning, and shopping list generation.

### Requirements

- INV-01 through INV-12 (Inventory CRUD, filtering, preferences)
- BAR-01 through BAR-04 (Barcode scanning)
- SHOP-01 through SHOP-07 (Shopping list)
- MATCH-01 through MATCH-02 (Matching basics — partial)

### Success Criteria

1. Inventory list with category grouping and filtering
2. User can add, edit, delete inventory items
3. Expiring items page shows items nearing expiration
4. Barcode scan creates inventory from UPC API
5. Shopping list auto-generates from meal plan
6. User can check/uncheck and manage list items

### Dependencies

- Requires Phase 1 (ingredients for linking)
- Requires Phase 2 (meal plan for shopping list generation)

### Plans

**Plans:** 5 plans

- [x] 03-01-PLAN.md — Inventory schema contracts (metadata + household expiration preference)
- [x] 03-02-PLAN.md — Inventory CRUD/list/filter/expiration flows + quick-add endpoint
- [x] 03-03-PLAN.md — Barcode scan page with local-first lookup and UPC fallback
- [ ] 03-04-PLAN.md — Shopping app foundation with week-based generator + match metrics
- [x] 03-05-PLAN.md — Shopping checklist actions, UI, and navigation wiring

---

## Phase 4: Discovery & Matching

**Goal:** "What Can I Make?" recipe matching with inventory and expiration awareness.

### Requirements

- MATCH-01 through MATCH-06 (Recipe matching)
- UI enhancements for matching display

### Success Criteria

1. Page loads recipes and computes match percentage vs inventory
2. Recipes sorted by match percentage
3. Progress bars and missing ingredient badges shown
4. Expiring/expired items highlighted, urgent recipes surfaced

### Dependencies

- Requires Phase 1 (recipes)
- Requires Phase 3 (inventory matching)

---

## Phase Transition Notes

After each phase:
1. Verify all success criteria met
2. Update REQUIREMENTS.md status
3. Mark requirements as validated in PROJECT.md
4. Review and update Out of Scope if needed

---

## Future Considerations (Post-v1)

These items were identified but deferred to v2+:
- Recipe URL import (complexity around JS-rendered sites)
- Drag-and-drop meal reordering
- Recipe filtering by cuisine on planner
- Light mode UI
- Multi-user household sharing
- Nutrition tracking
- AI-powered meal suggestions

---

*Last updated: 2026-04-19*
