"""Classement général des joueurs."""

from flask import Blueprint, render_template, session
from flask_login import current_user
from sqlalchemy import func

from filmatrix.extensions import db
from filmatrix.models import Attempt, User
from filmatrix.services.friends import get_friendship_between
from filmatrix.services.levels import calculate_level


bp = Blueprint("leaderboard", __name__)


@bp.route("/classement")
def leaderboard() -> str:
    """Affiche le classement général des joueurs, trié par XP total"""
    results = (
            db.session.query(
                User.id,
                User.username,
                User.total_xp,
                func.count(Attempt.id).label("total"),
                func.sum(db.case((Attempt.is_correct, 1), else_=0)).label("correct"),
            )
            .join(Attempt, Attempt.user_id == User.id)
            .group_by(User.id)
            .order_by(User.total_xp.desc())
            .all()
        )

    leaderboard_entries = []
    for result in results:
        level_info = calculate_level(result.total_xp)

        friendship_status = None
        if current_user.is_authenticated and current_user.id != result.id:
            friendship = get_friendship_between(current_user.id, result.id)
            if friendship is not None:
                friendship_status = friendship.status

        leaderboard_entries.append(
                {
                    "user_id": result.id,
                    "username": result.username,
                    "total_xp": result.total_xp,
                    "level": level_info["level"],
                    "total": result.total,
                    "correct": result.correct,
                    "friendship_status": friendship_status,
                    }
            )

    return render_template("leaderboard/classement.html", results=leaderboard_entries)
