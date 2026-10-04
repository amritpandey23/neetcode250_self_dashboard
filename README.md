# NeetCode 250 Self Dashboard

Personal Flask dashboard to track NeetCode 250 progress, status, and notes. Data comes from `neetcode_250_complete.json` and is stored in SQLite.

## Features

- Register / login / logout (password hashing via Werkzeug)
- 250 problems seeded from JSON on first run
- Per-problem status: Todo, Attempted, Done
- Notes per problem
- Filters: search, category, difficulty, status
- Progress summary and category bars
- **Spaces**: long-form private documents (categories → sections → markdown entries with LaTeX, Mermaid, code highlighting, YouTube embeds)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # if you don't already have .env
# edit .env and set GEMINI_API_KEY for AI chat
python run.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001), register an account, and start tracking.

> On macOS, port 5000 is often used by AirPlay Receiver and returns `HTTP 403`. This app uses **5001** instead.

## Project layout

```
app/
  auth.py          # login / register / logout
  models.py        # User, Problem, Progress, Space/docs models
  routes.py        # dashboard + problem detail
  docs.py          # Spaces / categories / sections / entries
  seed.py          # load JSON into SQLite
  templates/
  static/css/
config.py
run.py
neetcode_250_complete.json
```

### Spaces

Open **Spaces** in the nav to create topic workspaces (e.g. “Data Structures & Algorithms”). Each space has a category sidebar; categories hold sections and markdown entries. Entries support the same rich editor as problem notes, plus Mermaid diagrams and YouTube embeds (` ```youtube ` fences or bare YouTube URLs).

SQLite DB path: `instance/neetcode.db`

Set `SECRET_KEY` in the environment before deploying anywhere beyond local use.

## AI coach (Gemini)

Each problem page has a right-side AI chat that uses your live status and notes as context.

Locally, set values in `.env` (loaded automatically via `python-dotenv`):

```bash
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash
```

On EC2, add those to `/etc/neetcode250/env` and restart:

```bash
sudo systemctl restart neetcode250
```
