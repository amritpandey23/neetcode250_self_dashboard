"""Fetch upcoming LeetCode weekly / biweekly contests.

Uses LeetCode's public GraphQL contest feed (same source as https://leetcode.com/contest/).
Results are cached in memory to avoid hitting the network on every page load.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
CONTEST_PAGE = "https://leetcode.com/contest/"
CACHE_TTL = timedelta(hours=1)

_QUERY = """
query {
  allContests {
    title
    titleSlug
    startTime
    duration
  }
}
"""

_cache = {"fetched_at": None, "payload": None}


def _now():
    return datetime.now(timezone.utc)


def _ics_stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _calendar_links(contest: dict) -> dict:
    title = contest["title"]
    start = contest["start"]
    end = contest["end"]
    url = contest["url"]
    details = (
        f"{contest['kind_label']} LeetCode contest.\\n"
        f"Duration: {contest['duration_minutes']} minutes.\\n"
        f"{url}"
    )
    dates = f"{_ics_stamp(start)}/{_ics_stamp(end)}"
    google = "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(
        {
            "action": "TEMPLATE",
            "text": title,
            "dates": dates,
            "details": details.replace("\\n", "\n"),
            "location": url,
        }
    )
    outlook_params = urllib.parse.urlencode(
        {
            "path": "/calendar/action/compose",
            "rru": "addevent",
            "subject": title,
            "startdt": start.isoformat().replace("+00:00", "Z"),
            "enddt": end.isoformat().replace("+00:00", "Z"),
            "body": details.replace("\\n", "\n"),
            "location": url,
        }
    )
    return {
        "google": google,
        "outlook": f"https://outlook.live.com/calendar/0/action/compose?{outlook_params}",
        "outlook_office": f"https://outlook.office.com/calendar/0/deeplink/compose?{outlook_params}",
    }


def build_ics(contest: dict) -> str:
    """Build a single-event ICS document for a contest."""
    uid = f"{contest['slug']}@neetcode250-local"
    description = (
        f"{contest['kind_label']} LeetCode contest\\n"
        f"Duration: {contest['duration_minutes']} minutes\\n"
        f"{contest['url']}"
    )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NeetCode 250 Tracker//Contests//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_ics_stamp(_now())}",
        f"DTSTART:{_ics_stamp(contest['start'])}",
        f"DTEND:{_ics_stamp(contest['end'])}",
        f"SUMMARY:{contest['title']}",
        f"DESCRIPTION:{description}",
        f"URL:{contest['url']}",
        f"LOCATION:{contest['url']}",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ]
    return "\r\n".join(lines)


def find_contest(slug: str):
    """Find one upcoming contest by slug from the cached/fresh feed."""
    schedule = get_upcoming_contests(limit_per_kind=20)
    for contest in schedule["weekly"] + schedule["biweekly"]:
        if contest["slug"] == slug:
            return contest
    return None


def _relative_label(start: datetime, now: datetime) -> str:
    delta = start - now
    if delta.total_seconds() <= 0:
        return "Live / started"
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days >= 2:
        return f"in {days} days"
    if days == 1:
        return f"in 1 day {hours}h" if hours else "in 1 day"
    if hours >= 1:
        return f"in {hours}h {minutes}m"
    return f"in {minutes}m"


def _normalize(contest: dict, now: datetime) -> dict | None:
    slug = contest.get("titleSlug") or ""
    title = contest.get("title") or ""
    start_ts = contest.get("startTime")
    duration = contest.get("duration") or 0
    if start_ts is None:
        return None

    kind = None
    if slug.startswith("weekly-contest-") or title.lower().startswith("weekly contest"):
        kind = "weekly"
    elif slug.startswith("biweekly-contest-") or title.lower().startswith("biweekly contest"):
        kind = "biweekly"
    else:
        return None

    start = datetime.fromtimestamp(int(start_ts), tz=timezone.utc)
    end = start + timedelta(seconds=int(duration))
    # Keep contests that haven't ended yet.
    if end <= now:
        return None

    contest = {
        "title": title,
        "slug": slug,
        "kind": kind,
        "kind_label": "Weekly" if kind == "weekly" else "Biweekly",
        "url": f"https://leetcode.com/contest/{slug}/",
        "start": start,
        "end": end,
        "duration_minutes": int(duration) // 60,
        "start_display": start.strftime("%a, %b %d · %H:%M UTC"),
        "relative": _relative_label(start, now),
        "is_live": start <= now < end,
    }
    contest["calendar"] = _calendar_links(contest)
    return contest


def _fetch_remote() -> list[dict]:
    body = json.dumps({"query": _QUERY}).encode("utf-8")
    request = urllib.request.Request(
        LEETCODE_GRAPHQL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Referer": CONTEST_PAGE,
            "User-Agent": "NeetCode250SelfDashboard/1.0 (+local contest schedule)",
        },
        method="POST",
    )
    context = (
        ssl.create_default_context(cafile=certifi.where())
        if certifi is not None
        else ssl.create_default_context()
    )
    with urllib.request.urlopen(request, timeout=6, context=context) as response:
        payload = json.loads(response.read().decode("utf-8"))
    contests = (((payload or {}).get("data") or {}).get("allContests")) or []
    if not isinstance(contests, list):
        raise ValueError("Unexpected contest payload")
    return contests


def get_upcoming_contests(limit_per_kind: int = 3, force_refresh: bool = False) -> dict:
    """Return upcoming weekly/biweekly contests plus fetch metadata."""
    now = _now()
    fetched_at = _cache["fetched_at"]
    stale = (
        force_refresh
        or fetched_at is None
        or (now - fetched_at) > CACHE_TTL
        or _cache["payload"] is None
    )

    error = None
    raw = _cache["payload"]
    if stale:
        try:
            raw = _fetch_remote()
            _cache["payload"] = raw
            _cache["fetched_at"] = now
            fetched_at = now
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            error = str(exc)
            if raw is None:
                return {
                    "weekly": [],
                    "biweekly": [],
                    "next_weekly": None,
                    "next_biweekly": None,
                    "fetched_at": fetched_at,
                    "source": CONTEST_PAGE,
                    "error": error,
                    "stale": True,
                }

    weekly = []
    biweekly = []
    for item in raw or []:
        normalized = _normalize(item, now)
        if not normalized:
            continue
        bucket = weekly if normalized["kind"] == "weekly" else biweekly
        bucket.append(normalized)

    weekly.sort(key=lambda c: c["start"])
    biweekly.sort(key=lambda c: c["start"])

    weekly = weekly[:limit_per_kind]
    biweekly = biweekly[:limit_per_kind]

    return {
        "weekly": weekly,
        "biweekly": biweekly,
        "next_weekly": weekly[0] if weekly else None,
        "next_biweekly": biweekly[0] if biweekly else None,
        "fetched_at": fetched_at,
        "source": CONTEST_PAGE,
        "error": error,
        "stale": bool(error),
    }
