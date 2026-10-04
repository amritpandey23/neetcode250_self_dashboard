# Active Context

## Current focus
Dark/light theme toggle shipped with deep CSS token coverage.

## Recent decisions
- Theme via `html[data-theme="light|dark"]`, persisted in `localStorage` (`neetcode-theme`)
- FOUC prevented by early head script; toggle in header (sun/moon)
- Nearly all UI colors go through CSS variables (surfaces, hovers, toasts, AI chat, MD editor, roadmap)
- Charts and Mermaid re-theme on `themechange`
- Problem LeetCode URL editable on problem detail; seed preserves customized URLs
- Dashboard shows Attempted + Solved history lists (newest date first)
- `ActivityLog` records core actions; dashboard Activity log panel (newest first)
- Problem↔entry links via `ProblemEntryLink`; Spaces + AI Coach remain as before

## Next steps
- Optional: surface linked entries in AI Coach context
- Optional: export notes / review due dates
