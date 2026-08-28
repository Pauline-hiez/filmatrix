"""Accueil et catalogue des modes de jeu."""

from flask import Blueprint, render_template, request, session
from flask_login import current_user
from sqlalchemy import func

from filmatrix.extensions import db
from filmatrix.models import Attempt, Question, User
from filmatrix.game_modes import GAME_MODES
from filmatrix.services.levels import calculate_level
from filmatrix.services.questions import resolve_content_type
from filmatrix.services.score import QUESTIONS_PER_RUN


bp = Blueprint("main", __name__)


@bp.route("/")
def home() -> str:
    """Page d'accueil : vitrine des modes de jeu, progression et classement"""
    question_counts = dict(
        db.session.query(Question.mode, func.count(Question.id))
        .group_by(Question.mode)
        .all()
    )

    # On n'affiche que les modes qui ont au moins une question en base,
    # pour ne pas envoyer le joueur vers un mode vide.
    playable_modes = [
        dict(mode, question_count=question_counts.get(mode["slug"], 0))
        for mode in GAME_MODES
        if question_counts.get(mode["slug"], 0) > 0
    ]

    top_players = User.query.order_by(User.total_xp.desc()).limit(5).all()

    level_info = None
    correct_count = 0
    if current_user.is_authenticated:
        level_info = calculate_level(current_user.total_xp)
        correct_count = Attempt.query.filter_by(
            user_id=current_user.id, is_correct=True
        ).count()

    return render_template(
        "main/accueil.html",
        modes=playable_modes,
        top_players=top_players,
        level_info=level_info,
        correct_count=correct_count,
        total_questions=sum(question_counts.values()),
        total_players=User.query.count(),
    )

@bp.route("/modes")
def modes() -> str:
    """Affiche la liste des modes de jeu disponibles

    Le sélecteur films / séries ne filtre pas la grille (tous les modes
    restent jouables) : il suit le joueur jusqu'à l'écran de préparation."""
    return render_template(
        "main/modes.html",
        modes=GAME_MODES,
        content_type=resolve_content_type(request.args.get("content_type")),
        questions_per_run=QUESTIONS_PER_RUN,
    )
