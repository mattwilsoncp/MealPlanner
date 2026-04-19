# Meal Planner App v2 — Requirements

## v1 Requirements

> Audit status (2026-04-19): Verification artifacts and runtime evidence are in place; milestone v1 is ready to close pending close-command execution.

### Authentication & Household

- [ ] **AUTH-01**: User can register a new account with email/password
- [ ] **AUTH-02**: User can log in and stay logged in across sessions
- [ ] **AUTH-03**: User can log out from any page
- [ ] **AUTH-04**: Unauthenticated users are redirected to login
- [ ] **HOUSE-01**: User has an associated household record for data scoping
- [ ] **HOUSE-02**: All data operations are scoped to user's household

### Recipe Management

- [ ] **REC-01**: User can create a recipe with title, description
- [ ] **REC-02**: User can upload a photo for a recipe
- [ ] **REC-03**: User can add an optional video URL to a recipe
- [ ] **REC-04**: User can add custom flags (on_hand_idea, leftover_worthy, needs_review)
- [ ] **REC-05**: User can view recipe list as a card/grid
- [ ] **REC-06**: User can search recipes by title/description
- [ ] **REC-07**: User can sort recipes (rated first, then by rating value, then by date)
- [ ] **REC-08**: User can view individual recipe details
- [ ] **REC-09**: User can edit a recipe
- [ ] **REC-10**: User can delete a recipe with confirmation
- [ ] **REC-11**: Recipes with needs_review=True are excluded from normal list
- [x] **REC-12**: Review queue page shows recipes needing review

### Recipe Ingredients

- [ ] **ING-01**: User can add structured ingredients to a recipe
- [ ] **ING-02**: Ingredients have name, quantity, unit, order
- [x] **ING-03**: User can link an ingredient to an inventory item
- [x] **ING-04**: User can link an ingredient to a USDA food reference
- [ ] **ING-05**: User can delete an ingredient from a recipe
- [x] **ING-06**: User can view ingredient nutrition data

### Recipe Instructions

- [ ] **INST-01**: User can add ordered instructions to a recipe
- [x] **INST-02**: User can reorder instructions
- [ ] **INST-03**: User can delete an instruction

### Recipe Tags & Ratings

- [ ] **TAG-01**: User can assign tags to a recipe
- [x] **TAG-02**: User can create new tags when editing a recipe
- [ ] **RATE-01**: User can rate a recipe 1-5
- [ ] **RATE-02**: User can add notes to a rating
- [ ] **RATE-03**: Ratings are upserted (one current rating per recipe)
- [ ] **RATE-04**: Recipe displays computed rating (average or meal-plan-derived)

### Recipe Review Workflow

- [ ] **REV-01**: Recipes flagged needs_review appear in review queue
- [ ] **REV-02**: Review page shows recipe ingredients vs inventory matching
- [ ] **REV-03**: User can reconcile ingredients with inventory via dropdown
- [ ] **REV-04**: User can quick-add inventory items inline during reconciliation
- [ ] **REV-05**: User can save ingredient-to-inventory links
- [ ] **REV-06**: User can mark recipe as ready (needs_review=False)
- [ ] **REV-07**: User can mark recipe ready directly without reconciliation

### Meal Planning

- [x] **MEAL-01**: Weekly planner view shows 7 days
- [x] **MEAL-02**: User can navigate between weeks (prev/next)
- [x] **MEAL-03**: Week has meal types: breakfast, lunch, dinner, snack
- [x] **MEAL-04**: User can add multiple meals per type per day
- [x] **MEAL-05**: User can link a recipe to a meal slot
- [x] **MEAL-06**: User can add custom/free-text meals
- [x] **MEAL-07**: User can update a meal (change recipe or notes)
- [x] **MEAL-08**: User can delete a meal
- [x] **MEAL-09**: User can rate a meal plan entry
- [x] **MEAL-10**: User can view linked recipe from meal card
- [x] **MEAL-11**: User can add side dishes to a meal (linked to recipe or custom text)

### On-Hand Ideas & Leftovers

- [x] **ONHAND-01**: User can mark recipes as on_hand_idea
- [x] **ONHAND-02**: Modal shows list of on-hand idea recipes
- [x] **ONHAND-03**: User can add/remove recipes from on-hand list
- [x] **ONHAND-04**: User can swap on-hand idea into meal slot
- [x] **LEFT-01**: User can flag recipes as leftover_worthy
- [x] **LEFT-02**: Planner loads leftover-worthy meals by date
- [x] **LEFT-03**: User can plan leftover meals

### Cooking Reconciliation

- [x] **COOK-01**: User can initiate cooking from a meal card
- [x] **COOK-02**: Reconciliation page shows recipe ingredients (left) and inventory (right)
- [x] **COOK-03**: Inventory separated into "Still Have" and "Used / Ran Out"
- [x] **COOK-04**: User can check off recipe ingredients visually
- [x] **COOK-05**: User can move inventory items between sections
- [x] **COOK-06**: User can mark all inventory as used
- [x] **COOK-07**: User can add recipe ingredient to inventory inline
- [x] **COOK-08**: Confirm button processes used items and updates inventory

### Shopping List

- [x] **SHOP-01**: Shopping list is week-based
- [x] **SHOP-02**: Opening page auto-loads current week
- [x] **SHOP-03**: Auto-generate list from meal plan if none exists
- [x] **SHOP-04**: User can regenerate week's shopping list
- [x] **SHOP-05**: User can check/uncheck items
- [x] **SHOP-06**: User can delete individual items
- [x] **SHOP-07**: User can clear entire week list

### Inventory Management

- [x] **INV-01**: User can view inventory list
- [x] **INV-02**: Inventory grouped by category with Uncategorized fallback
- [x] **INV-03**: User can filter inventory by category
- [x] **INV-04**: User can filter inventory by location
- [x] **INV-05**: User can search inventory
- [x] **INV-06**: User can add inventory item (name, quantity, unit, category, location, expiration, notes, image, barcode)
- [x] **INV-07**: User can edit inventory item
- [x] **INV-08**: User can delete inventory item
- [x] **INV-09**: User can view expiring items
- [x] **INV-10**: User can view expired items
- [x] **INV-11**: User can configure expiring-item threshold days
- [x] **INV-12**: User can quick-add inventory from recipe/cooking pages

### Barcode Scanning

- [x] **BAR-01**: Dedicated barcode scan page
- [x] **BAR-02**: Barcode lookup checks user's existing inventory first
- [x] **BAR-03**: If not found, query UPC Item DB API
- [x] **BAR-04**: Create inventory item from API data (name, size, brand, image, barcode, category)

### "What Can I Make?"

- [x] **MATCH-01**: Load recipes and compare ingredients to inventory
- [x] **MATCH-02**: Compute available count, total count, match percentage
- [x] **MATCH-03**: Sort by match percentage
- [x] **MATCH-04**: Show progress bars and missing ingredient badges
- [x] **MATCH-05**: Highlight expiring/expired items in results
- [x] **MATCH-06**: Surface recipes using urgent (expiring) items

### UI/UX Requirements

- [ ] **UI-01**: Tailwind CSS + DaisyUI styling
- [ ] **UI-02**: Card-based layouts
- [ ] **UI-03**: Server-rendered templates with selective JS enhancement
- [ ] **UI-04**: Responsive design (desktop-first with mobile-aware classes)
- [ ] **UI-05**: Modal behavior for interactions
- [ ] **UI-06**: JSON endpoints for in-page updates

### Verification Closure Gate

- [x] **REQ-VERIFICATION-GAP-ALL**: All phase verification artifacts exist and requirement coverage is backed by executable evidence

---

## v2 Requirements (Deferred)

- Recipe URL import from websites
- Drag-and-drop meal reordering
- Recipe filtering by cuisine/category on meal planner
- Light mode UI
- Multi-user household sharing
- Real-time collaboration
- Recipe sharing between households
- Nutrition tracking and goals
- Meal planning suggestions/AI recommendations

---

## Out of Scope

- **Drag-and-drop meal movement** — Complex, not essential for v1
- **Recipe filtering by cuisine on planner** — Can add later
- **Light mode UI** — Dark mode sufficient
- **Multi-user real-time** — Household-scoped for now
- **Social features** — No sharing, following, or community

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 through HOUSE-02 | 1 | Complete |
| REC-12, ING-03, ING-04, ING-06, INST-02, TAG-02 | 5 | Complete |
| REC-01 through REV-07 (except listed gap IDs) | 1 | Complete |
| MEAL-01 through LEFT-03 | 2 | Complete |
| COOK-01 through COOK-08 | 2 | Complete |
| SHOP-01 through SHOP-07 | 3 | Complete |
| INV-01 through INV-12 | 3 | Complete |
| BAR-01 through BAR-04 | 3 | Complete |
| MATCH-01 through MATCH-06 | 4 | Complete |
| UI-01 through UI-06 | All | Complete |
| REQ-VERIFICATION-GAP-ALL | 6 | Complete |

---

*Last updated: 2026-04-19*
