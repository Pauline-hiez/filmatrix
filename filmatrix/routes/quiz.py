"""Parties solo : préparation, déroulé et signalement d'une question."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.catalog import REPORT_REASON
from filmatrix.models import Attempt, Report
from filmatrix.game_modes import GAME_MODES, MIX_MODE_SLUG
from filmatrix.services.badges import BADGES, check_and_award_badges
from filmatrix.services.engine import check_answer, convert_answer, scramble_title
from filmatrix.services.levels import (
    BLINDTEST_DURATION,
    DEFAULT_LEVEL,
    LEVELS,
    coins_for_level,
    duration_for,
    resolve_level,
    xp_for_level,
)
from filmatrix.services.questions import (
    count_run_questions,
    draw_run_questions,
    find_question,
    format_correct_answer,
    mode_tags,
    mode_tags_for_type,
    playable_question_query,
    resolve_content_type,
    run_filters,
    shuffle_options,
)
from filmatrix.services.score import (
    QUESTIONS_PER_RUN,
    read_run,
    record_answer,
    run_length,
    start_run,
)


bp = Blueprint("quiz", __name__)


@bp.route("/quiz/<mode>")
def quiz_setup(mode: str) -> str:
    """Écran de préparation : le joueur règle sa partie avant de la lancer

    C'est le seul point d'entrée vers une partie. Tant qu'il n'a pas cliqué
    sur Commencer, aucun chrono ne tourne"""
    mode_info = next((entry for entry in GAME_MODES if entry["slug"] == mode), None)

    if mode_info is None:
        return redirect(url_for("main.modes"))

    # On ne propose que les thèmes qui ont au moins une question dans ce mode
    # et qui comptent assez de questions pour valoir la peine d'être proposés
    # (cf. TAG_MIN_QUESTIONS dans services/questions.py). La liste complète
    # des univers reste disponible à part, pour le lien qui les révèle tous.
    available_tags = mode_tags(mode)
    all_univers_tags = mode_tags_for_type(mode, "univers")

    content_type = resolve_content_type(request.args.get("content_type"))
    selected_tag_ids = request.args.getlist("tag_id", type=int)

    # Le compteur doit refléter le filtre : sinon le bouton reste actif
    # alors que la sélection films / séries ne renvoie aucune question. Il
    # ne compte que le jouable : un visiteur ne doit pas se voir promettre
    # des questions réservées aux comptes.
    available = playable_question_query(
        mode, content_type=content_type, tag_ids=selected_tag_ids
    ).count()

    return render_template(
            "quiz/preparation.html",
            mode=mode_info,
            question_count=available,
            run_length=min(QUESTIONS_PER_RUN, available),
            content_type=content_type,
            selected_tag_ids=selected_tag_ids,
            all_tags=available_tags,
            all_univers_tags=all_univers_tags,
            levels=LEVELS,
            default_level=DEFAULT_LEVEL,
            blindtest_duration=BLINDTEST_DURATION,
        )

@bp.route("/quiz/<mode>/disponibilite")
def quiz_availability(mode: str) -> dict:
    """Renvoie le nombre de questions disponibles pour un mode et ses filtres

    Appelé par quiz_setup.js à chaque changement de filtre sur l'écran de
    préparation, pour tenir le compteur à jour sans recharger la page."""
    content_type = resolve_content_type(request.args.get("content_type"))
    tag_ids = request.args.getlist("tag_id", type=int)

    available = playable_question_query(mode, content_type=content_type, tag_ids=tag_ids).count()

    return {"available": available, "run_length": min(QUESTIONS_PER_RUN, available)}

@bp.route("/quiz/<mode>/<int:position>", methods=["GET", "POST"])
def quiz(mode: str, position: int) -> str:
    """Affiche une question (GET) ou traite la réponse envoyée (POST)."""
    tag_ids = request.args.getlist("tag_id", type=int)
    content_type = resolve_content_type(request.args.get("content_type"))
    level = resolve_level(request.args.get("level"))

    # Le tirage doit précéder la recherche de la question : c'est lui qui
    # décide quelle question occupe la position 1.
    if request.method == "GET" and position == 1:
        start_run(
            session,
            mode,
            question_ids=draw_run_questions(mode, content_type=content_type, tag_ids=tag_ids),
            filters=run_filters(content_type=content_type, tag_ids=tag_ids),
        )

    question = find_question(mode, position, content_type=content_type, tag_ids=tag_ids)

    if question is None:
        return render_template("quiz/termine.html", score=read_run(session, mode))

    # Le tirage de la partie en cours fait foi ; à défaut — lien direct,
    # session expirée — on retombe sur ce que les filtres permettent.
    total_questions = run_length(
        session, mode, run_filters(content_type=content_type, tag_ids=tag_ids)
    ) or count_run_questions(mode, content_type=content_type, tag_ids=tag_ids)

    if question.requires_account and not current_user.is_authenticated:
        flash("Connecte-toi pour accéder à cette question.")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        is_timeout = request.form.get("timeout") == "true"

        if is_timeout:
            is_correct = False
        else:
            raw_answer = request.form["answer"]
            player_answer = convert_answer(question.mode, raw_answer)
            is_correct = check_answer(question, player_answer)

        if question.mode == "devinette" and not is_correct:
            hint_index = int(request.form.get("hint_index", 0))
            hints = question.payload["hints"]

            if hint_index < len(hints) - 1:
                return {
                    "is_correct": False,
                    "give_up": False,
                    "next_hint": hints[hint_index + 1],
                    "was_timeout": is_timeout,
                }

        new_badges = []
        earned_xp = 0
        earned_coins = 0

        if current_user.is_authenticated:
            already_answered_correctly = Attempt.query.filter_by(
                user_id=current_user.id,
                question_id=question.id,
                is_correct=True,
            ).first() is not None

            attempt = Attempt(
                user_id=current_user.id,
                question_id=question.id,
                is_correct=is_correct,
            )
            db.session.add(attempt)

            if is_correct and not already_answered_correctly:
                earned_xp = xp_for_level(level)
                earned_coins = coins_for_level(level)
                current_user.total_xp += earned_xp
                current_user.coins += earned_coins

            db.session.commit()

            new_badge_codes = check_and_award_badges(current_user)
            db.session.commit()

            new_badges = [BADGES[code] for code in new_badge_codes]

        correct_answer_text = None if is_correct else format_correct_answer(question)

        record_answer(session, mode, question.id, is_correct, earned_xp, earned_coins)

        if question.mode == "chronologie":
            correct_order = question.correct_answer["order"]
            if is_timeout:
                position_results = [False] * len(correct_order)
            else:
                position_results = [
                    player_answer[i] == correct_order[i]
                    for i in range(len(correct_order))
                ]
            return {
                "is_correct": is_correct,
                "position_results": position_results,
                "give_up": True,
                "new_badges": new_badges,
                "correct_answer": correct_answer_text,
            }

        return {
            "is_correct": is_correct,
            "give_up": True,
            "new_badges": new_badges,
            "correct_answer": correct_answer_text,
        }

    scrambled_title = None
    if question.mode == "film_melange":
        scrambled_title = scramble_title(question.correct_answer["title"])

    options = shuffle_options(question) if question.mode == "qcm" else None

    return render_template(
            "quiz/question.html",
            question=question,
            scrambled_title=scrambled_title,
            options=options,
            report_reasons=REPORT_REASON,
            level=LEVELS[level],
            duration=duration_for(level, question.mode),
            position=position,
            total_questions=total_questions,
            is_mix=mode == MIX_MODE_SLUG,
        )

@bp.route("/signaler/<int:question_id>", methods=["POST"])
@login_required
def report_question(question_id: int) -> str:
    """Enregistre un signalement sur une question"""
    reason = request.form.get("reason", "other")

    report = Report(
            user_id=current_user.id,
            question_id=question_id,
            reason=reason,
        )
    db.session.add(report)
    db.session.commit()

    return {"success": True}
