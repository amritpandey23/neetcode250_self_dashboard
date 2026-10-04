import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
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
from app.gemini import GeminiError, chat as gemini_chat
from app.models import Problem, Progress
from app.schema import AGING_MAX_SOLVES, AGING_WEEKS

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
    """Build cumulative attempted/done series for the last N days.

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

    attempt_times.sort()
    done_times.sort()

    labels = []
    attempted_series = []
    done_series = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_end = day + timedelta(days=1)
        labels.append(day.strftime("%b %d"))
        attempted_series.append(sum(1 for ts in attempt_times if ts < day_end))
        done_series.append(sum(1 for ts in done_times if ts < day_end))

    return {
        "days": days,
        "labels": labels,
        "attempted": attempted_series,
        "done": done_series,
        "options": PROGRESS_RANGE_OPTIONS,
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
    from app.contests import get_upcoming_contests

    contest_preview = get_upcoming_contests(limit_per_kind=1)
    progress_timeline = _progress_timeline(current_user.id, range_days)

    return render_template(
        "dashboard.html",
        stats=stats,
        continue_learning=continue_learning,
        aging_preview=aging_preview,
        contest_preview=contest_preview,
        progress_timeline=progress_timeline,
        statuses=Progress.STATUSES,
        status_labels=Progress.STATUS_LABELS,
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
    from app.contests import get_upcoming_contests

    force = request.args.get("refresh") == "1"
    schedule = get_upcoming_contests(limit_per_kind=4, force_refresh=force)
    return render_template("contests.html", schedule=schedule)


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
    leetcode_url = (request.form.get("leetcode_url") or "").strip()
    next_url = _safe_next_url(
        request.form.get("next"),
        url_for("main.problems", category=category) if category else url_for("main.problems"),
    )

    if not name or not category or not leetcode_url:
        flash("Name, category, and LeetCode URL are required.", "error")
        return redirect(next_url)

    if difficulty not in ("Easy", "Medium", "Hard"):
        flash("Choose a valid difficulty.", "error")
        return redirect(next_url)

    if not leetcode_url.startswith(("http://", "https://")):
        flash("LeetCode URL must start with http:// or https://.", "error")
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
    db.session.commit()
    flash(f'Added "{name}" to {category}.', "success")
    return redirect(next_url)


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
        progress.status = new_status
        progress.notes = notes
        progress.updated_at = datetime.now(timezone.utc)
        _apply_practice(progress, new_status, previous, log_practice=log_practice)

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

    gemini_configured = bool(current_app.config.get("GEMINI_API_KEY"))
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
        gemini_model=current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash"),
    )


@main_bp.route("/problem/<slug>/chat", methods=["POST"])
@login_required
def problem_chat(slug):
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    history = payload.get("history") or []
    context = payload.get("context") or {}

    try:
        answer = gemini_chat(
            api_key=current_app.config.get("GEMINI_API_KEY", ""),
            model=current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash"),
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

    return jsonify({"reply": answer})


@main_bp.route("/problem/<slug>/bookmark", methods=["POST"])
@login_required
def toggle_bookmark(slug):
    problem = Problem.query.filter_by(slug=slug).first_or_404()
    progress = _get_or_create_progress(problem.id)
    progress.bookmarked = not progress.bookmarked
    progress.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    label = "Bookmarked" if progress.bookmarked else "Removed bookmark"
    flash(f"{label}: {problem.name}.", "success")

    next_url = _safe_next_url(request.form.get("next"), url_for("main.bookmarks"))
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
    db.session.commit()

    flash(f"Reset {problem.name} to a clean slate.", "success")
    return redirect(next_url)
