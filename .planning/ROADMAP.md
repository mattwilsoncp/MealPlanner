# Meal Planner App v2 — Roadmap

## Milestones

- ✅ **v1** — Shipped 2026-04-19 (6 phases, 21 plans) — see `.planning/milestones/v1-ROADMAP.md`
- ✅ **v1.1** — YouTube Recipe Import — Shipped 2026-05-?? (4 phases) — see `.planning/v1.1-ROADMAP.md`
- [ ] **v1.2** — AI Meal Suggestions (4 phases) — see below

## Backlog

- Light mode UI
- Multi-user household sharing
- Nutrition tracking
- Recipe filtering by cuisine on planner

Use `/gsd-new-milestone` to define the next milestone roadmap and requirements.

## v1.2: AI Meal Suggestions

**4 phases** | **30 requirements** | **Defined:** 2026-05-31

### Phase 1: Preferences Configuration (7 requirements)

Create the MealPreferences model and preferences UI.

| Req | Description |
|-----|-------------|
| PREF-01 | Cuisine preferences (multi-select) |
| PREF-02 | Dietary restrictions (checkboxes) |
| PREF-03 | Cooking effort setting |
| PREF-04 | Servings per meal |
| PREF-05 | Excluded ingredients |
| PREF-06 | Preferences UI page |
| PREF-07 | Persist per household |

### Phase 2: AI Service & API Integration (12 requirements)

Build the AI orchestration service and integrate with opencode.ai API.

| Req | Description |
|-----|-------------|
| GENR-01 | "Generate AI Plan" button on planner |
| GENR-02 | Collect preferences + inventory + date range |
| GENR-03 | Call opencode.ai API |
| GENR-04 | Use free model |
| GENR-05 | Error handling |
| GENR-06 | Retry logic |
| GENR-07 | Parse JSON response |
| GENR-08 | Coverage for date range |
| GENR-09 | Inventory-aware suggestions |
| GENR-10 | Variety in meal suggestions |
| GENR-11 | Dietary restriction enforcement |
| TEST-01 | AI service unit tests |

### Phase 3: AI Plan Review & Acceptance (8 requirements)

Build the interactive review workflow for AI-generated meal plans.

| Req | Description |
|-----|-------------|
| REVW-01 | Preview full AI week |
| REVW-02 | Accept individual day |
| REVW-03 | Regenerate individual day |
| REVW-04 | Reject individual day |
| REVW-05 | Accept all ("Save Plan") |
| REVW-06 | Save as MealPlan records |
| REVW-07 | Don't overwrite existing entries |
| REVW-08 | Cancel mid-generation |
| TEST-03 | Review workflow tests |

### Phase 4: Shopping List & Polish (3 requirements + 1 test)

Calculate missing ingredients and integrate with shopping list.

| Req | Description |
|-----|-------------|
| SHOP-01 | Calculate missing ingredients |
| SHOP-02 | Add missing items to shopping list |
| SHOP-03 | Don't duplicate existing inventory items |
| TEST-04 | Overall coverage >= 94% |
