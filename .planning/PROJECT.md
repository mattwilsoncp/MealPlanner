# Meal Planner App v2

## What This Is

A Django-based meal planning web application that helps users organize recipes, plan weekly meals, manage inventory, and generate shopping lists. The app emphasizes recipe organization as its core value, with meal planning and inventory management as supporting features.

## Current State

- **Milestone:** v1 shipped (2026-04-19)
- **Status:** Production-ready MVP with recipe, planning, inventory, shopping, barcode, and discovery flows delivered
- **Verification:** Phase verification artifacts exist for phases 1-4 and milestone audit is `ready_to_close`

## Core Value

**Recipe organization** — the app must excel at helping users store, find, and manage their recipes. Every feature should enhance, not distract from, this primary goal.

## Next Milestone Goals

- Improve recipe ingestion (URL import and normalization)
- Expand planning UX (drag/drop and planner filtering)
- Add collaborative household capabilities
- Introduce nutrition-goal tracking and suggestion workflows

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
| Django + Postgres | User-provided spec - mature, well-tested stack | ✓ Confirmed in v1 |
| Server-rendered templates | User preference for selective JS enhancement | ✓ Confirmed in v1 |
| Tailwind + DaisyUI | User-provided spec - rapid UI development | ✓ Confirmed in v1 |
| User-scoped via households | Allows future multi-user household sharing | ✓ Confirmed in v1 |

## Requirements

v1 requirements were archived to `.planning/milestones/v1-REQUIREMENTS.md`.

Use `/gsd-new-milestone` to define fresh active requirements for the next milestone.

---

*Last updated: 2026-04-19 after v1 milestone closure*
