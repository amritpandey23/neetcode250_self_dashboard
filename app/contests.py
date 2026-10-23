"""Fetch upcoming contests from LeetCode, CodeChef and Codeforces.

LeetCode data comes from its public GraphQL contest feed (same source as
https://leetcode.com/contest/). CodeChef data comes from the JSON feed behind
https://www.codechef.com/contests. Codeforces data comes from its public
contest.list API. Results are cached in memory to avoid hitting the network on
every page load.
"""

from __future__ import annotations

import calendar as _calendar
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
LEETCODE_CONTEST_PAGE = "https://leetcode.com/contest/"
CODECHEF_API = "https://www.codechef.com/api/list/contests/all"
CODECHEF_CONTEST_PAGE = "https://www.codechef.com/contests"
CODEFORCES_API = "https://codeforces.com/api/contest.list?gym=false"
CODEFORCES_CONTEST_PAGE = "https://codeforces.com/contests"
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

_caches = {
    "leetcode": {"fetched_at": None, "payload": None},
    "codechef": {"fetched_at": None, "payload": None},
    "codeforces": {"fetched_at": None, "payload": None},
}

# Errors we treat as "source unavailable" rather than a bug in the app.
_FETCH_ERRORS = (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ssl_context():
    return (
        ssl.create_default_context(cafile=certifi.where())
        if certifi is not None
        else ssl.create_default_context()
    )


def _ics_stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _calendar_links(contest: dict) -> dict:
    title = contest["title"]
    start = contest["start"]
    end = contest["end"]
    url = contest["url"]
    details = (
        f"{contest['kind_label']} contest on {contest['platform']}.\\n"
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
    uid = f"{contest['platform_key']}-{contest['slug']}@neetcode250-local"
    description = (
        f"{contest['kind_label']} contest on {contest['platform']}\\n"
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
    schedule = get_upcoming_contests(limit_per_kind=30)
    for contest in schedule["all"]:
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


def _base_contest(
    *,
    title: str,
    slug: str,
    platform: str,
    platform_key: str,
    kind: str,
    kind_label: str,
    url: str,
    start: datetime,
    end: datetime,
    now: datetime,
    tz,
) -> dict:
    start_local = start.astimezone(tz)
    contest = {
        "title": title,
        "slug": slug,
        "platform": platform,
        "platform_key": platform_key,
        "kind": kind,
        "kind_label": kind_label,
        "url": url,
        "start": start,
        "end": end,
        "start_local": start_local,
        "local_date": start_local.date(),
        "duration_minutes": int((end - start).total_seconds()) // 60,
        "start_display": start_local.strftime("%a, %b %d · %H:%M %Z"),
        "start_time": start_local.strftime("%H:%M"),
        "relative": _relative_label(start, now),
        "is_live": start <= now < end,
    }
    contest["calendar"] = _calendar_links(contest)
    return contest


def _normalize_leetcode(contest: dict, now: datetime, tz) -> dict | None:
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

    return _base_contest(
        title=title,
        slug=slug,
        platform="LeetCode",
        platform_key="leetcode",
        kind=kind,
        kind_label="Weekly" if kind == "weekly" else "Biweekly",
        url=f"https://leetcode.com/contest/{slug}/",
        start=start,
        end=end,
        now=now,
        tz=tz,
    )


_CODECHEF_SERIES = (
    ("START", "Starters"),
    ("DSAMONDAY", "DSA Monday"),
    ("PLACEPREP", "Placement Prep"),
    ("LTIME", "Lunchtime"),
    ("COOK", "Cook-Off"),
)


def _codechef_series(code: str, title: str) -> str:
    upper = (code or "").upper()
    for prefix, label in _CODECHEF_SERIES:
        if upper.startswith(prefix):
            return label
    return title.split("(")[0].strip() or "CodeChef"


def _normalize_codechef(contest: dict, now: datetime, tz) -> dict | None:
    code = (contest.get("contest_code") or "").strip()
    title = (contest.get("contest_name") or "").strip()
    start_iso = contest.get("contest_start_date_iso")
    end_iso = contest.get("contest_end_date_iso")
    if not code or not title or not start_iso or not end_iso:
        return None

    try:
        start = datetime.fromisoformat(start_iso).astimezone(timezone.utc)
        end = datetime.fromisoformat(end_iso).astimezone(timezone.utc)
    except ValueError:
        return None

    if end <= now:
        return None

    return _base_contest(
        title=title,
        slug=code,
        platform="CodeChef",
        platform_key="codechef",
        kind="codechef",
        kind_label=_codechef_series(code, title),
        url=f"https://www.codechef.com/{code}",
        start=start,
        end=end,
        now=now,
        tz=tz,
    )


_CODEFORCES_SERIES = (
    ("educational", "Educational Round"),
    ("codeforces round", "Codeforces Round"),
    ("icpc", "ICPC"),
)


def _codeforces_series(name: str) -> str:
    lower = (name or "").lower()
    for prefix, label in _CODEFORCES_SERIES:
        if prefix in lower:
            return label
    return "Codeforces"


def _normalize_codeforces(contest: dict, now: datetime, tz) -> dict | None:
    if contest.get("phase") not in ("BEFORE", "CODING"):
        return None

    contest_id = contest.get("id")
    start_ts = contest.get("startTimeSeconds")
    duration = contest.get("durationSeconds") or 0
    if contest_id is None or start_ts is None:
        return None

    start = datetime.fromtimestamp(int(start_ts), tz=timezone.utc)
    end = start + timedelta(seconds=int(duration))
    if end <= now:
        return None

    name = contest.get("name") or f"Codeforces Contest {contest_id}"
    return _base_contest(
        title=name,
        slug=f"codeforces-{contest_id}",
        platform="Codeforces",
        platform_key="codeforces",
        kind="codeforces",
        kind_label=_codeforces_series(name),
        url=f"https://codeforces.com/contest/{contest_id}",
        start=start,
        end=end,
        now=now,
        tz=tz,
    )


def _fetch_leetcode() -> list[dict]:
    body = json.dumps({"query": _QUERY}).encode("utf-8")
    request = urllib.request.Request(
        LEETCODE_GRAPHQL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Referer": LEETCODE_CONTEST_PAGE,
            "User-Agent": "NeetCode250SelfDashboard/1.0 (+local contest schedule)",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=6, context=_ssl_context()) as response:
        payload = json.loads(response.read().decode("utf-8"))
    contests = (((payload or {}).get("data") or {}).get("allContests")) or []
    if not isinstance(contests, list):
        raise ValueError("Unexpected LeetCode payload")
    return contests


def _fetch_codechef() -> list[dict]:
    query = urllib.parse.urlencode(
        {"sort_by": "START", "sorting_order": "asc", "offset": 0, "limit": 50, "mode": "all"}
    )
    request = urllib.request.Request(
        f"{CODECHEF_API}?{query}",
        headers={
            "Accept": "application/json",
            "Referer": CODECHEF_CONTEST_PAGE,
            "User-Agent": "NeetCode250SelfDashboard/1.0 (+local contest schedule)",
        },
    )
    with urllib.request.urlopen(request, timeout=6, context=_ssl_context()) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("status") not in (None, "success"):
        raise ValueError("Unexpected CodeChef payload")
    items = (payload.get("present_contests") or []) + (payload.get("future_contests") or [])
    if not isinstance(items, list):
        raise ValueError("Unexpected CodeChef payload")
    return items


def _fetch_codeforces() -> list[dict]:
    request = urllib.request.Request(
        CODEFORCES_API,
        headers={
            "Accept": "application/json",
            "Referer": CODEFORCES_CONTEST_PAGE,
            "User-Agent": "NeetCode250SelfDashboard/1.0 (+local contest schedule)",
        },
    )
    with urllib.request.urlopen(request, timeout=8, context=_ssl_context()) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("status") != "OK":
        raise ValueError("Unexpected Codeforces payload")
    contests = payload.get("result") or []
    if not isinstance(contests, list):
        raise ValueError("Unexpected Codeforces payload")
    return [c for c in contests if c.get("phase") in ("BEFORE", "CODING")]


def _load_source(key: str, fetcher, force_refresh: bool):
    """Return (raw payload, fetched_at, error) for one platform, with caching."""
    cache = _caches[key]
    now = _now()
    fetched_at = cache["fetched_at"]
    needs_refresh = (
        force_refresh
        or fetched_at is None
        or (now - fetched_at) > CACHE_TTL
        or cache["payload"] is None
    )

    error = None
    if needs_refresh:
        try:
            cache["payload"] = fetcher()
            cache["fetched_at"] = now
            fetched_at = now
        except _FETCH_ERRORS as exc:
            error = str(exc) or exc.__class__.__name__
            if cache["payload"] is None:
                return None, fetched_at, error

    return cache["payload"], fetched_at, error


_SOURCES = (
    ("leetcode", "LeetCode", _fetch_leetcode),
    ("codechef", "CodeChef", _fetch_codechef),
    ("codeforces", "Codeforces", _fetch_codeforces),
)


def get_upcoming_contests(
    limit_per_kind: int = 3,
    force_refresh: bool = False,
    tz=None,
) -> dict:
    """Return upcoming contests from all platforms plus fetch metadata.

    ``tz`` controls the display timezone (defaults to UTC). Cached payloads are
    always stored raw, so switching timezone only re-formats the results.
    """
    zone = tz or timezone.utc
    now = _now()

    with ThreadPoolExecutor(max_workers=len(_SOURCES)) as pool:
        futures = {
            key: pool.submit(_load_source, key, fetcher, force_refresh)
            for key, _label, fetcher in _SOURCES
        }
        loaded = {key: future.result() for key, future in futures.items()}

    lc_raw, lc_fetched, lc_error = loaded["leetcode"]
    cc_raw, cc_fetched, cc_error = loaded["codechef"]
    cf_raw, cf_fetched, cf_error = loaded["codeforces"]

    weekly = []
    biweekly = []
    for item in lc_raw or []:
        normalized = _normalize_leetcode(item, now, zone)
        if not normalized:
            continue
        bucket = weekly if normalized["kind"] == "weekly" else biweekly
        bucket.append(normalized)

    codechef = []
    for item in cc_raw or []:
        normalized = _normalize_codechef(item, now, zone)
        if normalized:
            codechef.append(normalized)

    codeforces = []
    for item in cf_raw or []:
        normalized = _normalize_codeforces(item, now, zone)
        if normalized:
            codeforces.append(normalized)

    weekly.sort(key=lambda c: c["start"])
    biweekly.sort(key=lambda c: c["start"])
    codechef.sort(key=lambda c: c["start"])
    codeforces.sort(key=lambda c: c["start"])

    weekly = weekly[:limit_per_kind]
    biweekly = biweekly[:limit_per_kind]
    codechef = codechef[:limit_per_kind]
    codeforces = codeforces[:limit_per_kind]

    all_contests = sorted(weekly + biweekly + codechef + codeforces, key=lambda c: c["start"])
    fetched_times = [t for t in (lc_fetched, cc_fetched, cf_fetched) if t is not None]
    errors = {
        key: message
        for key, message in (
            ("leetcode", lc_error),
            ("codechef", cc_error),
            ("codeforces", cf_error),
        )
        if message
    }
    labels = {"leetcode": "LeetCode", "codechef": "CodeChef", "codeforces": "Codeforces"}

    return {
        "weekly": weekly,
        "biweekly": biweekly,
        "codechef": codechef,
        "codeforces": codeforces,
        "all": all_contests,
        "next_weekly": weekly[0] if weekly else None,
        "next_biweekly": biweekly[0] if biweekly else None,
        "fetched_at": max(fetched_times) if fetched_times else None,
        "source": LEETCODE_CONTEST_PAGE,
        "sources": [
            {"name": "LeetCode", "url": LEETCODE_CONTEST_PAGE},
            {"name": "CodeChef", "url": CODECHEF_CONTEST_PAGE},
            {"name": "Codeforces", "url": CODEFORCES_CONTEST_PAGE},
        ],
        "errors": errors,
        "failed_sources": [labels[key] for key in errors],
        "error": "; ".join(f"{labels[key]}: {msg}" for key, msg in errors.items()) or None,
        "stale": bool(errors),
        "timezone": str(zone),
    }


def build_month_calendar(contests: list[dict], year: int, month: int, tz=None) -> dict:
    """Group contests into a Sunday-first month grid plus a flat agenda.

    Days are calendar days in ``tz`` (the user's timezone).
    """
    zone = tz or timezone.utc
    today = datetime.now(timezone.utc).astimezone(zone).date()
    by_day: dict[date, list[dict]] = {}
    for contest in contests:
        day = contest["start"].astimezone(zone).date()
        if day.year == year and day.month == month:
            by_day.setdefault(day, []).append(contest)

    grid = _calendar.Calendar(firstweekday=6)
    weeks = []
    agenda = []
    for week in grid.monthdatescalendar(year, month):
        row = []
        for day in week:
            day_contests = sorted(by_day.get(day, []), key=lambda c: c["start"])
            platforms = []
            for contest in day_contests:
                key = contest["platform_key"]
                if key not in platforms:
                    platforms.append(key)
            entry = {
                "date": day,
                "in_month": day.month == month and day.year == year,
                "is_today": day == today,
                "contests": day_contests,
                "platforms": platforms,
            }
            row.append(entry)
            if entry["in_month"] and day_contests:
                agenda.append(entry)
        weeks.append(row)

    return {"year": year, "month": month, "weeks": weeks, "agenda": agenda}
