"""Shared helpers."""

from __future__ import annotations

import re
from datetime import datetime, timezone


def slugify(text, fallback="item"):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or fallback


def unique_slug(base_text, exists_fn, fallback="item"):
    """Return a slug not claimed by exists_fn(slug) -> truthy."""
    base = slugify(base_text, fallback=fallback)
    slug = base
    counter = 2
    while exists_fn(slug):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def swap_order(items, target, direction):
    """Swap target.order_index with neighbor in ordered list. Returns True if swapped."""
    if not items or target not in items:
        return False
    idx = items.index(target)
    if direction == "up" and idx > 0:
        neighbor = items[idx - 1]
    elif direction == "down" and idx < len(items) - 1:
        neighbor = items[idx + 1]
    else:
        return False
    target.order_index, neighbor.order_index = neighbor.order_index, target.order_index
    return True


def next_order_index(items):
    if not items:
        return 0
    return max(item.order_index for item in items) + 1


def relative_past(dt, now=None):
    """Human past relative label: Today, Yesterday, 3 days ago, 1 week ago, …"""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if dt > now:
        dt = now

    day_delta = (now.date() - dt.astimezone(now.tzinfo).date()).days
    if day_delta <= 0:
        return "Today"
    if day_delta == 1:
        return "Yesterday"
    if day_delta < 7:
        return f"{day_delta} days ago"

    weeks = day_delta // 7
    if day_delta < 30:
        return "1 week ago" if weeks == 1 else f"{weeks} weeks ago"

    months = day_delta // 30
    if day_delta < 365:
        return "1 month ago" if months == 1 else f"{months} months ago"

    years = day_delta // 365
    return "1 year ago" if years == 1 else f"{years} years ago"
