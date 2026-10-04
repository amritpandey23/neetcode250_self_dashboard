# System Patterns

## Architecture
- Flask application factory (`create_app`)
- Blueprints: `auth`, `main`
- Flask-SQLAlchemy models + Flask-Login sessions
- Jinja templates + static CSS

## Data model
- `User` — username + password hash
- `Problem` — canonical NeetCode 250 metadata (shared)
- `Progress` — per-user status/notes (`unique user_id + problem_id`)

## Critical paths
1. Startup → create tables → seed problems from JSON
2. Login → dashboard with joins via progress map in Python
3. Problem detail POST → upsert Progress row

## Patterns
- Progress map built once per dashboard request (`problem_id → Progress`)
- Missing progress treated as `todo`
- Solved count = `done` only
