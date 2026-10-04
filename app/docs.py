"""Per-user document Spaces: categories, sections, and markdown entries."""

from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.models import DocCategory, DocEntry, DocSection, Space, utcnow
from app.utils import next_order_index, swap_order, unique_slug

docs_bp = Blueprint("docs", __name__, url_prefix="/spaces")


def _owned_space(space_slug):
    space = Space.query.filter_by(
        user_id=current_user.id, slug=space_slug
    ).first_or_404()
    return space


def _space_slug(name, user_id, exclude_id=None):
    def exists(slug):
        q = Space.query.filter_by(user_id=user_id, slug=slug)
        if exclude_id is not None:
            q = q.filter(Space.id != exclude_id)
        return q.first() is not None

    return unique_slug(name, exists, fallback="space")


def _category_slug(name, space_id, exclude_id=None):
    def exists(slug):
        q = DocCategory.query.filter_by(space_id=space_id, slug=slug)
        if exclude_id is not None:
            q = q.filter(DocCategory.id != exclude_id)
        return q.first() is not None

    return unique_slug(name, exists, fallback="category")


def _section_slug(name, category_id, exclude_id=None):
    def exists(slug):
        q = DocSection.query.filter_by(category_id=category_id, slug=slug)
        if exclude_id is not None:
            q = q.filter(DocSection.id != exclude_id)
        return q.first() is not None

    return unique_slug(name, exists, fallback="section")


def _entry_slug(title, category_id, exclude_id=None):
    def exists(slug):
        q = DocEntry.query.filter_by(category_id=category_id, slug=slug)
        if exclude_id is not None:
            q = q.filter(DocEntry.id != exclude_id)
        return q.first() is not None

    return unique_slug(title, exists, fallback="entry")


def _ordered_spaces():
    return (
        Space.query.filter_by(user_id=current_user.id)
        .order_by(Space.order_index.asc(), Space.name.asc())
        .all()
    )


def _ordered_categories(space):
    return (
        DocCategory.query.filter_by(space_id=space.id)
        .order_by(DocCategory.order_index.asc(), DocCategory.name.asc())
        .all()
    )


def _category_entry_counts(space):
    counts = {}
    for cat in space.categories:
        counts[cat.id] = len(cat.entries)
    return counts


def _category_tree(category):
    """Sections + unsectioned entries for one category (sidebar / main list)."""
    sections = (
        DocSection.query.filter_by(category_id=category.id)
        .order_by(DocSection.order_index.asc(), DocSection.name.asc())
        .all()
    )
    unsectioned = (
        DocEntry.query.filter_by(category_id=category.id, section_id=None)
        .order_by(DocEntry.order_index.asc(), DocEntry.title.asc())
        .all()
    )
    section_entries = {
        section.id: (
            DocEntry.query.filter_by(section_id=section.id)
            .order_by(DocEntry.order_index.asc(), DocEntry.title.asc())
            .all()
        )
        for section in sections
    }
    return {
        "sections": sections,
        "section_entries": section_entries,
        "unsectioned": unsectioned,
    }


def _space_nav_context(space, active_category=None, active_entry=None):
    categories = _ordered_categories(space)
    trees = {cat.id: _category_tree(cat) for cat in categories}
    return {
        "space": space,
        "categories": categories,
        "category_trees": trees,
        "entry_counts": _category_entry_counts(space),
        "active_category": active_category,
        "active_entry": active_entry,
    }


# ---------- Hub ----------


@docs_bp.route("/", methods=["GET"])
@login_required
def index():
    spaces = _ordered_spaces()
    return render_template("spaces/index.html", spaces=spaces)


@docs_bp.route("/", methods=["POST"])
@login_required
def create_space():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Space name is required.", "error")
        return redirect(url_for("docs.index"))
    if len(name) > 200:
        flash("Space name is too long.", "error")
        return redirect(url_for("docs.index"))

    spaces = _ordered_spaces()
    space = Space(
        user_id=current_user.id,
        name=name,
        slug=_space_slug(name, current_user.id),
        order_index=next_order_index(spaces),
    )
    db.session.add(space)
    db.session.commit()
    flash(f"Created space “{space.name}”.", "success")
    return redirect(url_for("docs.space_home", space_slug=space.slug))


@docs_bp.route("/<space_slug>/rename", methods=["POST"])
@login_required
def rename_space(space_slug):
    space = _owned_space(space_slug)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Space name is required.", "error")
        return redirect(url_for("docs.index"))
    space.name = name
    space.slug = _space_slug(name, current_user.id, exclude_id=space.id)
    space.updated_at = utcnow()
    db.session.commit()
    flash("Space renamed.", "success")
    next_url = request.form.get("next") or url_for("docs.index")
    return redirect(next_url)


@docs_bp.route("/<space_slug>/delete", methods=["POST"])
@login_required
def delete_space(space_slug):
    space = _owned_space(space_slug)
    name = space.name
    db.session.delete(space)
    db.session.commit()
    flash(f"Deleted space “{name}”.", "success")
    return redirect(url_for("docs.index"))


@docs_bp.route("/<space_slug>/reorder", methods=["POST"])
@login_required
def reorder_space(space_slug):
    space = _owned_space(space_slug)
    direction = request.form.get("direction")
    spaces = _ordered_spaces()
    if swap_order(spaces, space, direction):
        db.session.commit()
    return redirect(request.form.get("next") or url_for("docs.index"))


# ---------- Space / category ----------


@docs_bp.route("/<space_slug>")
@login_required
def space_home(space_slug):
    space = _owned_space(space_slug)
    categories = _ordered_categories(space)
    if categories:
        return redirect(
            url_for(
                "docs.category",
                space_slug=space.slug,
                cat_slug=categories[0].slug,
            )
        )
    nav = _space_nav_context(space)
    return render_template(
        "spaces/category.html",
        category=None,
        sections=[],
        section_entries={},
        unsectioned=[],
        **nav,
    )


@docs_bp.route("/<space_slug>/<cat_slug>")
@login_required
def category(space_slug, cat_slug):
    space = _owned_space(space_slug)
    category = DocCategory.query.filter_by(
        space_id=space.id, slug=cat_slug
    ).first_or_404()
    tree = _category_tree(category)
    nav = _space_nav_context(space, active_category=category)
    return render_template(
        "spaces/category.html",
        category=category,
        sections=tree["sections"],
        section_entries=tree["section_entries"],
        unsectioned=tree["unsectioned"],
        **nav,
    )


@docs_bp.route("/<space_slug>/categories", methods=["POST"])
@login_required
def create_category(space_slug):
    space = _owned_space(space_slug)
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Category name is required.", "error")
        return redirect(url_for("docs.space_home", space_slug=space.slug))
    categories = _ordered_categories(space)
    cat = DocCategory(
        space_id=space.id,
        name=name,
        slug=_category_slug(name, space.id),
        order_index=next_order_index(categories),
    )
    db.session.add(cat)
    db.session.commit()
    flash(f"Created category “{cat.name}”.", "success")
    return redirect(
        url_for("docs.category", space_slug=space.slug, cat_slug=cat.slug)
    )


@docs_bp.route("/<space_slug>/categories/<int:category_id>/rename", methods=["POST"])
@login_required
def rename_category(space_slug, category_id):
    space = _owned_space(space_slug)
    cat = DocCategory.query.filter_by(id=category_id, space_id=space.id).first_or_404()
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Category name is required.", "error")
        return redirect(
            url_for("docs.category", space_slug=space.slug, cat_slug=cat.slug)
        )
    cat.name = name
    cat.slug = _category_slug(name, space.id, exclude_id=cat.id)
    cat.updated_at = utcnow()
    db.session.commit()
    flash("Category renamed.", "success")
    return redirect(
        url_for("docs.category", space_slug=space.slug, cat_slug=cat.slug)
    )


@docs_bp.route("/<space_slug>/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(space_slug, category_id):
    space = _owned_space(space_slug)
    cat = DocCategory.query.filter_by(id=category_id, space_id=space.id).first_or_404()
    name = cat.name
    db.session.delete(cat)
    db.session.commit()
    flash(f"Deleted category “{name}”.", "success")
    return redirect(url_for("docs.space_home", space_slug=space.slug))


@docs_bp.route("/<space_slug>/categories/<int:category_id>/reorder", methods=["POST"])
@login_required
def reorder_category(space_slug, category_id):
    space = _owned_space(space_slug)
    cat = DocCategory.query.filter_by(id=category_id, space_id=space.id).first_or_404()
    categories = _ordered_categories(space)
    if swap_order(categories, cat, request.form.get("direction")):
        db.session.commit()
    return redirect(
        request.form.get("next")
        or url_for("docs.category", space_slug=space.slug, cat_slug=cat.slug)
    )


# ---------- Sections ----------


@docs_bp.route("/<space_slug>/sections", methods=["POST"])
@login_required
def create_section(space_slug):
    space = _owned_space(space_slug)
    category_id = request.form.get("category_id", type=int)
    cat = DocCategory.query.filter_by(id=category_id, space_id=space.id).first_or_404()
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Section name is required.", "error")
        return redirect(
            url_for("docs.category", space_slug=space.slug, cat_slug=cat.slug)
        )
    sections = (
        DocSection.query.filter_by(category_id=cat.id)
        .order_by(DocSection.order_index.asc())
        .all()
    )
    section = DocSection(
        category_id=cat.id,
        name=name,
        slug=_section_slug(name, cat.id),
        order_index=next_order_index(sections),
    )
    db.session.add(section)
    db.session.commit()
    flash(f"Created section “{section.name}”.", "success")
    return redirect(
        url_for("docs.category", space_slug=space.slug, cat_slug=cat.slug)
    )


@docs_bp.route("/<space_slug>/sections/<int:section_id>/rename", methods=["POST"])
@login_required
def rename_section(space_slug, section_id):
    space = _owned_space(space_slug)
    section = (
        DocSection.query.join(DocCategory)
        .filter(DocSection.id == section_id, DocCategory.space_id == space.id)
        .first_or_404()
    )
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Section name is required.", "error")
        return redirect(
            url_for(
                "docs.category",
                space_slug=space.slug,
                cat_slug=section.category.slug,
            )
        )
    section.name = name
    section.slug = _section_slug(name, section.category_id, exclude_id=section.id)
    section.updated_at = utcnow()
    db.session.commit()
    flash("Section renamed.", "success")
    return redirect(
        url_for(
            "docs.category",
            space_slug=space.slug,
            cat_slug=section.category.slug,
        )
    )


@docs_bp.route("/<space_slug>/sections/<int:section_id>/delete", methods=["POST"])
@login_required
def delete_section(space_slug, section_id):
    space = _owned_space(space_slug)
    section = (
        DocSection.query.join(DocCategory)
        .filter(DocSection.id == section_id, DocCategory.space_id == space.id)
        .first_or_404()
    )
    cat_slug = section.category.slug
    name = section.name
    db.session.delete(section)
    db.session.commit()
    flash(f"Deleted section “{name}”.", "success")
    return redirect(
        url_for("docs.category", space_slug=space.slug, cat_slug=cat_slug)
    )


@docs_bp.route("/<space_slug>/sections/<int:section_id>/reorder", methods=["POST"])
@login_required
def reorder_section(space_slug, section_id):
    space = _owned_space(space_slug)
    section = (
        DocSection.query.join(DocCategory)
        .filter(DocSection.id == section_id, DocCategory.space_id == space.id)
        .first_or_404()
    )
    sections = (
        DocSection.query.filter_by(category_id=section.category_id)
        .order_by(DocSection.order_index.asc(), DocSection.name.asc())
        .all()
    )
    if swap_order(sections, section, request.form.get("direction")):
        db.session.commit()
    return redirect(
        url_for(
            "docs.category",
            space_slug=space.slug,
            cat_slug=section.category.slug,
        )
    )


# ---------- Entries ----------


@docs_bp.route("/<space_slug>/entries/new", methods=["GET", "POST"])
@login_required
def new_entry(space_slug):
    space = _owned_space(space_slug)
    category_id = request.values.get("category_id", type=int)
    section_id = request.values.get("section_id", type=int)
    cat = DocCategory.query.filter_by(id=category_id, space_id=space.id).first_or_404()
    section = None
    if section_id:
        section = DocSection.query.filter_by(
            id=section_id, category_id=cat.id
        ).first_or_404()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        body = request.form.get("body") or ""
        if not title:
            flash("Entry title is required.", "error")
            return render_template(
                "spaces/entry_form.html",
                space=space,
                category=cat,
                section=section,
                entry=None,
                title_value=title,
                body_value=body,
            )
        siblings = (
            DocEntry.query.filter_by(
                category_id=cat.id,
                section_id=section.id if section else None,
            )
            .order_by(DocEntry.order_index.asc())
            .all()
        )
        entry = DocEntry(
            category_id=cat.id,
            section_id=section.id if section else None,
            title=title,
            slug=_entry_slug(title, cat.id),
            body=body,
            order_index=next_order_index(siblings),
        )
        db.session.add(entry)
        db.session.commit()
        flash("Entry created.", "success")
        return redirect(
            url_for(
                "docs.entry",
                space_slug=space.slug,
                cat_slug=cat.slug,
                entry_slug=entry.slug,
            )
        )

    return render_template(
        "spaces/entry_form.html",
        space=space,
        category=cat,
        section=section,
        entry=None,
        title_value="",
        body_value="",
    )


@docs_bp.route("/<space_slug>/<cat_slug>/e/<entry_slug>")
@login_required
def entry(space_slug, cat_slug, entry_slug):
    """Preview an entry inside the space shell."""
    space = _owned_space(space_slug)
    cat = DocCategory.query.filter_by(space_id=space.id, slug=cat_slug).first_or_404()
    entry = DocEntry.query.filter_by(
        category_id=cat.id, slug=entry_slug
    ).first_or_404()
    nav = _space_nav_context(space, active_category=cat, active_entry=entry)
    return render_template(
        "spaces/entry_preview.html",
        category=cat,
        section=entry.section,
        entry=entry,
        **nav,
    )


@docs_bp.route(
    "/<space_slug>/<cat_slug>/e/<entry_slug>/edit", methods=["GET", "POST"]
)
@login_required
def edit_entry(space_slug, cat_slug, entry_slug):
    space = _owned_space(space_slug)
    cat = DocCategory.query.filter_by(space_id=space.id, slug=cat_slug).first_or_404()
    entry = DocEntry.query.filter_by(
        category_id=cat.id, slug=entry_slug
    ).first_or_404()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        body = request.form.get("body") or ""
        if not title:
            flash("Entry title is required.", "error")
            return render_template(
                "spaces/entry_form.html",
                space=space,
                category=cat,
                section=entry.section,
                entry=entry,
                title_value=title,
                body_value=body,
            )
        entry.title = title
        entry.slug = _entry_slug(title, cat.id, exclude_id=entry.id)
        entry.body = body
        entry.updated_at = utcnow()
        db.session.commit()
        flash("Entry saved.", "success")
        return redirect(
            url_for(
                "docs.entry",
                space_slug=space.slug,
                cat_slug=cat.slug,
                entry_slug=entry.slug,
            )
        )

    return render_template(
        "spaces/entry_form.html",
        space=space,
        category=cat,
        section=entry.section,
        entry=entry,
        title_value=entry.title,
        body_value=entry.body or "",
    )


@docs_bp.route("/<space_slug>/entries/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_entry(space_slug, entry_id):
    space = _owned_space(space_slug)
    entry = (
        DocEntry.query.join(DocCategory)
        .filter(DocEntry.id == entry_id, DocCategory.space_id == space.id)
        .first_or_404()
    )
    cat_slug = entry.category.slug
    title = entry.title
    db.session.delete(entry)
    db.session.commit()
    flash(f"Deleted entry “{title}”.", "success")
    return redirect(
        url_for("docs.category", space_slug=space.slug, cat_slug=cat_slug)
    )


@docs_bp.route("/<space_slug>/entries/<int:entry_id>/reorder", methods=["POST"])
@login_required
def reorder_entry(space_slug, entry_id):
    space = _owned_space(space_slug)
    entry = (
        DocEntry.query.join(DocCategory)
        .filter(DocEntry.id == entry_id, DocCategory.space_id == space.id)
        .first_or_404()
    )
    siblings = (
        DocEntry.query.filter_by(
            category_id=entry.category_id, section_id=entry.section_id
        )
        .order_by(DocEntry.order_index.asc(), DocEntry.title.asc())
        .all()
    )
    if swap_order(siblings, entry, request.form.get("direction")):
        db.session.commit()
    return redirect(
        url_for(
            "docs.category",
            space_slug=space.slug,
            cat_slug=entry.category.slug,
        )
    )
