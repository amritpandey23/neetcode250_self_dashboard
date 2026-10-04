# Active Context

## Current focus
UI/UX refinement for Spaces (hub/category/document) and auth (login/register), aligned with Dashboard/Problems polish.

## Recent decisions
- Hero emphasizes NeetCode 250 progress + Continue Learning (from existing progress data); greeting de-emphasized
- Stats as a single segmented row: Problems / Attempted / Solved (no fake metrics)
- Less card nesting: hero/filters are sections; problem list is the primary bordered surface
- Filters autosubmit on change/search debounce; Apply removed; + Add Question is primary CTA
- Sidebar progress bars only when `done > 0`; no invented category taxonomy groups
- Problem rows: star → title → LC → difficulty (metadata) → status (user state) → chevron; whole-row click/keyboard
- Roadmap: quieter dotted grid, larger nodes, completed/current/upcoming states, YOU ARE HERE from progress, zoom controls kept
- Type scale via CSS tokens (`--title-size`, `--section-size`, `--body-size`, `--meta-size`, `--label-size`)
- Theme via `html[data-theme]`, persisted in `localStorage`

## Next steps
- Optional: surface linked Spaces entries in AI Coach context
- Optional: export notes / review due dates
