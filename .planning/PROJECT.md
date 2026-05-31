# Meal Planner App v2

## What This Is

A Django-based meal planning web application that helps users organize recipes, plan weekly meals, manage inventory, and generate shopping lists. The app emphasizes recipe organization as its core value, with meal planning and inventory management as supporting features.

## Current State

- **Milestone:** v1.2 (AI Meal Suggestions)
- **Status:** Defining requirements
- **Previous:** v1.1 shipped (2026-04-22)

## Core Value

**Recipe organization** — the app must excel at helping users store, find, and manage their recipes. Every feature should enhance, not distract from, this primary goal.

## Current Milestone: v1.2 AI Meal Suggestions

**Goal:** Generate creative weekly meal plans using free models from opencode.ai based on user preferences and available inventory.

**Target features:**
- User preference configuration (dietary restrictions, cuisines, cooking effort)
- AI-powered weekly meal generation via opencode.ai API (OpenAI-compatible)
- Novel AI-generated recipes based on inventory + preferences
- Generated plan integrates with existing weekly planner UI (side dishes, leftovers)
- Shopping list generation for missing ingredients
- Accept / reject / regenerate individual days

## Context

### Problem

Users struggle with:
- Disorganized recipe collections
- Decision fatigue at meal time
- Food waste from unused ingredients
- Forgetting what they have in inventory
- Manual recipe entry is time-consuming

### Who It's For

- Meal preppers who plan and batch-cook meals for the week
- Home cooks wanting to organize recipes and reduce waste
- Anyone wanting to streamline their weekly meal planning
- YouTube recipe viewers who want to save cooking videos as recipes

### Tech Stack

- Django web application with server-rendered templates
- PostgreSQL database for domain data
- Django auth, sessions, messages, media uploads
- Tailwind CSS + DaisyUI for styling
- JavaScript for selective enhancement (modals, JSON endpoints)
- YouTube Data API / oEmbed for metadata fetching
- NLP library for ingredient parsing

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Django + Postgres | User-provided spec - mature, well-tested stack | ✓ Confirmed in v1 |
| Server-rendered templates | User preference for selective JS enhancement | ✓ Confirmed in v1 |
| Tailwind + DaisyUI | User-provided spec - rapid UI development | ✓ Confirmed in v1 |
| User-scoped via households | Allows future multi-user household sharing | ✓ Confirmed in v1 |
| YouTube import | User-requested v1.1 feature | ✓ Confirmed in v1.1 |
| AI meal suggestions | User-requested v1.2 feature | New in v1.2 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-05-31 — v1.2 milestone started*