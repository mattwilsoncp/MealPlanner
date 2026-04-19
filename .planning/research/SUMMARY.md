# Project Research Summary

**Project:** Meal Planner App v2
**Domain:** Recipe Management & Meal Planning Web Application
**Researched:** 2026-04-19
**Confidence:** HIGH

## Executive Summary

This is a Django-based meal planner application focused on recipe organization, weekly meal planning, and inventory tracking to reduce food waste. The research establishes that successful meal planner apps solve the **decision fatigue problem** — helping users answer "what's for dinner?" — not just storing recipes. The market segments into recipe managers (Paprika, Plan to Eat), weekly planners (Mealime, ReciMe), and AI planners (Eat This Much, Kitchendary), with this app positioned in the middle ground that users actually adopt long-term.

The recommended stack uses Django 6.0.3 with PostgreSQL 14+, Tailwind CSS 4.x + DaisyUI for styling, and Alpine.js for selective interactivity. Server-rendered templates are appropriate given the user preference for simplicity over SPA complexity. The critical architectural decision is normalizing ingredient data from day one — storing structured quantities and units rather than dumb strings — because this enables every downstream feature: shopping list aggregation, inventory matching, and "what can I make" queries.

The top risks are ingredient data quality (if treated as strings, feature ceiling is low), rigid meal planning that users abandon when schedules change, and building too many features before validating product-market fit. The research strongly recommends a phased approach: Recipe Foundation with proper data modeling first, then Meal Planning, then Shopping List, then Inventory, then Discovery features.

## Key Findings

### Recommended Stack

The stack is anchored in Django 6.0.3 (latest production release, Python 3.12+ support) with PostgreSQL 14+ (Django 5.2+ dropped PostgreSQL 13 support). psycopg 3.1+ provides the modern database adapter with connection pooling. The frontend uses Tailwind CSS 4.x and DaisyUI 5.x per user specification, with Alpine.js 3.x for minimal interactivity (modals, dropdowns) rather than full SPA frameworks. No API layer is needed initially — server-rendered templates per user preference.

**Core technologies:**
- **Django 6.0.3** — Web framework with built-in auth, sessions, ORM, media handling
- **PostgreSQL 14+** — Required for Django 5.2+ compatibility, full-text search ready
- **psycopg 3.1+** — Modern adapter with connection pooling, native Django support
- **Tailwind CSS 4.x + DaisyUI 5.x** — User-specified component library
- **Alpine.js 3.x** — Lightweight JS for selective enhancement

### Expected Features

**Must have (table stakes):**
- Recipe CRUD with photo upload — core function, every app has this
- Recipe search — users accumulate recipes, finding specific ones is essential
- Recipe ingredients with quantities — structured data (not free text)
- Weekly meal calendar view — 7 days, multiple meal types per day
- Multiple meals per slot — some days have lunch + dinner + leftovers
- Manual grocery list generation — pull ingredients from planned meals
- Shopping list item management — check off items, add extras
- User authentication — multi-tenancy with household scope

**Should have (differentiators):**
- Recipe URL import — major friction reduction, eliminates manual entry
- Inventory tracking with expiration dates — reduces food waste
- "What Can I Make?" matching — shows available meals from pantry
- Expiration-aware recipe suggestions — prioritize ingredients about to expire
- Recipe tags and rating — organize large collections, quality signals
- Side dishes and leftover-aware planning — how people actually cook

**Defer (v2+):**
- AI-generated meal plans — crowded market, Eat This Much wins here
- Nutrition tracking — MyFitnessPal owns this, out of scope
- Multi-user real-time collaboration — household scope sufficient initially
- Light mode UI — ship dark mode, evaluate after feedback

### Architecture Approach

The recommended architecture uses a layered pattern: Presentation (Django templates), Service (domain logic classes), Data Access (Django ORM models), and Persistence (PostgreSQL). Each domain component — Recipe Service, Meal Plan Service, Inventory Service, Shopping List Service — has clear boundaries and communicates through defined interfaces. Household scoping provides natural data isolation with all models including a foreign key to Household. The build order respects dependencies: Foundation (auth, household) → Recipe Core → Meal Planning → Inventory → Shopping List → Discovery features.

**Major components:**
1. **Recipe Service** — CRUD, search, tagging, rating, photo management
2. **Meal Plan Service** — Weekly planning, meal assignment, meal types
3. **Inventory Service** — Stock tracking, expiration monitoring
4. **Shopping List Service** — List generation from plans, ingredient aggregation
5. **Household Service** — User grouping, context management
6. **Recommendation Service** — "What Can I Make?" matching, expiration-aware suggestions

### Critical Pitfalls

1. **Ingredient data as dumb strings** — Must normalize from day one. Stored as "2 cups flour", no structure = can't aggregate shopping lists, can't answer "what can I make". Prevention: Separate Ingredient model, RecipeIngredient with amount/unit, ingredient alias table.

2. **Solving the wrong problem** — Building recipe storage when users need decision reduction. Users abandon apps that add friction at 5pm. Prevention: Lead with "what can I make", optimize for the dinner moment, not recipe accumulation.

3. **Rigid weekly planning** — 7 specific dinners, Wednesday happens, plan is "ruined". Prevention: Backup meals, 3-day chunks not 7-day rigid, easy swap mechanism, "don't know" default.

4. **Shopping list doesn't know how people shop** — Random order, no pantry subtraction, no store grouping. Prevention: Group by store section, subtract pantry on-hand, deduplicate intelligently.

5. **Technical debt from day one** — No indexes, N+1 queries, dies at 500 recipes. Prevention: Add indexes early, seed with realistic volume, query optimization as standard.

## Implications for Roadmap

Based on research, the following phase structure emerges:

### Phase 1: Recipe Foundation
**Rationale:** Recipes are the foundation all other features build on. Critical to get ingredient data modeling correct from the start — fixing this later requires major migration.
**Delivers:** User auth, household model, Recipe CRUD with photo upload, structured ingredient storage (amount + unit + ingredient reference), recipe search, tags/categories, ratings, basic indexes.
**Addresses:** All table stakes features except meal planner and shopping list.
**Avoids:** Pitfall #1 (ingredient strings), Pitfall #5 (technical debt).

### Phase 2: Meal Planning
**Rationale:** The core value proposition — helping users decide what to cook. Depends on recipes existing.
**Delivers:** Weekly meal calendar (7 days × 4 meal types), meal assignment, multiple meals per slot, cooking reconciliation, meal ratings.
**Addresses:** Weekly meal planner, multiple meals per slot, leftover tracking.
**Avoids:** Pitfall #3 (rigid planning) — build in backup meals and flexible reassignment.

### Phase 3: Shopping List Generation
**Rationale:** Natural flow: plan meals → know what ingredients needed → generate list. Depends on meal planner and structured ingredients.
**Delivers:** Manual grocery list generation from planned meals, ingredient aggregation/deduplication, shopping list management (add/remove/checkoff).
**Addresses:** Grocery list table stakes.
**Avoids:** Pitfall #4 (shopping list ignorance) — implement pantry subtraction and store grouping.

### Phase 4: Inventory Tracking
**Rationale:** Complements shopping list by tracking what users already have. Enables the "reduce food waste" value proposition.
**Delivers:** Inventory CRUD, category/location tracking, expiration date tracking, ingredient linking to recipes.
**Addresses:** Inventory tracking, expiration warnings.
**Avoids:** Pitfall #4 continuation — must integrate with shopping list.

### Phase 5: Discovery Features
**Rationale:** The differentiators that set this app apart. Depends on inventory and recipe ingredients being properly linked.
**Delivers:** "What Can I Make?" matching, expiration-aware recipe suggestions, recipe URL import.
**Addresses:** Differentiator features from research.
**Avoids:** Pitfall #2 (wrong problem) — these features solve decision fatigue.

### Phase Ordering Rationale

- **Dependencies drive order:** Recipe CRUD → Meal Planning → Shopping List → Inventory → Discovery. Each builds on the previous.
- **Data quality first:** Ingredient normalization in Phase 1 enables all downstream features. Wrong data model = rewrite later.
- **Value progression:** Each phase delivers tangible value — recipes usable (1), decisions reduced (2), shopping streamlined (3), waste reduced (4), discovery enabled (5).
- **Pitfall avoidance built in:** Each phase explicitly addresses identified pitfalls.

### Research Flags

**Phases likely needing deeper research:**
- **Phase 2:** Meal planner flexibility features — research energy-aware matching and backup meal patterns
- **Phase 5:** Recipe URL import — requires HTML parsing and fallback patterns for JS-rendered content

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** Django auth, Recipe CRUD — well-documented, standard patterns
- **Phase 3:** Shopping list generation — established aggregations pattern
- **Phase 4:** Inventory tracking — typical CRUD with date handling

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Django 6.0.3 latest release, PostgreSQL 14+ required, psycopg3 standard |
| Features | MEDIUM | Table stakes verified across competitors, differentiators inferred from positioning |
| Architecture | HIGH | Matches established Django patterns, multiple production references |
| Pitfalls | HIGH | Verified across multiple sources on failure modes |

**Overall confidence:** HIGH

### Gaps to Address

- **Recipe URL import complexity:** Research covered at high level but actual HTML parsing patterns need exploration during Phase 5 planning
- **Grocery deduplication edge cases:** Unit conversion ("2 cups" + "1 cup" = "3 cups") needs specification — may need research
- **Inventory expiration notifications:** Notification channel (email? push? in-app?) not specified — defer to Phase 4

## Sources

### Primary (HIGH confidence)
- Django 6.0.3 release notes — https://www.djangoproject.com/download
- psycopg 3.3 release — https://www.psycopg.org/articles/2025/12/01/psycopg-33-released/
- Tailwind CSS + DaisyUI 5 documentation — https://v5.daisyui.com/docs/install

### Secondary (MEDIUM confidence)
- Meal planner competitive analysis — Eat This Much, Mealime, Paprika, ReciMe, AnyList product analysis
- Tandoor Recipes (8K stars) — https://github.com/TandoorRecipes/recipes — production Django meal planning reference
- Industry analysis — Fortune, FoodsPlans, What's for Dinner comparisons (2026)

### Tertiary (LOW confidence)
- Recipe URL import patterns — may need validation during Phase 5
- Exact grocery deduplication algorithms — unit conversion edge cases need specification

---
*Research completed: 2026-04-19*
*Ready for roadmap: yes*