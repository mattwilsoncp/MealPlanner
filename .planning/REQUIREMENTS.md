# Requirements: Meal Planner v1.2 — AI Meal Suggestions

**Defined:** 2026-05-31
**Core Value:** Help users plan their weekly meals with AI-generated suggestions that use available inventory and match their preferences.

## v1.2 Requirements

### Preferences Configuration

- [ ] **PREF-01**: User can set cuisine preferences (multi-select: Italian, Mexican, Asian, American, Mediterranean, etc.)
- [ ] **PREF-02**: User can set dietary restrictions (checkboxes: vegetarian, vegan, gluten-free, dairy-free, low-carb, keto)
- [ ] **PREF-03**: User can set cooking effort preference (quick <30min, moderate 30-60min, elaborate >60min)
- [ ] **PREF-04**: User can set servings per meal (1-8, default 2)
- [ ] **PREF-05**: User can add excluded ingredients (free-text tags)
- [ ] **PREF-06**: User can view and edit their current preferences on a dedicated page
- [ ] **PREF-07**: Preferences persist per household and are restored on return

### AI Meal Generation

- [ ] **GENR-01**: User can click "Generate AI Plan" on the weekly planner page
- [ ] **GENR-02**: System collects preferences, available inventory, and date range before generating
- [ ] **GENR-03**: System sends a structured prompt to opencode.ai/zen/v1 (OpenAI-compatible API)
- [ ] **GENR-04**: System uses a free model (deepseek-v4-flash-free, mimo-v2.5-free, or nemotron-3-super-free)
- [ ] **GENR-05**: System handles API errors gracefully with a user-friendly error message
- [ ] **GENR-06**: System retries on transient API failures with exponential backoff (max 3 attempts)
- [ ] **GENR-07**: System parses AI response as structured JSON (title, meal_type, description, cook_time, ingredients per day)
- [ ] **GENR-08**: Generated plan covers all days in the selected date range
- [ ] **GENR-09**: System prefers using available inventory items (especially near-expiry perishables) in suggestions
- [ ] **GENR-10**: System generates unique, varied meals (no repeating similar dishes in the same week)
- [ ] **GENR-11**: Generated meals respect dietary restrictions (validated in prompt AND output)

### AI Plan Review & Acceptance

- [ ] **REVW-01**: User can preview the full AI-generated week before saving
- [ ] **REVW-02**: User can accept an individual day's meal suggestion
- [ ] **REVW-03**: User can regenerate an individual day's meal suggestion
- [ ] **REVW-04**: User can reject an individual day's meal suggestion (removes from preview)
- [ ] **REVW-05**: User can accept all remaining suggestions at once ("Save Plan")
- [ ] **REVW-06**: Accepting a suggestion saves it as a MealPlan record with custom_meal text
- [ ] **REVW-07**: Saving a plan does not overwrite existing meal entries (skips populated slots)
- [ ] **REVW-08**: User can cancel the AI plan generation mid-process

### Shopping List Integration

- [ ] **SHOP-01**: System calculates missing ingredients between AI-generated meals and current inventory
- [ ] **SHOP-02**: Missing ingredients are added to the shopping list upon plan acceptance
- [ ] **SHOP-03**: Items already in inventory are noted and not duplicated in shopping list

### Testing

- [ ] **TEST-01**: AI service unit tests cover prompt construction, response parsing, error handling
- [ ] **TEST-02**: Preference model and views have full test coverage
- [ ] **TEST-03**: AI plan review workflow is tested (accept/regenerate/reject/save combinations)
- [ ] **TEST-04**: Overall test coverage stays at or above 94%

## v2 Requirements (Deferred)

### Enhanced Preferences

- **PREF-08**: User can set calorie/nutritional targets
- **PREF-09**: User can set budget per meal/per week
- **PREF-10**: User can rate past AI-generated meals to improve future suggestions

### Advanced AI Features

- **GENR-12**: AI suggests meal prep timings (what to cook when)
- **GENR-13**: AI generates step-by-step cooking instructions
- **GENR-14**: System learns from user's accept/reject patterns over time
- **GENR-15**: User can generate plans for specific occasions (e.g., "dinner party for 6")

### Export & Printing

- **SHOP-04**: User can print/export the weekly menu
- **SHOP-05**: User can print a consolidated grocery list

## Out of Scope

| Feature | Reason |
|---------|--------|
| Nutritional / calorie calculation | High complexity, requires food database. Defer to v2+ |
| AI image generation for recipes | Would require separate model/workflow. Not core to planning |
| Multi-user collaborative planning | Beyond hh scope for v1.2 |
| Offline/Air-gapped mode | Requires local model serving. Focus on API-based for now |
| Meal prep timeline scheduler | Adds scheduling complexity. Defer to future release |
| Integration with external meal delivery | Business logic outside current scope |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PREF-01 | Phase 1 | Pending |
| PREF-02 | Phase 1 | Pending |
| PREF-03 | Phase 1 | Pending |
| PREF-04 | Phase 1 | Pending |
| PREF-05 | Phase 1 | Pending |
| PREF-06 | Phase 1 | Pending |
| PREF-07 | Phase 1 | Pending |
| GENR-01 | Phase 2 | Pending |
| GENR-02 | Phase 2 | Pending |
| GENR-03 | Phase 2 | Pending |
| GENR-04 | Phase 2 | Pending |
| GENR-05 | Phase 2 | Pending |
| GENR-06 | Phase 2 | Pending |
| GENR-07 | Phase 2 | Pending |
| GENR-08 | Phase 2 | Pending |
| GENR-09 | Phase 2 | Pending |
| GENR-10 | Phase 2 | Pending |
| GENR-11 | Phase 2 | Pending |
| REVW-01 | Phase 3 | Pending |
| REVW-02 | Phase 3 | Pending |
| REVW-03 | Phase 3 | Pending |
| REVW-04 | Phase 3 | Pending |
| REVW-05 | Phase 3 | Pending |
| REVW-06 | Phase 3 | Pending |
| REVW-07 | Phase 3 | Pending |
| REVW-08 | Phase 3 | Pending |
| SHOP-01 | Phase 4 | Pending |
| SHOP-02 | Phase 4 | Pending |
| SHOP-03 | Phase 4 | Pending |
| TEST-01 | Phase 2 | Pending |
| TEST-02 | Phase 1 | Pending |
| TEST-03 | Phase 3 | Pending |
| TEST-04 | Phase 4 | Pending |

**Coverage:**
- v1.2 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-31*
*Last updated: 2026-05-31 after initial definition*
