# Architecture Patterns for Meal Planner Applications

**Domain:** Recipe Management & Meal Planning Web Application  
**Framework:** Django (Python) with Server-Rendered Templates  
**Researched:** 2026-04-19  
**Confidence:** HIGH

## Executive Summary

Meal planner applications follow a consistent architectural pattern centered on four core domain areas: recipe management, meal planning, inventory tracking, and shopping list generation. These systems require careful attention to data relationships between recipes and ingredients, as well as the flow of information from planned meals through inventory consumption to shopping lists.

For this Django-based application, the recommended architecture uses a layered approach with clear component boundaries: the presentation layer handles UI via Django templates, the service layer encapsulates business logic, and the data layer manages persistence through Django models. The household scope provides natural data isolation while supporting future multi-user scenarios.

## Recommended Architecture

### Layered Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Recipes   │  │Meal Planner │  │  Inventory  │  Shopping   │
│  │   Views     │  │   Views     │  │   Views     │    Lists    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    Views    │
└─────────┼────────────────┼────────────────┼────────────┬───────┘
          │                │                │            │
          ▼                ▼                ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Recipe    │  │    Meal     │  │  Inventory  │  Shopping   │
│  │   Service   │  │   Service   │  │   Service   │   Service   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    Service   │
└─────────┼────────────────┼────────────────┼────────────┬───────┘
          │                │                │            │
          ▼                ▼                ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA ACCESS LAYER                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Django ORM (Models)                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE LAYER                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              PostgreSQL Database                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Recipe Service** | Recipe CRUD, search, tagging, rating, photo management | Recipe Model, Ingredient Model, Tag Model |
| **Meal Plan Service** | Weekly planning, meal assignment, meal types, leftovers | Recipe Model, MealPlan Model, MealEntry Model |
| **Inventory Service** | Stock tracking, expiration monitoring, consumption | Ingredient Model, InventoryItem Model |
| **Shopping List Service** | List generation from plans, item aggregation, checkoff | Inventory Model, ShoppingList Model, ShoppingItem Model |
| **Household Service** | User grouping, context management, sharing | User Model, Household Model, HouseholdMember Model |
| **Recommendation Service** | "What Can I Make?" matching, expiration-aware suggestions | Recipe, Inventory, Ingredient Models |

### Data Flow Patterns

**Recipe-to-Meal Flow:**
```
1. User creates/imports recipe with ingredients
2. Recipe Service validates and stores recipe
3. User assigns recipe to meal slot in Meal Planner
4. Meal Plan Service creates meal entry
5. Shopping List Service aggregates ingredients from planned meals
6. Inventory Service subtracts on-hand items
7. User generates shopping list with net requirements
```

**Inventory-to-Recipe Matching Flow:**
```
1. User updates inventory with on-hand ingredients
2. Inventory Service stores current stock levels
3. Recommendation Service queries recipes matching available ingredients
4. System surfaces recipes user can make "now"
5. User selects recipe, system marks ingredients as "to acquire"
```

### Build Order and Dependencies

The following order respects component dependencies and enables incremental validation:

```
1. FOUNDATION
   ├── User Authentication (Django auth)
   ├── Household Model & Management
   └── Base template & navigation
   
2. RECIPE CORE (Phase 1)
   ├── Recipe CRUD
   ├── Ingredient linking
   ├── Photo upload
   ├── Search & filtering
   └── Tag/category system
   └── Rating system
   
3. MEAL PLANNING (Phase 2)
   ├── Weekly planner UI
   ├── Meal types (breakfast/lunch/dinner/snack)
   ├── Meal assignment to days
   └── Meal notes & ratings
   
4. INVENTORY (Phase 3)
   ├── Inventory CRUD
   ├── Category/location tracking
   ├── Expiration date tracking
   └── Ingredient linking to recipes
   
5. SHOPPING LIST (Phase 4)
   ├── List generation from meal plan
   ├── Ingredient aggregation/deduplication
   ├── Inventory subtraction
   └── List management (add/remove/checkoff)
   
6. ADVANCED (Phase 5)
   ├── "What Can I Make?" matching
   ├── Expiration-aware suggestions
   ├── Side dishes
   ├── Cooking reconciliation
   └── Barcode scanning
```

## Key Architectural Decisions

### Service Layer Pattern

For a Django application of this scope, a service layer provides clean separation between view logic and business rules. Services are implemented as Python classes or modules that encapsulate domain operations:

```python
# services/recipe_service.py
class RecipeService:
    def create_recipe(self, household, data, user):
        # Validation logic
        # Business rule enforcement
        # Model creation
        
    def search_recipes(self, household, query, filters):
        # Query building
        # Filter application
        # Return structured results
```

This pattern keeps views thin and testable while providing a clear API for the domain logic.

### Household-Scoped Data Isolation

All domain models include a foreign key to `Household`, ensuring data remains isolated:

```python
class Recipe(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE)
    # ... other fields
```

Views and services always filter by `request.user.household`, preventing data leakage between households.

### Ingredient Normalization

Ingredients require careful handling due to naming variations ("tomato" vs "tomatoes", "2 cups" vs "1 pint"). The architecture supports:

- Base ingredient entities (normalized names)
- Recipe-specific ingredient references with quantity/unit
- Unit conversion utilities for aggregation
- Ingredient matching for inventory and recommendations

## Data Model Relationships

```
Household
├── User (multiple)
├── Recipe (many)
│   ├── RecipeIngredient (many) ─── Ingredient
│   ├── RecipeTag (many) ────────── Tag
│   └── RecipeRating (many)
├── MealPlan (one per week/household)
│   └── MealEntry (many per day)
│       └── Recipe (reference)
├── InventoryItem (many)
│   └── Ingredient
└── ShoppingList (many)
    └── ShoppingItem (many)
```

## Scalability Considerations

| Aspect | Current (MVP) | Growth Phase | Enterprise |
|--------|---------------|--------------|------------|
| **Database** | Single PostgreSQL instance | Read replicas | Sharding by household |
| **File Storage** | Local media folder | S3/CDN | Distributed object storage |
| **Caching** | None required | Django cache framework | Redis for session/cache |
| **Search** | Django ORM filtering | PostgreSQL full-text | Elasticsearch for scale |

For MVP, PostgreSQL with Django ORM provides adequate performance for typical household collections (100s-1000s of recipes). Full-text search can be added via PostgreSQL's built-in capabilities before needing dedicated search infrastructure.

## Common Pitfalls to Avoid

### Pitfall 1: Ingredient Data Model Confusion

**Problem:** Storing ingredients as simple text fields in recipes, making aggregation impossible.

**Prevention:** Separate ingredient normalization:
- `Ingredient` model (normalized reference data)
- `RecipeIngredient` model (recipe-specific quantity/unit)
- Match ingredients during import and allow manual correction.

### Pitfall 2: Tight Coupling Between Meal Plan and Shopping List

**Problem:** Shopping lists directly tied to specific meal plans, preventing independent management.

**Prevention:** Use intermediate "shopping requirements" that can be:
- Generated from meal plans
- Manually added
- Modified independently of source plan

### Pitfall 3: Missing Household Scope in Queries

**Problem:** Accidentally exposing recipes between households due to missing filters.

**Prevention:** 
- Always filter queries by `request.user.household`
- Use custom querysets with automatic household filtering
- Add database-level constraints as failsafe

### Pitfall 4: Over-Engineering for "Future Features"

**Problem:** Building complex multi-user collaboration before validating single-household product-market fit.

**Prevention:** Design models to support household grouping but implement single-user-first workflows initially.

## Sources

- **Tandoor Recipes** (https://github.com/TandoorRecipes/recipes) - Large-scale Django/Vue meal planning application, 8K+ stars, active development
- **Mealie** (https://github.com/mealie-recipes/mealie) - Modern self-hosted meal planner with Vue/FastAPI, PostgreSQL backend
- **mealCurator** (https://github.com/jtweeder/mealcurator) - Production Django meal planning application
- **What's for Dinner** architecture documentation - Enterprise-grade meal planning platform patterns
- **Django Documentation** - ORM patterns, authentication, views

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Component boundaries | HIGH | Matches established Django patterns and domain requirements |
| Data flow patterns | HIGH | Based on multiple production meal planner implementations |
| Build order | HIGH | Follows logical dependency chains (recipes → planning → inventory → shopping) |
| Scalability | MEDIUM | Recommendations appropriate for MVP; may need adjustment based on usage patterns |

## Gaps to Address During Implementation

- **Barcode scanning integration** - May require third-party API research in later phase
- **Recipe import from URLs** - Requires web scraping pattern decisions
- **Real-time collaboration** - Out of scope for MVP but should not block future addition
