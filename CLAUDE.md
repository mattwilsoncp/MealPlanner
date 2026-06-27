<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **MealPlanner** (2419 symbols, 3556 relationships, 83 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/MealPlanner/context` | Codebase overview, check index freshness |
| `gitnexus://repo/MealPlanner/clusters` | All functional areas |
| `gitnexus://repo/MealPlanner/processes` | All execution flows |
| `gitnexus://repo/MealPlanner/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

## Design System

The UI is an **editorial monochrome** aesthetic — coolors light-neutral ramp
+ wide-tracked geometric display type. Full philosophy in `DESIGN.md`; this is
the quick reference for agents editing templates.

### Color tokens (defined in `templates/base.html` `:root`)
- **Surface**: `--bg-page: #f8f9fa`, `--bg-card: #ffffff`, `--bg-elevated: #e9ecef`
- **Borders**: `--border-subtle: #dee2e6`, `--border-medium: #ced4da`, `--border-strong: #adb5bd`
- **Text**: `--text-primary: #212529`, `--text-secondary: #495057`, `--text-muted: #6c757d`
- **No accent colors** — keep monochrome. Legacy aliases (`--brand-green`,
  `--accent-coral`, semantic `success/warning/error-bg`) all remap to the
  neutral ramp for backward compatibility; prefer explicit tokens in new code.

### Typography
- **Display / headlines**: `var(--font-display)` (Space Grotesk), weight 500, line-height 1.03
- **Body**: `var(--font-primary)` (DM Sans), weight 400, line-height 1.45
- **Mono / labels**: `var(--font-mono)` (JetBrains Mono), uppercase, `letter-spacing: 0.05–0.18em`
- **Hero scale**: `.vp-display` → `clamp(40px,6vw,80px)` weight 500 line-height 1.00; `.vp-display-secondary` → `clamp(28px,4vw,56px)` weight 400 line-height 1.05
- **Eyebrow**: `<span class="vp-eyebrow">` mono micro-label above every primary headline

### Component classes (`.vp-*` in `templates/base.html`)
| Class | Purpose |
|-------|---------|
| `.vp-shell` | Page wrapper (max-width 1280px, side padding) |
| `.vp-hero` / `.vp-hero-inner` | Top section with eyebrow + display headline + subhead |
| `.vp-section` / `.vp-section-header` / `.vp-section-header-title` | Section spacing + headers |
| `.vp-card` / `.vp-card-tight` | Bordered panels for forms/tables |
| `.vp-table` | Tabular data with mono column headers, hairline rows, hover row |
| `.vp-input` | Underline-only form field; border thickens to `--text-primary` on focus |
| `.vp-btn-primary` | Solid `#212529` rectangle inverts on hover |
| `.vp-btn-ghost` | 1px `#ced4da` outline goes solid on hover |
| `.vp-label-mono` | Small mono uppercase form label |
| `.vp-divider` | Hairline horizontal rule |

### Page composition
Every primary page follows **`vp-hero` → `vp-section` containing `vp-card[-tight]`**. Form pages pair the hero with a right-side `vp-card` form panel so hero copy lives in the left column. Backwards-compatible aliases (`.btn-primary`, `.card-dark`, `.input-dark`, `.label-dark`, `.link-green`) are remapped to the new monochrome tokens, so older template fragments still render correctly without rewrites — prefer the explicit `.vp-*` classes in new code.

### Conventions
- **No shadows** — depth comes from border contrast (`#dee2e6 → #adb5bd`).
- **Border radius 4–6px** for cards/buttons. No pills, no 16px+ radii.
- **Modals** use native `<dialog>` + `x-show`, not custom DOM overlays.
- **Hardcoded home cards**: `meal_planner/templates/index.html` references six
  explicit `01`–`06` anchors (no `home_cards` context variable; the route
  serves `TemplateView.as_view(template_name="index.html")`).
- **Atomic recipe-route edits**: recipe_detail.html must render the full-word
  `Protein {{ …|floatformat:2 }}g`, `Carbs`, `Fat` plus the literal
  `Nutrition unavailable for this ingredient.` — `IngredientLinksAndNutritionTests`
  asserts on those exact strings.
