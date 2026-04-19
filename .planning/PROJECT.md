# Meal Planner App v2

## What This Is

A Django-based meal planning web application that helps users organize recipes, plan weekly meals, manage inventory, and generate shopping lists. The app emphasizes recipe organization as its core value, with meal planning and inventory management as supporting features.

## Core Value

**Recipe organization** — the app must excel at helping users store, find, and manage their recipes. Every feature should enhance, not distract from, this primary goal.

## Context

### Problem

Users struggle with:
- Disorganized recipe collections
- Decision fatigue at meal time
- Food waste from unused ingredients
- Forgetting what they have in inventory

### Who It's For

- Meal preppers who plan and batch-cook meals for the week
- Home cooks wanting to organize recipes and reduce waste
- Anyone wanting to streamline their weekly meal planning

### Tech Stack

- Django web application with server-rendered templates
- PostgreSQL database for domain data
- Django auth, sessions, messages, media uploads
- Tailwind CSS + DaisyUI for styling
- JavaScript for selective enhancement (modals, JSON endpoints)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Django + Postgres | User-provided spec - mature, well-tested stack | — Pending |
| Server-rendered templates | User preference for selective JS enhancement | — Pending |
| Tailwind + DaisyUI | User-provided spec - rapid UI development | — Pending |
| User-scoped via households | Allows future multi-user household sharing | — Pending |

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] User authentication (login/logout/signup)
- [ ] Household context management
- [ ] Recipe CRUD (create, read, update, delete)
- [ ] Recipe search and filtering
- [ ] Recipe sorting (rating, date)
- [ ] Recipe rating system (1-5 scale with notes)
- [ ] Recipe tags and categorization
- [ ] Recipe photo upload
- [ ] Recipe review workflow
- [ ] Ingredient-to-inventory linking
- [ ] Weekly meal planner
- [ ] Meal types (breakfast, lunch, dinner, snack)
- [ ] Multiple meals per type per day
- [ ] Custom meal notes
- [ ] Meal rating
- [ ] On-hand ideas feature
- [ ] Leftover-aware planning
- [ ] Side dishes for meals
- [ ] Cooking reconciliation
- [ ] Shopping list generation
- [ ] Shopping list management
- [ ] Inventory CRUD
- [ ] Inventory categorization and location
- [ ] Inventory expiration tracking
- [ ] Barcode scanning and lookup
- [ ] "What Can I Make?" recipe matching
- [ ] Expiration-aware recipe suggestions

### Out of Scope

- [ ] Drag-and-drop meal movement between days — complex, not essential
- [ ] Recipe filtering by cuisine/category on meal planner — can add later
- [ ] Light mode UI — dark mode sufficient for v1
- [ ] Multi-user real-time collaboration — household-scoped for now

---

*Last updated: 2026-04-19 after initialization*