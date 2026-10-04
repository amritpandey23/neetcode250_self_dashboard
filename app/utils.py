"""Shared helpers."""

from __future__ import annotations

import re


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
