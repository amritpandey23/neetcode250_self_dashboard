from sqlalchemy import text

from app import db

AGING_WEEKS = 2
AGING_MAX_SOLVES = 5


def ensure_schema():
    """Apply lightweight SQLite migrations for columns added after first run."""
    with db.engine.begin() as conn:
        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(progress)"))
        }
        if "bookmarked" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE progress ADD COLUMN bookmarked BOOLEAN "
                    "NOT NULL DEFAULT 0"
                )
            )
        if "solve_count" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE progress ADD COLUMN solve_count INTEGER "
                    "NOT NULL DEFAULT 0"
                )
            )
        if "last_practiced_at" not in columns:
            conn.execute(
                text("ALTER TABLE progress ADD COLUMN last_practiced_at DATETIME")
            )

        # Normalize legacy statuses to todo / attempted / done.
        conn.execute(
            text("UPDATE progress SET status = 'attempted' WHERE status = 'in_progress'")
        )
        conn.execute(
            text("UPDATE progress SET status = 'done' WHERE status = 'reviewed'")
        )

        # Backfill practice tracking for existing attempted/done rows.
        conn.execute(
            text(
                """
                UPDATE progress
                SET last_practiced_at = COALESCE(completed_at, updated_at, CURRENT_TIMESTAMP)
                WHERE status IN ('attempted', 'done')
                  AND last_practiced_at IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE progress
                SET solve_count = 1
                WHERE status = 'done' AND solve_count = 0
                """
            )
        )
