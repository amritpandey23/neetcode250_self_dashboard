import calendar as _calendar
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.activity import activity_count, activity_icon, log_activity, recent_activity
from app.email_challenge import question_of_the_day
from app.gemini import (
    GeminiError,
    chat as gemini_chat,
    list_chat_models,
    resolve_model,
)
from app.models import (
    ActivityLog,
    DocCategory,
    DocEntry,
    Problem,
    ProblemEntryLink,
    Progress,
    Space,
)
from app.schema import AGING_MAX_SOLVES, AGING_WEEKS
from app.utils import user_timezone

main_bp = Blueprint("main", __name__)

DIFFICULTY_ORDER = {"Easy": 0, "Medium": 1, "Hard": 2}


def _difficulty_sort_key(problem):
    return (
        DIFFICULTY_ORDER.get(problem.difficulty, 99),
        problem.order_index,
        problem.name.lower(),
    )


def _sort_by_difficulty(problems):
    return sorted(problems, key=_difficulty_sort_key)


def _progress_map(user_id):
    return {
        p.problem_id: p
        for p in Progress.query.filter_by(user_id=user_id).all()
    }


def _stats(problems, progress_by_id):
    total = len(problems)
    counts = {"todo": 0, "attempted": 0, "done": 0}
    by_difficulty = defaultdict(lambda: {"total": 0, "done": 0})
    by_category = defaultdict(lambda: {"total": 0, "done": 0})

    for problem in problems:
        entry = progress_by_id.get(problem.id)
        status = entry.status if entry else "todo"
        if status not in counts:
            status = "todo"
        counts[status] += 1

        solved = status == "done"
        by_difficulty[problem.difficulty]["total"] += 1
        by_category[problem.category]["total"] += 1
        if solved:
            by_difficulty[problem.difficulty]["done"] += 1
            by_category[problem.category]["done"] += 1

    solved = counts["done"]
    percent = round((solved / total) * 100) if total else 0

    return {
        "total": total,
        "counts": counts,
        "solved": solved,
        "percent": percent,
        "by_difficulty": dict(by_difficulty),
        "by_category": dict(by_category),
    }


def _categories():
    categories = []
    seen = set()
    for problem in Problem.query.order_by(Problem.order_index).all():
        if problem.category not in seen:
            seen.add(problem.category)
            categories.append(problem.category)
    return categories


def _safe_next_url(candidate, fallback=None):
    fallback = fallback or url_for("main.dashboard")
    if not candidate:
        return fallback
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return fallback
    if not candidate.startswith("/"):
        return fallback
    return candidate


def _normalize_leetcode_url(raw):
    """Return a cleaned http(s) URL, or None if invalid/empty."""
    url = (raw or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        return None
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    return url


def _problems_return_url():
    args = {}
    for key in ("category", "difficulty", "status", "q"):
        value = request.args.get(key)
        if value:
            args[key] = value
    return url_for("main.problems", **args)


def _slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "problem"


def _unique_slug(name):
    base = _slugify(name)
    slug = base
    counter = 2
    while Problem.query.filter_by(slug=slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _get_or_create_progress(problem_id):
    progress = Progress.query.filter_by(
        user_id=current_user.id, problem_id=problem_id
    ).first()
    if not progress:
        progress = Progress(user_id=current_user.id, problem_id=problem_id)
        db.session.add(progress)
    return progress


def _aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _apply_practice(progress, new_status, previous, log_practice=False):
    """Update practice age / solve count when attempted, done, or logged again."""
    now = datetime.now(timezone.utc)

    if new_status in ("attempted", "done"):
        progress.last_practiced_at = now

    if new_status == "done" and previous != "done":
        progress.solve_count = (progress.solve_count or 0) + 1
        progress.completed_at = now
    elif new_status == "done" and log_practice:
        # Re-practice an already-done problem (e.g. from Aging).
        progress.solve_count = (progress.solve_count or 0) + 1
        progress.last_practiced_at = now
    elif new_status == "attempted" and log_practice:
        progress.last_practiced_at = now
    elif new_status != "done":
        progress.completed_at = None


PROGRESS_RANGE_OPTIONS = (
    (7, "1W"),
    (14, "2W"),
    (30, "1M"),
    (90, "3M"),
)


def _progress_timeline(user_id, days=7):
    """Build per-day attempted/done counts for the last N days.

    Approximated from current progress timestamps (no event log):
    - attempted: last_practiced_at / updated_at for attempted+done
    - done: completed_at / last_practiced_at / updated_at for done
    """
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 7
    allowed = {option[0] for option in PROGRESS_RANGE_OPTIONS}
    if days not in allowed:
        days = 7

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    entries = Progress.query.filter(
        Progress.user_id == user_id,
        Progress.status.in_(("attempted", "done")),
    ).all()

    attempt_times = []
    done_times = []
    for entry in entries:
        if entry.status == "done":
            done_at = (
                _aware(entry.completed_at)
                or _aware(entry.last_practiced_at)
                or _aware(entry.updated_at)
            )
            attempted_at = _aware(entry.last_practiced_at) or done_at
            if attempted_at is not None:
                attempt_times.append(attempted_at)
            if done_at is not None:
                done_times.append(done_at)
        else:
            attempted_at = _aware(entry.last_practiced_at) or _aware(entry.updated_at)
            if attempted_at is not None:
                attempt_times.append(attempted_at)

    labels = []
    attempted_series = []
    done_series = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_end = day + timedelta(days=1)
        labels.append(day.strftime("%b %d"))
        attempted_series.append(
            sum(1 for ts in attempt_times if day <= ts < day_end)
        )
        done_series.append(sum(1 for ts in done_times if day <= ts < day_end))

    return {
        "days": days,
        "labels": labels,
        "attempted": attempted_series,
        "done": done_series,
        "options": PROGRESS_RANGE_OPTIONS,
    }


DIFFICULTY_SEGMENTS = (
    ("Easy", "easy"),
    ("Medium", "medium"),
    ("Hard", "hard"),
)


def _difficulty_progress(stats):
    """Build the segmented donut used by the dashboard difficulty card.

    Each difficulty gets an equal third of the ring; the filled part of that
    third is ``solved / total`` for that difficulty.
    """
    segments = []
    stops = []
    cursor = 0.0
    for label, key in DIFFICULTY_SEGMENTS:
        bucket = stats["by_difficulty"].get(label) or {"total": 0, "done": 0}
        total = bucket.get("total", 0)
        done = bucket.get("done", 0)
        ratio = (done / total) if total else 0
        end = cursor + 120.0
        fill_end = cursor + (120.0 * ratio)
        stops.append(f"var(--{key}) {cursor:.2f}deg {fill_end:.2f}deg")
        stops.append(f"var(--{key}-bg) {fill_end:.2f}deg {end:.2f}deg")
        segments.append(
            {
                "label": label,
                "key": key,
                "done": done,
                "total": total,
                "percent": round(ratio * 100),
            }
        )
        cursor = end

    return {
        "segments": segments,
        "style": "conic-gradient(" + ", ".join(stops) + ")",
        "percent": stats["percent"],
        "solved": stats["solved"],
        "total": stats["total"],
    }


def _streak_summary(user_id, tz, month=None):
    """Build the daily streak calendar for the user's local timezone.

    A day is *solved* when a problem was completed (or reviewed) that day and
    *attempted* when only practice/status activity happened. Both count toward
    the streak. History comes from Progress timestamps plus the activity log,
    which preserves days that the current progress row no longer remembers.
    """
    zone = tz or timezone.utc
    today = datetime.now(timezone.utc).astimezone(zone).date()
    focus = month or date(today.year, today.month, 1)

    day_status = {}

    def mark(stamp, solved):
        aware = _aware(stamp)
        if aware is None:
            return
        day = aware.astimezone(zone).date()
        if solved:
            day_status[day] = "solved"
        elif day_status.get(day) != "solved":
            day_status[day] = "attempted"

    entries = Progress.query.filter(Progress.user_id == user_id).all()
    for entry in entries:
        if entry.status == "done":
            mark(entry.completed_at or entry.last_practiced_at or entry.updated_at, True)
            if entry.last_practiced_at:
                mark(entry.last_practiced_at, True)
        elif entry.status == "attempted":
            mark(entry.last_practiced_at or entry.updated_at, False)

    entry_by_problem = {entry.problem_id: entry for entry in entries}
    logs = ActivityLog.query.filter(
        ActivityLog.user_id == user_id,
        ActivityLog.action.in_(("status_changed", "practice_logged")),
    ).all()
    for log in logs:
        summary = (log.summary or "").strip()
        if log.action == "practice_logged":
            entry = entry_by_problem.get(log.entity_id)
            mark(log.created_at, bool(entry and entry.status == "done"))
        elif summary.endswith(" as Done"):
            mark(log.created_at, True)
        elif summary.endswith(" as Attempted"):
            mark(log.created_at, False)

    active_days = sorted(day_status)
    best = 0
    run = 0
    previous = None
    for day in active_days:
        run = run + 1 if previous and (day - previous).days == 1 else 1
        best = max(best, run)
        previous = day

    current = 0
    cursor = today
    if cursor not in day_status:
        # Keep yesterday's streak visible until the current day ends.
        cursor -= timedelta(days=1)
    while cursor in day_status:
        current += 1
        cursor -= timedelta(days=1)

    grid = _calendar.Calendar(firstweekday=6)
    weeks = []
    for week in grid.monthdatescalendar(focus.year, focus.month):
        row = []
        for day in week:
            in_month = day.month == focus.month and day.year == focus.year
            row.append(
                {
                    "date": day,
                    "in_month": in_month,
                    "is_today": day == today,
                    "status": day_status.get(day) if in_month else None,
                }
            )
        weeks.append(row)

    return {
        "current": current,
        "best": best,
        "active_days": len(active_days),
        "today_status": day_status.get(today),
        "month_label": focus.strftime("%B %Y"),
        "weeks": weeks,
    }


def _continue_learning(all_problems, progress_by_id):
    """Pick next problem from existing progress: recent attempt, else first unfinished."""
    recent = None
    recent_ts = None
    for problem in all_problems:
        entry = progress_by_id.get(problem.id)
        if not entry or entry.status == "done":
            continue
        stamp = _aware(entry.last_practiced_at) or _aware(entry.updated_at)
        if stamp and (recent_ts is None or stamp > recent_ts):
            recent_ts = stamp
            recent = problem
    if recent:
        entry = progress_by_id[recent.id]
        return {
            "problem": recent,
            "status": entry.status,
        }

    for problem in all_problems:
        entry = progress_by_id.get(problem.id)
        status = entry.status if entry else "todo"
        if status != "done":
            return {"problem": problem, "status": status}
    return None


def _aging_entries(user_id):
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=AGING_WEEKS)
    entries = (
        Progress.query.filter(
            Progress.user_id == user_id,
            Progress.status.in_(("attempted", "done")),
            Progress.solve_count < AGING_MAX_SOLVES,
            Progress.last_practiced_at.isnot(None),
        )
        .join(Problem)
        .order_by(Progress.last_practiced_at.asc())
        .all()
    )

    aging = []
    now = datetime.now(timezone.utc)
    for entry in entries:
        last = _aware(entry.last_practiced_at)
        if last is None or last > cutoff:
            continue
        age_days = (now - last).days
        age_weeks = max(1, age_days // 7)
        aging.append(
            {
                "entry": entry,
                "problem": entry.problem,
                "age_days": age_days,
                "age_weeks": age_weeks,
            }
        )
    return aging


def _activity_stamp(entry, *, solved=False):
    """Best available date for activity ordering/display."""
    if solved:
        return (
            _aware(entry.completed_at)
            or _aware(entry.last_practiced_at)
            or _aware(entry.updated_at)
        )
    return _aware(entry.last_practiced_at) or _aware(entry.updated_at)


def _activity_lists(user_id):
    """Attempted + solved histories, newest first."""
    entries = (
        Progress.query.filter(
            Progress.user_id == user_id,
            Progress.status.in_(("attempted", "done")),
        )
        .join(Problem)
        .all()
    )

    attempted = []
    solved = []
    for entry in entries:
        if entry.status == "done":
            stamp = _activity_stamp(entry, solved=True)
            if stamp is None:
                continue
            solved.append(
                {
                    "entry": entry,
                    "problem": entry.problem,
                    "at": stamp,
                }
            )
        elif entry.status == "attempted":
            stamp = _activity_stamp(entry, solved=False)
            if stamp is None:
                continue
            attempted.append(
                {
                    "entry": entry,
                    "problem": entry.problem,
                    "at": stamp,
                }
            )

    attempted.sort(key=lambda item: item["at"], reverse=True)
    solved.sort(key=lambda item: item["at"], reverse=True)
    return attempted, solved


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    # Legacy links used /dashboard?category=... for the problem browser.
    if request.args.get("category") or request.args.get("q") or request.args.get("difficulty") or request.args.get("status"):
        return redirect(url_for("main.problems", **request.args.to_dict()))

    range_days = request.args.get("range", 7)
    progress_by_id = _progress_map(current_user.id)
    all_problems = Problem.query.order_by(Problem.order_index).all()
    stats = _stats(all_problems, progress_by_id)
    continue_learning = _continue_learning(all_problems, progress_by_id)
    aging_preview = _aging_entries(current_user.id)[:3]
    attempted_recent, solved_history = _activity_lists(current_user.id)
    activity_feed = recent_activity(current_user.id, limit=5)
    activity_total = activity_count(current_user.id)
    from app.contests import build_month_calendar, get_upcoming_contests

    user_tz = user_timezone(current_user)
    contest_preview = get_upcoming_contests(limit_per_kind=30, tz=user_tz)
    today_local = datetime.now(timezone.utc).astimezone(user_tz).date()
    difficulty_progress = _difficulty_progress(stats)
    streak = _streak_summary(current_user.id, user_tz, today_local)
    contest_calendar = build_month_calendar(
        contest_preview["all"], today_local.year, today_local.month, tz=user_tz
    )
    if not contest_calendar["agenda"] and contest_preview["all"]:
        first_start = contest_preview["all"][0]["start_local"]
        contest_calendar = build_month_calendar(
            contest_preview["all"], first_start.year, first_start.month, tz=user_tz
        )
    contest_month_label = date(
        contest_calendar["year"], contest_calendar["month"], 1
    ).strftime("%B %Y")
    progress_timeline = _progress_timeline(current_user.id, range_days)
    qotd_problem = question_of_the_day()
    qotd_entry = progress_by_id.get(qotd_problem.id) if qotd_problem else None
    qotd_status = qotd_entry.status if qotd_entry else "todo"

    return render_template(
        "dashboard.html",
        stats=stats,
        difficulty_progress=difficulty_progress,
        streak=streak,
        continue_learning=continue_learning,
        aging_preview=aging_preview,
        attempted_recent=attempted_recent,
        solved_history=solved_history,
        activity_feed=activity_feed,
        activity_total=activity_total,
        activity_icon=activity_icon,
        contest_preview=contest_preview,
        contest_calendar=contest_calendar,
        contest_month_label=contest_month_label,
        contest_timezone_name=str(user_tz),
        progress_timeline=progress_timeline,
        qotd_problem=qotd_problem,
        qotd_status=qotd_status,
        statuses=Progress.STATUSES,
        status_labels=Progress.STATUS_LABELS,
    )


@main_bp.route("/activity")
@login_required
def activity_log():
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = 50
    total = activity_count(current_user.id)
    pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = min(page, pages)
    offset = (page - 1) * per_page
    items = recent_activity(current_user.id, limit=per_page, offset=offset)
    return render_template(
        "activity.html",
        activity_feed=items,
        activity_icon=activity_icon,
        page=page,
        pages=pages,
        total=total,
        per_page=per_page,
    )


@main_bp.route("/problems")
@login_required
def problems():
    category = request.args.get("category", "")
    difficulty = request.args.get("difficulty", "")
    status = request.args.get("status", "")
    q = (request.args.get("q") or "").strip()

    query = Problem.query.order_by(Problem.order_index)
    if category:
        query = query.filter_by(category=category)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if q:
        query = query.filter(Problem.name.ilike(f"%{q}%"))

    problems = query.all()
    progress_by_id = _progress_map(current_user.id)
    all_problems = Problem.query.order_by(Problem.order_index).all()
    stats = _stats(all_problems, progress_by_id)

    if status:
        problems = [
            problem
            for problem in problems
            if (progress_by_id.get(problem.id).status if progress_by_id.get(problem.id) else "todo")
            == status
        ]

    categories = _categories()

    problems_by_category = defaultdict(list)
    for problem in problems:
        problems_by_category[problem.category].append(problem)

    grouped_problems = [
        (cat, _sort_by_difficulty(problems_by_category[cat]))
        for cat in categories
        if cat in problems_by_category
    ]

    return_url = _problems_return_url()

    return render_template(
        "problems.html",
        problems=problems,
        grouped_problems=grouped_problems,
        progress_by_id=progress_by_id,
        stats=stats,
        categories=categories,
        return_url=return_url,
        filters={
            "category": category,
            "difficulty": difficulty,
            "status": status,
            "q": q,
        },
        statuses=Progress.STATUSES,
        status_labels=Progress.STATUS_LABELS,
    )


@main_bp.route("/roadmap")
@login_required
def roadmap():
    from app.roadmap_data import NODE_H, NODE_W, ROADMAP_NODES, build_roadmap_edges

    progress_by_id = _progress_map(current_user.id)
    all_problems = Problem.query.order_by(Problem.order_index).all()
    stats = _stats(all_problems, progress_by_id)

    nodes = []
    nodes_by_name = {}
    for item in ROADMAP_NODES:
        data = stats["by_category"].get(item["name"], {"done": 0, "total": 0})
        total = data["total"]
        done = data["done"]
        percent = round((done / total) * 100) if total else 0
        if percent >= 100:
            state = "complete"
        elif percent > 0:
            state = "current"
        else:
            state = "upcoming"
        node = {
            **item,
            "done": done,
            "total": total,
            "percent": percent,
            "state": state,
            "width": NODE_W,
            "height": NODE_H,
        }
        nodes.append(node)
        nodes_by_name[item["name"]] = node

    current_node = next((n["name"] for n in nodes if n["state"] == "current"), None)
    if current_node is None:
        current_node = next((n["name"] for n in nodes if n["state"] != "complete"), None)

    for node in nodes:
        node["is_here"] = node["name"] == current_node

    return render_template(
        "roadmap.html",
        nodes=nodes,
        edges=build_roadmap_edges(nodes_by_name),
        node_w=NODE_W,
        node_h=NODE_H,
        overall=stats,
        current_node=current_node,
    )


@main_bp.route("/bookmarks")
@login_required
def bookmarks():
    entries = (
        Progress.query.filter_by(user_id=current_user.id, bookmarked=True)
        .join(Problem)
        .all()
    )
    problems = _sort_by_difficulty([entry.problem for entry in entries])
    progress_by_id = {entry.problem_id: entry for entry in entries}
    return render_template(
        "bookmarks.html",
        problems=problems,
        progress_by_id=progress_by_id,
        statuses=Progress.STATUSES,
        status_labels=Progress.STATUS_LABELS,
    )


@main_bp.route("/aging")
@login_required
def aging():
    items = _aging_entries(current_user.id)
    return render_template(
        "aging.html",
        items=items,
        status_labels=Progress.STATUS_LABELS,
        aging_weeks=AGING_WEEKS,
        aging_max_solves=AGING_MAX_SOLVES,
    )


@main_bp.route("/contests")
@login_required
def contests():
    from app.contests import build_month_calendar, get_upcoming_contests

    force = request.args.get("refresh") == "1"
    user_tz = user_timezone(current_user)
    schedule = get_upcoming_contests(limit_per_kind=30, force_refresh=force, tz=user_tz)

    today = datetime.now(timezone.utc).astimezone(user_tz).date()
    month_arg = (request.args.get("month") or "").strip()
    try:
        year_str, month_str = month_arg.split("-")
        year, month = int(year_str), int(month_str)
        if not (2000 <= year <= 2100 and 1 <= month <= 12):
            raise ValueError
        if month_arg != f"{year:04d}-{month:02d}":
            raise ValueError
    except ValueError:
        year, month = today.year, today.month

    first_of_month = date(year, month, 1)
    prev_month = (first_of_month - timedelta(days=1)).strftime("%Y-%m")
    next_month = (date(year + (month == 12), month % 12 + 1, 1)).strftime("%Y-%m")

    fetched_display = None
    if schedule["fetched_at"] is not None:
        fetched_display = schedule["fetched_at"].astimezone(user_tz).strftime(
            "%Y-%m-%d %H:%M %Z"
        )

    return render_template(
        "contests.html",
        schedule=schedule,
        calendar=build_month_calendar(schedule["all"], year, month, tz=user_tz),
        month_label=first_of_month.strftime("%B %Y"),
        month_param=f"{year:04d}-{month:02d}",
        prev_month=prev_month,
        next_month=next_month,
        is_current_month=(year, month) == (today.year, today.month),
        timezone_name=str(user_tz),
        fetched_display=fetched_display,
    )


@main_bp.route("/contests/<slug>/calendar.ics")
@login_required
def contest_ics(slug):
    from app.contests import build_ics, find_contest

    contest = find_contest(slug)
    if not contest:
        flash("Contest not found or no longer upcoming.", "error")
        return redirect(url_for("main.contests"))

    filename = f"{contest['slug']}.ics"
    return Response(
        build_ics(contest),
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@main_bp.route("/problems/add", methods=["POST"])
@login_required
def add_problem():
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip()
    difficulty = (request.form.get("difficulty") or "").strip()
    leetcode_url = _normalize_leetcode_url(request.form.get("leetcode_url"))
    next_url = _safe_next_url(
        request.form.get("next"),
        url_for("main.problems", category=category) if category else url_for("main.problems"),
    )

    if not name or not category or not leetcode_url:
        flash("Name, category, and a valid LeetCode URL are required.", "error")
        return redirect(next_url)

    if difficulty not in ("Easy", "Medium", "Hard"):
        flash("Choose a valid difficulty.", "error")
        return redirect(next_url)

    max_order = db.session.query(db.func.max(Problem.order_index)).scalar()
    problem = Problem(
        slug=_unique_slug(name),
        name=name,
        difficulty=difficulty,
        category=category,
        leetcode_url=leetcode_url,
        neetcode_url="",
        order_index=(max_order or 0) + 1,
    )
    db.session.add(problem)
    log_activity(
        current_user.id,
        "problem_added",
        f"Added problem “{name}” to {category}",
        entity_type="problem",
        href=url_for("main.problem_detail", slug=problem.slug),
    )
    db.session.commit()
    flash(f'Added "{name}" to {category}.', "success")
    return redirect(next_url)


def _user_entry_options(user_id, exclude_entry_ids=None):
    """Flat selectable list of the user's Spaces entries with path labels."""
    exclude = set(exclude_entry_ids or [])
    rows = (
        db.session.query(DocEntry, DocCategory, Space)
        .join(DocCategory, DocEntry.category_id == DocCategory.id)
        .join(Space, DocCategory.space_id == Space.id)
        .filter(Space.user_id == user_id)
        .order_by(Space.order_index.asc(), Space.name.asc(),
                  DocCategory.order_index.asc(), DocCategory.name.asc(),
                  DocEntry.order_index.asc(), DocEntry.title.asc())
        .all()
    )
    options = []
    for entry, category, space in rows:
        if entry.id in exclude:
            continue
        section_bit = f" / {entry.section.name}" if entry.section else ""
        options.append(
            {
                "id": entry.id,
                "label": f"{space.name} / {category.name}{section_bit} / {entry.title}",
                "entry": entry,
                "category": category,
                "space": space,
            }
        )
    return options


def _problem_entry_links(user_id, problem_id):
    links = (
        ProblemEntryLink.query.filter_by(user_id=user_id, problem_id=problem_id)
        .order_by(ProblemEntryLink.created_at.asc())
        .all()
    )
    enriched = []
    for link in links:
        entry = link.entry
        if not entry or not entry.category or not entry.category.space:
            continue
        if entry.category.space.user_id != user_id:
            continue
        space = entry.category.space
        category = entry.category
        enriched.append(
            {
                "link": link,
                "entry": entry,
                "space": space,
                "category": category,
                "url": url_for(
                    "docs.entry",
                    space_slug=space.slug,
                    cat_slug=category.slug,
                    entry_slug=entry.slug,
                ),
                "path": (
                    f"{space.name} / {category.name}"
                    + (f" / {entry.section.name}" if entry.section else "")
                ),
            }
        )
    return enriched


@main_bp.route("/problem/<slug>", methods=["GET", "POST"])
@login_required
def problem_detail(slug):
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    progress = Progress.query.filter_by(
        user_id=current_user.id, problem_id=problem.id
    ).first()
    # Prefer the page the user came from; otherwise return to the full dashboard.
    next_param = request.values.get("next")
    back_url = _safe_next_url(next_param, url_for("main.problems", category=problem.category))
    category_url = url_for("main.problems", category=problem.category)
    if "/aging" in (back_url or ""):
        back_href, back_label = url_for("main.aging"), "Aging"
    elif "/bookmarks" in (back_url or ""):
        back_href, back_label = url_for("main.bookmarks"), "Bookmarks"
    else:
        back_href, back_label = category_url, problem.category

    if request.method == "POST":
        new_status = request.form.get("status", "todo")
        notes = request.form.get("notes", "")
        log_practice = bool(request.form.get("log_practice"))

        if new_status not in Progress.STATUSES:
            flash("Invalid status.", "error")
            return redirect(url_for("main.problem_detail", slug=slug, next=back_url))

        if not progress:
            progress = Progress(
                user_id=current_user.id,
                problem_id=problem.id,
            )
            db.session.add(progress)

        previous = progress.status
        previous_notes = progress.notes or ""
        progress.status = new_status
        progress.notes = notes
        progress.updated_at = datetime.now(timezone.utc)
        _apply_practice(progress, new_status, previous, log_practice=log_practice)

        detail_href = url_for("main.problem_detail", slug=slug)
        if log_practice:
            log_activity(
                current_user.id,
                "practice_logged",
                f"Logged practice on {problem.name}",
                entity_type="problem",
                entity_id=problem.id,
                href=detail_href,
            )
        if previous != new_status:
            log_activity(
                current_user.id,
                "status_changed",
                f"Marked {problem.name} as {Progress.STATUS_LABELS.get(new_status, new_status)}",
                entity_type="problem",
                entity_id=problem.id,
                href=detail_href,
            )
        elif (notes or "") != previous_notes:
            log_activity(
                current_user.id,
                "notes_updated",
                f"Updated notes for {problem.name}",
                entity_type="problem",
                entity_id=problem.id,
                href=detail_href,
            )

        db.session.commit()
        if log_practice:
            flash("Practice logged. Aging timer reset.", "success")
        else:
            flash("Progress saved.", "success")
        return redirect(url_for("main.problem_detail", slug=slug, next=back_url))

    prev_problem = (
        Problem.query.filter(Problem.order_index < problem.order_index)
        .order_by(Problem.order_index.desc())
        .first()
    )
    next_problem = (
        Problem.query.filter(Problem.order_index > problem.order_index)
        .order_by(Problem.order_index.asc())
        .first()
    )

    linked_entries = _problem_entry_links(current_user.id, problem.id)
    linked_ids = {item["entry"].id for item in linked_entries}
    entry_options = _user_entry_options(current_user.id, exclude_entry_ids=linked_ids)

    gemini_api_key = current_app.config.get("GEMINI_API_KEY", "")
    gemini_configured = bool(gemini_api_key)
    gemini_model = current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_models = (
        list_chat_models(gemini_api_key, default_model=gemini_model)
        if gemini_configured
        else []
    )
    return render_template(
        "problem_detail.html",
        problem=problem,
        progress=progress,
        statuses=Progress.STATUSES,
        status_labels=Progress.STATUS_LABELS,
        back_url=back_url,
        back_href=back_href,
        back_label=back_label,
        prev_problem=prev_problem,
        next_problem=next_problem,
        aging_weeks=AGING_WEEKS,
        aging_max_solves=AGING_MAX_SOLVES,
        gemini_configured=gemini_configured,
        gemini_model=gemini_model,
        gemini_models=gemini_models,
        linked_entries=linked_entries,
        entry_options=entry_options,
    )


@main_bp.route("/problem/<slug>/link-entry", methods=["POST"])
@login_required
def link_problem_entry(slug):
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    next_url = _safe_next_url(
        request.form.get("next"),
        url_for("main.problem_detail", slug=slug),
    )
    entry_id = request.form.get("entry_id", type=int)
    if not entry_id:
        flash("Choose a Spaces entry to link.", "error")
        return redirect(next_url)

    entry = (
        DocEntry.query.join(DocCategory)
        .join(Space)
        .filter(DocEntry.id == entry_id, Space.user_id == current_user.id)
        .first()
    )
    if not entry:
        flash("That Spaces entry was not found.", "error")
        return redirect(next_url)

    existing = ProblemEntryLink.query.filter_by(
        user_id=current_user.id,
        problem_id=problem.id,
        entry_id=entry.id,
    ).first()
    if existing:
        flash("That entry is already linked.", "info")
        return redirect(next_url)

    db.session.add(
        ProblemEntryLink(
            user_id=current_user.id,
            problem_id=problem.id,
            entry_id=entry.id,
        )
    )
    log_activity(
        current_user.id,
        "entry_linked",
        f"Linked “{entry.title}” to {problem.name}",
        entity_type="problem",
        entity_id=problem.id,
        href=url_for("main.problem_detail", slug=slug),
    )
    db.session.commit()
    flash(f"Linked “{entry.title}”.", "success")
    return redirect(next_url)


@main_bp.route("/problem/<slug>/unlink-entry/<int:link_id>", methods=["POST"])
@login_required
def unlink_problem_entry(slug, link_id):
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    next_url = _safe_next_url(
        request.form.get("next"),
        url_for("main.problem_detail", slug=slug),
    )
    link = ProblemEntryLink.query.filter_by(
        id=link_id,
        user_id=current_user.id,
        problem_id=problem.id,
    ).first_or_404()
    title = link.entry.title if link.entry else "entry"
    db.session.delete(link)
    log_activity(
        current_user.id,
        "entry_unlinked",
        f"Unlinked “{title}” from {problem.name}",
        entity_type="problem",
        entity_id=problem.id,
        href=url_for("main.problem_detail", slug=slug),
    )
    db.session.commit()
    flash(f"Unlinked “{title}”.", "success")
    return redirect(next_url)


@main_bp.route("/problem/<slug>/chat", methods=["POST"])
@login_required
def problem_chat(slug):
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    history = payload.get("history") or []
    context = payload.get("context") or {}
    api_key = current_app.config.get("GEMINI_API_KEY", "")
    default_model = current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash")
    model = resolve_model(
        payload.get("model"),
        api_key,
        default_model=default_model,
    )

    try:
        answer = gemini_chat(
            api_key=api_key,
            model=model,
            problem=problem,
            message=message,
            history=history,
            context=context,
        )
    except GeminiError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except Exception:
        current_app.logger.exception("Unexpected Gemini chat failure")
        return jsonify({"error": "Unexpected AI error."}), 500

    return jsonify({"reply": answer, "model": model})


@main_bp.route("/problem/<slug>/bookmark", methods=["POST"])
@login_required
def toggle_bookmark(slug):
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    progress = _get_or_create_progress(problem.id)
    progress.bookmarked = not progress.bookmarked
    progress.updated_at = datetime.now(timezone.utc)
    log_activity(
        current_user.id,
        "bookmarked" if progress.bookmarked else "unbookmarked",
        (
            f"Bookmarked {problem.name}"
            if progress.bookmarked
            else f"Removed bookmark from {problem.name}"
        ),
        entity_type="problem",
        entity_id=problem.id,
        href=url_for("main.problem_detail", slug=slug),
    )
    db.session.commit()

    label = "Bookmarked" if progress.bookmarked else "Removed bookmark"
    flash(f"{label}: {problem.name}.", "success")

    next_url = _safe_next_url(request.form.get("next"), url_for("main.bookmarks"))
    return redirect(next_url)


@main_bp.route("/problem/<slug>/leetcode-url", methods=["POST"])
@login_required
def update_leetcode_url(slug):
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    next_url = _safe_next_url(
        request.form.get("next"),
        url_for("main.problem_detail", slug=slug),
    )
    leetcode_url = _normalize_leetcode_url(request.form.get("leetcode_url"))
    if not leetcode_url:
        flash("Enter a valid URL starting with http:// or https://.", "error")
        return redirect(next_url)

    if leetcode_url == (problem.leetcode_url or "").strip():
        flash("LeetCode link unchanged.", "info")
        return redirect(next_url)

    problem.leetcode_url = leetcode_url
    log_activity(
        current_user.id,
        "leetcode_url_updated",
        f"Updated LeetCode link for {problem.name}",
        entity_type="problem",
        entity_id=problem.id,
        href=url_for("main.problem_detail", slug=slug),
    )
    db.session.commit()
    flash("LeetCode link updated.", "success")
    return redirect(next_url)


@main_bp.route("/problem/<slug>/reset", methods=["POST"])
@login_required
def reset_progress(slug):
    """Return a problem to a clean slate (status/practice/notes), keep bookmark."""
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    progress = Progress.query.filter_by(
        user_id=current_user.id, problem_id=problem.id
    ).first()
    next_url = _safe_next_url(
        request.form.get("next"),
        url_for("main.problem_detail", slug=slug),
    )

    if not progress:
        flash(f"{problem.name} is already a clean slate.", "success")
        return redirect(next_url)

    bookmarked = bool(progress.bookmarked)
    progress.status = "todo"
    progress.notes = ""
    progress.solve_count = 0
    progress.last_practiced_at = None
    progress.completed_at = None
    progress.bookmarked = bookmarked
    progress.updated_at = datetime.now(timezone.utc)
    log_activity(
        current_user.id,
        "progress_reset",
        f"Reset progress for {problem.name}",
        entity_type="problem",
        entity_id=problem.id,
        href=url_for("main.problem_detail", slug=slug),
    )
    db.session.commit()

    flash(f"Reset {problem.name} to a clean slate.", "success")
    return redirect(next_url)
