import json

from flask import current_app

from app import db
from app.models import Problem


def seed_problems():
    """Load problems from neetcode_250_complete.json if the table is empty or incomplete."""
    json_path = current_app.config["NEETCODE_JSON"]
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    problems_data = data.get("problems", [])
    existing = {p.slug: p for p in Problem.query.all()}

    if len(existing) == len(problems_data):
        return

    for index, item in enumerate(problems_data):
        slug = item["slug"]
        if slug in existing:
            problem = existing[slug]
            problem.name = item["name"]
            problem.difficulty = item["difficulty"]
            problem.category = item["category"]
            problem.neetcode_url = item["neetcode_url"]
            problem.leetcode_url = item["leetcode_url"]
            problem.order_index = index
        else:
            db.session.add(
                Problem(
                    slug=slug,
                    name=item["name"],
                    difficulty=item["difficulty"],
                    category=item["category"],
                    neetcode_url=item["neetcode_url"],
                    leetcode_url=item["leetcode_url"],
                    order_index=index,
                )
            )

    db.session.commit()
