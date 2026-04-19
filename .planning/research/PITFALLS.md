# Domain Pitfalls: Meal Planner App

**Project:** Meal Planner App v2
**Domain:** Recipe management and meal planning
**Researched:** 2026-04-19

## Critical Pitfalls

Mistakes that cause rewrites or major issues in meal planner / recipe management projects.

---

### Pitfall 1: Ingredient Data as Dumb Strings

**What goes wrong:** Ingredients stored as plain text strings ("2 cups flour", "1 tsp salt"). No structure, no normalization, no queryability.

**Why it happens:** Early prototype simplicity. It's faster to dump ingredients as strings than model them properly. Every recipe has its own format — "flour", "all-purpose flour", "flour (all purpose)", "all purpose flour" are all different to the database.

**Consequences:**

- Cannot answer "what recipes can I make with what I have?"
- Cannot aggregate shopping lists reliably ("2 cups flour" + "1 cup flour" = 3 cups? Maybe? If units match?)
- Duplicate detection fails
- Recipe scaling breaks (user changes servings, quantities don't update)
- "What can I make?" feature is nearly impossible

**Prevention:**

1. **Normalize ingredients at schema level** — ingredients table with canonical names, separate from recipes
2. **Store quantities structured** — amount + unit + ingredient reference, not free text
3. **Build an ingredient alias table** — mapping common variations to canonical ingredients
4. **Index aggressively** — on ingredient names, tags, from day one

**Warning signs:**

- Recipe ingredients are a single text field or JSON array of strings
- Shopping list generation does string matching ("2 cups" vs "2 cup" misses matches)
- "What can I make?" requires fuzzy string matching

**Phase mapping:** This is a data modeling decision that affects Recipe CRUD, inventory linking, shopping list generation, and "what can I make" features. Address in Phase 1 (Recipe Foundation) or you'll face a major migration later.

---

### Pitfall 2: Solving the Wrong Problem — Recipe Storage vs. Decision Fatigue

**What goes wrong:** Building another recipe CRUD app (digital cookbook) when users need help deciding what to cook tonight.

**Why it happens:** Devs naturally focus on data modeling, schema, UI frameworks. But meal planning apps fail because they add friction rather than reducing it. Users have decision fatigue at 5pm, not at 10am when they're "supposed" to plan.

**Consequences:**

- App becomes a recipe graveyard — users add recipes, never return
- No competitive advantage over a Notes app or bookmarked websites
- Retention problem despite good feature completeness

**Prevention:**

1. **Lead with decision reduction** — not recipe storage
2. **Optimize for the 5pm moment** — what can I make RIGHT NOW with minimal friction?
3. **Build a meal rotation first** — 5-10 repeatable meals, not 500 recipes
4. **Reduce options in the moment** — "here are 3 suggestions" beats "browse 200 recipes"

**Warning signs:**

- First user story is "add recipe" instead of "decide what to cook"
- Success metric is "recipes stored" instead of "meals planned"
- No "quick decide" or "what can I make" feature in v1

**Phase mapping:** This is a product philosophy that should be validated in early phases. The app's core value is recipe organization, but the MVP should explicitly test decision reduction (e.g., ratings, favorites, "what can I make").

---

### Pitfall 3: Rigid Weekly Planning Without Flexibility

**What goes wrong:** Users plan 7 specific dinners for 7 days. Wednesday happens — meeting runs late, no energy, takeout wins. Plan is "ruined." Users abandon the app.

**Why it happens:** Traditional meal planning front-loads all decisions to Sunday. But Wednesday-you is not Sunday-you. Plans assume perfect execution, no energy variance, no schedule changes.

**Consequences:**

- User guilt and abandonment when plans fail
- All-or-nothing mentality ("I failed, starting over Monday")
- No backup meals for tired days
- Plan becomes irrelevant by Wednesday

**Prevention:**

1. **Plan for imperfection** — include 2-3 "backup meals" that are quick (>15 min) or leftovers
2. **3-day chunks, not 7-day rigid** — plan Mon-Wed, reassess before Thursday
3. **Easy swap mechanism** — if Wednesday changes, swap to something else without guilt
4. **Energy-aware matching** — filter recipes by available time/energy
5. **"Don't know" default** — suggest from rotation, not force a new decision

**Warning signs:**

- Meal planning UI requires 7 slots filled before saving
- No "leftovers" as valid meal type
- No quick/few-ingredients fallback options

**Phase mapping:** This is core to the Weekly Meal Planner feature. Should be designed into Phase 2 (Meal Planning) from the start.

---

### Pitfall 4: Shopping List Doesn't Know How People Shop

**What goes wrong:** Shopping list shows 15 ingredients in random order. User visits 3 stores because items aren't grouped by store/aisle. Can't reuse what's already in pantry.

**Why it happens:** Each recipe is designed in isolation. Aggregating all recipe ingredients = shopping list. No consideration for how people actually shop.

**Consequences:**

- Long, disorganized shopping lists
- Forgetting ingredients ("did I buy that?")
- Not accounting for pantry staples
- Multiple store visits
- Food waste from duplicate purchases

**Prevention:**

1. **Group by store section** — produce, dairy, meat, pantry, frozen
2. **Subtract pantry on-hand** — link to inventory, show only what's missing
3. **Deduplicate intelligently** — "2 cups flour" + "1 cup flour" = "3 cups flour" (if same unit)
4. **Check ingredient availability** — if user always has salt, don't list it
5. **Sorted by store layout** — group by aisle/section, not alphabetically

**Warning signs:**

- Shopping list is alphabetical (or recipe-order)
- No pantry/inventory integration
- No quantity aggregation across recipes

**Phase mapping:** This is core to Shopping List Generation. Must integrate with Inventory CRUD (Phase 3) to be useful.

---

### Pitfall 5: Technical Debt From Day One — No Indexes, Slow Search

**What goes wrong:** Search takes seconds when app has hundreds of recipes. N+1 queries everywhere. App works fine with 50 recipes, dies at 500.

**Why it happens:** Early-stage performance seems fine. Don't plan for scale. Don't add indexes because "we only have 20 recipes."

**Consequences:**

- At 500 recipes: 4+ second search
- Slow recipe lists on every page
- User leaves during cooking because "the app is too slow"
- Forced refactoring at 100K users kills velocity

**Prevention:**

1. **Add indexes early** — on recipe title, tags, rating, created_at
2. **Plan for 10x** — design for 2000 recipes when you have 200
3. **Query optimization in code review** — N+1 detection as standard
4. **Seed data from day one** — test with realistic volume, not empty DB

**Warning signs:**

- No database indexes on foreign keys or filterable fields
- Recipe listing uses multiple queries per item
- Performance untested above 100 recipes

**Phase mapping:** This is a Django implementation concern that spans all phases. Address in Recipe Foundation (Phase 1) with proper model indexes and query patterns.

---

### Pitfall 6: No User Feedback Loop — Recipes Never Improve

**What goes wrong:** User adds 100 recipes. Can't find the good ones. Can't remember which recipes were successes vs. failures. App doesn't learn preferences.

**Why it happens:** Rating system is an afterthought (or missing). No tracking of what users actually cooked. Recipes are static data, not improving knowledge.

**Consequences:**

- Users can't find their favorite recipes
- Repeat failures ("we didn't like that last time")
- No recommendation basis
- Recipe quality doesn't improve over time

**Prevention:**

1. **Cooked / not cooked tracking** — did they actually make it?
2. **Date-rated reviews** — rating can change over time (first try: 3 stars, after mastering: 5 stars)
3. **Notes on recipes** — "too salty," "add more garlic"
4. **Trending / recently cooked** — sort by actual usage, not just date added

**Warning signs:**

- No way to mark recipes as "cooked"
- Rating is a single-time snapshot
- No sorting by user preference (must know which ones they like)

**Phase mapping:** This ties to Recipe Rating System (Phase 1) and informs "what can I make" suggestions. Should be designed early.

---

### Pitfall 7: Over-Engineering v1 — Building Features Nobody Uses

**What goes wrong:** App launches with 30 features. Core usage (add/view recipes) is clunky. Advanced features have 3 users.

**Why it happens:** Feature creep. "While we're at it" syndrome. Competitor feature parity chase before product-market fit.

**Consequences:**

- High development cost, low return
- UI complexity overwhelms new users
- Core value (recipe organization) diluted
- Maintenance burden increases

**Prevention:**

1. **Define core value first** — recipe organization, NOT meal planning
2. **Ship recipe CRUD first** — get it excellent before adding meal planner
3. **Validate each feature** — does this help users organize or decide?
4. **Resist feature inflation** — if you add one, cut one

**Warning signs:**

- Feature list > 10 for MVP
- First version has "AI recipe suggestions" or "social sharing"
- Core flows (add recipe, find recipe) are complex

**Phase mapping:** This is a product philosophy. The requirements list in PROJECT.md already identifies out-of-scope items (drag-and-drop, multi-user). This vigilance must continue across all phases.

---

### Pitfall 8: Ignoring Real Household Dynamics

**What goes wrong:** Meal plan assumes everyone eats at the same time, same preferences, same schedule. Plan ignores that households are chaotic.

**Why it happens:** Individual-user mindset. Plan for "dinner at 6pm." Doesn't account for: partner home later, kids' activities, different dietary needs, one person cooks while other hates cooking.

**Consequences:**

- Plan doesn't match household reality
- One person becomes "meal manager" again
- No visibility for other household members
- Resentment ("why do I always have to decide?")

**Prevention:**

1. **Flexible meal times** — not "dinner at 6pm" but "dinner slot"
2. **Multiple meal types per day** — different people might want different things
3. **Dietary filters per user** — if someone is vegetarian, filter suggestions
4. **Shared visibility** — plan visible to whole household (future multi-user)
5. **"On-hand ideas"** feature — use what's already available, not perfect plan

**Warning signs:**

- Single meal per day slot only (what if someone eats early, someone eats late?)
- No meal type flexibility (lunch = sandwich, always)
- No way to handle "we have leftovers from Tuesday"

**Phase mapping:** Leftover-aware planning and multiple meals per type per day are already in requirements. Ensure implementation respects varied household dynamics in Phase 2.

---

## Moderate Pitfalls

These are important but less likely to cause complete rewrite.

### Pitfall 9: Missing Recipe Photos Are Invisible

**What goes wrong:** Recipe has no photo or broken image. Recipes without photos don't get selected. Quality recipes ignored because no visual.

**Prevention:** Require at least one photo. Auto-generate placeholder if missing. Use consistent photo dimensions.

### Pitfall 10: No Export / Portability

**What goes wrong:** User can't leave. Recipe data is trapped. No way to download recipes.

**Prevention:** Allow recipe export (JSON, CSV). Keep data portable from day one. Consider open formats.

### Pitfall 11: Complex Recipe Entry

**What goes wrong:** Adding a recipe takes 20 minutes. Too many fields, too much friction. Users don't add recipes, app stays empty.

**Prevention:** Minimum viable recipe entry (name + ingredients + instructions). Advanced fields optional. Copy-from-URL parsing.

---

## Phase-Specific Warnings

| Phase | Pitfall to Avoid | Prevention |
|-------|-----------------|------------|
| Phase 1: Recipe Foundation | Ingredient strings, no indexes, complex entry | Normalize ingredients from day one, add model indexes, seed with test data |
| Phase 2: Meal Planning | Rigid plans, no flexibility | Build in backup meals, 3-day chunks, energy-aware matching |
| Phase 3: Shopping List | Ignorant shopping list | Subtract pantry, group by store section, deduplicate |
| Phase 4: Inventory | Not integrated | Link to shopping lists, expiration warnings |
| Phase 5: Discovery | Wrong problem | Focus on "what can I make", not recipe volume |

---

## Sources

- Nextmealai (2026): "Why Most AI Meal Planner Apps Fail" — decision fatigue, too many options
- MealPlanned (2026): "Why Meal Planning Never Sticks" — rigid planning failure modes
- Plan to Eat (2026): "Why You Can't Stick to Your Plan" — flexibility, real schedule
- KeyMacro (2025): "Why Meal Planning Fails" — three common failure reasons
- DEV Community (2026): "Stop Building Ghost Town Apps" — recipe storage vs decision fatigue
- Fabrizio Farfan (2026): "How I Built a Recipe App" — AI generation + human curation lessons
- bheisler.github.io (2020): "Building a Recipe Manager — Data Integrity" — ingredient normalization, data redundancy
- bollenbach.ca (2025): "A Catastrophic Launch" — testing in production, gradual rollout
- roarsinc.com (2025): "We Built a Meal Planning App" — iteration, technical debt, scaling