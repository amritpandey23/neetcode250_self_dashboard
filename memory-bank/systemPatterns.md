# System Patterns

## Architecture
- Flask application factory (`create_app`)
- Blueprints: `auth`, `main`, `docs` (Spaces)
- Flask-SQLAlchemy models + Flask-Login sessions
- Jinja templates + static CSS/JS (shared `markdown-editor.js`)

## Data model
- `User` — username + password hash
- `Problem` — canonical NeetCode 250 metadata (shared)
- `Progress` — per-user status/notes (`unique user_id + problem_id`)
- Spaces: `Space` → `DocCategory` → `DocSection?` → `DocEntry` (user-owned)
- `ProblemEntryLink` — per-user problem↔entry links (`unique user_id + problem_id + entry_id`)
- `ActivityLog` — per-user chronological action feed (`action`, `summary`, optional `href`)

## Critical paths
1. Startup → create tables → seed problems from JSON
2. Login → dashboard with joins via progress map in Python
3. Problem detail POST → upsert Progress row
4. Problem link/unlink entry → upsert/delete `ProblemEntryLink` (ownership via Space.user_id)

## Patterns
- Progress map built once per dashboard request (`problem_id → Progress`)
- Missing progress treated as `todo`
- Solved count = `done` only
- Spaces ownership always checked through Space.user_id
- Linked entry options exclude already-linked entries for that problem
- Theme: `data-theme` on `<html>`, CSS variables for all surfaces/ink/accents; JS `themechange` for Chart.js + Mermaid
