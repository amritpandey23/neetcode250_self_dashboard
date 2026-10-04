"""Helpers for recording and presenting core app activity."""

from __future__ import annotations

from app import db
from app.models import ActivityLog, utcnow

# Lucide icon names for dashboard rendering.
ACTION_ICONS = {
    "status_changed": "circle-dot",
    "practice_logged": "refresh-cw",
    "notes_updated": "pen-line",
    "bookmarked": "star",
    "unbookmarked": "star",
    "progress_reset": "eraser",
    "leetcode_url_updated": "link",
    "entry_linked": "link",
    "entry_unlinked": "unlink",
    "problem_added": "plus",
    "space_created": "library",
    "space_renamed": "pencil",
    "space_deleted": "trash-2",
    "category_created": "folder-plus",
    "category_renamed": "pencil",
    "category_deleted": "trash-2",
    "section_created": "folder-plus",
    "section_renamed": "pencil",
    "section_deleted": "trash-2",
    "entry_created": "file-plus",
    "entry_saved": "save",
    "entry_deleted": "trash-2",
}


def log_activity(
    user_id,
    action,
    summary,
    *,
    entity_type=None,
    entity_id=None,
    href=None,
):
    """Queue an activity row; caller must commit the session."""
    db.session.add(
        ActivityLog(
            user_id=user_id,
            action=action,
            summary=(summary or "").strip()[:500] or action,
            entity_type=entity_type,
            entity_id=entity_id,
            href=(href or "").strip()[:500] or None,
            created_at=utcnow(),
        )
    )


def recent_activity(user_id, limit=50, offset=0):
    query = (
        ActivityLog.query.filter_by(user_id=user_id)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
    )
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def activity_count(user_id):
    return ActivityLog.query.filter_by(user_id=user_id).count()


def activity_icon(action):
    return ACTION_ICONS.get(action, "activity")
