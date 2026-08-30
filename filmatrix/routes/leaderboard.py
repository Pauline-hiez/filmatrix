"""Classement général des joueurs."""

from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, session
from flask_login import current_user
from sqlalchemy import func

from filmatrix.extensions import db
from filmatrix.models import Attempt, User
from filmatrix.services.friends import get_friendship_between
from filmatrix.services.levels import calculate_level


bp = Blueprint("leaderboard", __name__)

PERIODS = {"week", "month", "all"}


def period_cutoff(period: str) -> datetime | None:
    """Renvoie le début de la période demandée, ou None pour « tous les temps »

    Semaine = depuis lundi 00h00, mois = depuis le 1er 00h00 (heure serveur) :
    des fenêtres calendaires, pas un simple « -7 jours » glissant."""
    now = datetime.utcnow()
    if period == "week":
        return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


@bp.route("/classement")
def leaderboard() -> str:
    """Affiche le classement des joueurs, sur une période choisie

    « Tous les temps » trie sur User.total_xp (fiable depuis toujours). Les
    fenêtres semaine/mois trient sur la somme d'Attempt.earned_xp : cette
    colonne n'existe que depuis son ajout, donc ces deux vues ne reflètent
    fidèlement que l'activité postérieure à ce déploiement — les parties plus
    anciennes comptent pour 0 XP dans ces vues, même si elles tombent dans la
    fenêtre de dates."""
    period = request.args.get("period", "all")
    if period not in PERIODS:
        period = "all"

    cutoff = period_cutoff(period)

    query = (
        db.session.query(
            User.id,
            User.username,
            User.avatar,
            User.total_xp,
            func.sum(Attempt.earned_xp).label("period_xp"),
            func.count(Attempt.id).label("total"),
            func.sum(db.case((Attempt.is_correct, 1), else_=0)).label("correct"),
        )
        .join(Attempt, Attempt.user_id == User.id)
    )
    if cutoff is not None:
        query = query.filter(Attempt.answered_at >= cutoff)
    query = query.group_by(User.id)
    query = query.order_by(User.total_xp.desc() if period == "all" else func.sum(Attempt.earned_xp).desc())

    results = query.all()

    leaderboard_entries = []
    for result in results:
        level_info = calculate_level(result.total_xp)
        display_xp = result.total_xp if period == "all" else (result.period_xp or 0)

        friendship_status = None
        if current_user.is_authenticated and current_user.id != result.id:
            friendship = get_friendship_between(current_user.id, result.id)
            if friendship is not None:
                friendship_status = friendship.status

        leaderboard_entries.append(
                {
                    "user_id": result.id,
                    "username": result.username,
                    "avatar": result.avatar,
                    "total_xp": display_xp,
                    "level": level_info["level"],
                    "xp_in_current_level": level_info["xp_in_current_level"],
                    "xp_for_next_level": level_info["xp_for_next_level"],
                    "total": result.total,
                    "correct": result.correct,
                    "friendship_status": friendship_status,
                    }
            )

    my_rank = None
    my_entry = None
    if current_user.is_authenticated:
        for index, entry in enumerate(leaderboard_entries, start=1):
            if entry["user_id"] == current_user.id:
                my_rank = index
                my_entry = entry
                break

    return render_template(
        "leaderboard/classement.html",
        results=leaderboard_entries,
        my_rank=my_rank,
        my_entry=my_entry,
        period=period,
    )
