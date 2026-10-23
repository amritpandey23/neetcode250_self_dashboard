# System Patterns

## Architecture
- Flask application factory (`create_app`)
- Blueprints: `auth`, `main`, `docs` (Spaces)
- Flask-SQLAlchemy models + Flask-Login sessions
- Jinja templates + static CSS/JS (shared `markdown-editor.js`)

## Data model
- `User` — username + password hash + optional `email` + `email_challenge_enabled`
- `Problem` — canonical NeetCode 250 metadata (shared)
- `Progress` — per-user status/notes (`unique user_id + problem_id`)
- Spaces: `Space` → `DocCategory` → `DocSection?` → `DocEntry` (user-owned)
- `ProblemEntryLink` — per-user problem↔entry links (`unique user_id + problem_id + entry_id`)
- `ActivityLog` — per-user chronological action feed (`action`, `summary`, optional `href`)
- `DailyChallenge` — one shared problem per server-local date (`unique challenge_date`)

## Critical paths
1. Startup → create tables → seed problems from JSON → start email-challenge scheduler thread
2. Login → dashboard with joins via progress map in Python
3. Problem detail POST → upsert Progress row
4. Problem link/unlink entry → upsert/delete `ProblemEntryLink` (ownership via Space.user_id)
5. Settings → save email/opt-in; optional immediate test send via `email_challenge.send_challenge_for_user`
6. Daily scheduler → `question_of_the_day()` (one server-local-day problem) → opted-in users at their local send time → SMTP or console log
7. Dashboard → same `question_of_the_day()` for every logged-in user
8. AI Coach chat → client sends selected Gemini model → `resolve_model` validates against Models API list → `generateContent`
9. Contests page → cached LeetCode GraphQL + CodeChef JSON + Codeforces API feeds → normalized upcoming contests → server-built Sunday-first month calendar (desktop grid, mobile agenda) in the user's timezone

## Patterns
- Progress map built once per dashboard request (`problem_id → Progress`)
- Missing progress treated as `todo`
- Solved count = `done` only
- Spaces ownership always checked through Space.user_id
- Linked entry options exclude already-linked entries for that problem
- Theme: `data-theme` on `<html>`, CSS variables for all surfaces/ink/accents; JS `themechange` for Chart.js + Mermaid
- Schema migrations via `ensure_schema()` `PRAGMA` + `ALTER TABLE` (users + progress)
- Email delivery abstracted in `app/email_challenge.py` (shared by Settings test + daily job)
- Gemini model list cached in-process (`list_chat_models`, 1h TTL); UI selection persisted in localStorage
- Question of the day is one `DailyChallenge` row per server-local date; emails and the dashboard both read it
- Contest sources cached per platform (1h TTL), normalized to a common shape (`platform`, `start`, `end`, `url`, `calendar`); a source failure degrades gracefully
- Contest calendar is built server-side (Sunday-first weeks + flat agenda); dates/times are displayed in the user's `email_challenge_timezone` (`user_timezone()`), defaulting to UTC
- Dashboard uses a 75% main column + 25% right rail: progress chart + activity lists on the left, contest mini-calendar in the rail
- The top hero is a 3-column grid: NeetCode 250 progress + merged Easy/Medium/Hard donut (left), streak calendar (middle), continue-learning card (right); it stacks to a single column below 900px
- Streak data is derived from `Progress` (`completed_at`, `last_practiced_at`, `updated_at`) plus `ActivityLog` status/practice rows; solved days win over attempted days, and both count toward current/best streaks
