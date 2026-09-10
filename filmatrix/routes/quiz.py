"""Parties solo : préparation, déroulé et signalement d'une question."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.catalog import REPORT_REASON
from filmatrix.models import Attempt, Report, Tag, User
from filmatrix.game_modes import GAME_MODES, MIX_MODE_SLUG
from filmatrix.services.character_answers import character_answer
from filmatrix.services.engine import check_answer, convert_answer, scramble_title
from filmatrix.services.friends import friend_cards, get_friends_list
from filmatrix.services.run_rewards import finalize_run_rewards
from filmatrix.services.levels import (
    LEVELS,
    calculate_level,
    coins_for_level,
    duration_for,
    resolve_level,
    xp_for_level,
)
from filmatrix.services.questions import (
    count_run_questions,
    draw_run_questions,
    find_question,
    answer_placeholder,
    content_label,
    format_correct_answer,
    question_image_url,
    mode_tags,
    question_display_prompt,
    mode_tags_for_type,
    playable_question_query,
    reachable_content_types,
    reachable_tag_ids,
    resolve_content_type,
    resolve_difficulty_filter,
    run_filters,
    shuffle_options,
)
from filmatrix.services.score import (
    GUEST_PREVIEW_LENGTH,
    QUESTIONS_PER_RUN,
    RUN_LENGTH_PRESETS,
    queue_fragment_candidate,
    queue_pending_attempt,
    read_run,
    read_run_fragment_results,
    read_run_reveal,
    record_answer,
    resolve_run_length,
    run_length,
    start_run,
)


bp = Blueprint("quiz", __name__)


def _effective_run_length(raw_value: str | int | None) -> int:
    """Résout la longueur de partie demandée, plafonnée pour un visiteur

    Un visiteur non connecté peut choisir n'importe quel format en
    manipulant l'URL : le plafond doit donc s'appliquer ici, pas seulement
    être suggéré par l'écran de préparation."""
    chosen = resolve_run_length(raw_value)
    if not current_user.is_authenticated:
        return min(chosen, GUEST_PREVIEW_LENGTH)
    return chosen


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
    difficulty = resolve_difficulty_filter(request.args.get("difficulty"))
    chosen_run_length = _effective_run_length(request.args.get("questions"))

    # Ces modes reposent sur un média ou une représentation qui n'est pas
    # compatible avec un univers filtré. On bascule vers le QCM plutôt que de
    # laisser l'utilisateur préparer une partie qui ne pourra pas être servie.
    incompatible_universe_modes = {"devinette_affiche", "casting", "emoji", "blindtest", "film_melange"}
    has_selected_universe = bool(
        selected_tag_ids
        and any(tag.id in selected_tag_ids for tag in all_univers_tags)
    )
    if has_selected_universe and mode in incompatible_universe_modes:
        params = {"content_type": content_type or None}
        params["tag_id"] = selected_tag_ids
        return redirect(url_for("quiz.quiz_setup", mode="qcm", **params))

    # Le compteur doit refléter le filtre : sinon le bouton reste actif
    # alors que la sélection films / séries ne renvoie aucune question. Il
    # ne compte que le jouable : un visiteur ne doit pas se voir promettre
    # des questions réservées aux comptes.
    available = playable_question_query(
        mode, content_type=content_type, tag_ids=selected_tag_ids, difficulty=difficulty
    ).count()

    # Un visiteur non connecté n'a qu'un seul format possible (l'aperçu) : pas
    # la peine de lui proposer un choix entre trois durées qui aboutissent
    # toutes au même plafond.
    displayed_presets = (
        RUN_LENGTH_PRESETS
        if current_user.is_authenticated
        else {GUEST_PREVIEW_LENGTH: "Aperçu"}
    )

    return render_template(
            "quiz/preparation.html",
            mode=mode_info,
            all_modes=GAME_MODES,
            question_count=available,
            run_length=min(chosen_run_length, available),
            run_length_presets=displayed_presets,
            chosen_run_length=chosen_run_length,
            content_type=content_type,
            selected_tag_ids=selected_tag_ids,
            all_tags=available_tags,
            all_univers_tags=all_univers_tags,
            levels=LEVELS,
            difficulty=difficulty,
            mode_duration=duration_for(mode),
        )

@bp.route("/quiz/<mode>/disponibilite")
def quiz_availability(mode: str) -> dict:
    """Renvoie le nombre de questions disponibles pour un mode et ses filtres,
    ainsi que les options des sélecteurs qui resteraient utiles

    Appelé par quiz_setup.js à chaque changement de filtre sur l'écran de
    préparation, pour tenir le compteur à jour et désactiver les options qui
    mèneraient à zéro question, sans recharger la page."""
    content_type = resolve_content_type(request.args.get("content_type"))
    tag_ids = request.args.getlist("tag_id", type=int)
    difficulty = resolve_difficulty_filter(request.args.get("difficulty"))
    chosen_run_length = _effective_run_length(request.args.get("questions"))

    available = playable_question_query(mode, content_type=content_type, tag_ids=tag_ids, difficulty=difficulty).count()
    default_reachable, reachable_by_type = reachable_tag_ids(mode, content_type, tag_ids, difficulty=difficulty)

    return {
        "available": available,
        "run_length": min(chosen_run_length, available),
        "default_reachable_tag_ids": default_reachable,
        "reachable_tag_ids_by_type": reachable_by_type,
        "reachable_content_types": reachable_content_types(mode, tag_ids, difficulty=difficulty),
    }

@bp.route("/quiz/<mode>/<int:position>", methods=["GET", "POST"])
def quiz(mode: str, position: int) -> str:
    """Affiche une question (GET) ou traite la réponse envoyée (POST)."""
    tag_ids = request.args.getlist("tag_id", type=int)
    content_type = resolve_content_type(request.args.get("content_type"))
    difficulty = resolve_difficulty_filter(request.args.get("difficulty"))
    chosen_run_length = _effective_run_length(request.args.get("questions"))

    # Le tirage doit précéder la recherche de la question : c'est lui qui
    # décide quelle question occupe la position 1.
    if request.method == "GET" and position == 1:
        start_run(
            session,
            mode,
            question_ids=draw_run_questions(
                mode, content_type=content_type, tag_ids=tag_ids, difficulty=difficulty, total_questions=chosen_run_length
            ),
            filters=run_filters(content_type=content_type, tag_ids=tag_ids, difficulty=difficulty, total_questions=chosen_run_length),
        )

    question = find_question(
        mode, position, content_type=content_type, tag_ids=tag_ids, difficulty=difficulty, total_questions=chosen_run_length
    )

    if question is None:
        # Filet de sécurité : si la dernière réponse n'a pas pu finaliser la
        # partie (ex. lien direct vers cette position), ce GET s'en charge -
        # idempotent si finalize_run_rewards() a déjà tout appliqué.
        if current_user.is_authenticated:
            finalize_run_rewards(current_user, session, mode)
        return render_template(
            "quiz/termine.html",
            score=read_run(session, mode),
            fragment_results=read_run_fragment_results(session, mode),
            reveal=read_run_reveal(session, mode),
        )

    # Le tirage de la partie en cours fait foi ; à défaut — lien direct,
    # session expirée — on retombe sur ce que les filtres permettent.
    total_questions = run_length(
        session, mode, run_filters(content_type=content_type, tag_ids=tag_ids, difficulty=difficulty, total_questions=chosen_run_length)
    ) or count_run_questions(
        mode, content_type=content_type, tag_ids=tag_ids, difficulty=difficulty, total_questions=chosen_run_length
    )

    # Chaque question porte sa propre difficulté : c'est elle, pas un réglage
    # choisi par le joueur, qui fixe le chrono et les gains de CETTE question.
    question_difficulty = resolve_level(question.difficulty)

    selected_universe = (
        bool(tag_ids)
        and Tag.query.filter(
            Tag.id.in_(tag_ids), Tag.tag_type == "univers"
        ).first()
        is not None
    )
    character_mode = (
        selected_universe
        and question.mode == "citation"
        and character_answer(question) is not None
    )

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
            expected_answer = character_answer(question) if character_mode else None
            is_correct = check_answer(question, player_answer, expected_answer=expected_answer)

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

        earned_xp = 0
        earned_coins = 0
        already_answered_correctly = False

        if current_user.is_authenticated:
            already_answered_correctly = Attempt.query.filter_by(
                user_id=current_user.id,
                question_id=question.id,
                is_correct=True,
            ).first() is not None

            if is_correct and not already_answered_correctly:
                earned_xp = xp_for_level(question_difficulty)
                earned_coins = coins_for_level(question_difficulty)

        # record_answer doit s'exécuter avant la lecture de current_streak :
        # c'est lui qui met la série à jour avec la réponse qu'on vient de
        # traiter. La lire avant refléterait l'état d'avant cette réponse.
        was_new = record_answer(session, mode, question.id, is_correct, earned_xp, earned_coins)

        # Rien de ce qui est gagné pendant la partie n'est écrit en base tout
        # de suite : tout est mis en file ici (XP, pièces, Attempt, candidat
        # à un fragment) et appliqué d'un coup par finalize_run_rewards(),
        # seulement si la partie va jusqu'à son terme - une partie abandonnée
        # ne doit rien laisser derrière elle (voir services/run_rewards.py).
        if current_user.is_authenticated and was_new:
            current_run_streak = session.get("run", {}).get("current_streak", 0)
            queue_pending_attempt(session, mode, question.id, is_correct, earned_xp, current_run_streak)
            if is_correct and not already_answered_correctly:
                character_name = character_answer(question) if character_mode else None
                queue_fragment_candidate(session, mode, question.id, character_name)

            # La dernière question répondue déclenche la finalisation tout de
            # suite, plutôt que de dépendre uniquement du GET suivant qui
            # affiche termine.html : si l'onglet se ferme juste après cette
            # réponse, les récompenses sont déjà appliquées (ce GET reste
            # inoffensif à appeler ensuite, finalize_run_rewards() est
            # idempotente une fois la partie marquée finalisée).
            if position == total_questions:
                finalize_run_rewards(current_user, session, mode)

        correct_answer_text = None if is_correct else format_correct_answer(
            question,
            alternate_answer=character_answer(question) if character_mode else None,
        )

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
                "correct_answer": correct_answer_text,
            }

        return {
            "is_correct": is_correct,
            "give_up": True,
            "correct_answer": correct_answer_text,
        }

    scrambled_title = None
    if question.mode == "film_melange":
        scrambled_title = scramble_title(question.correct_answer["title"])

    options = shuffle_options(question) if question.mode == "qcm" else None

    sidebar_friends = []
    player_level = None
    player_rank = None
    if current_user.is_authenticated:
        sidebar_friends = friend_cards(get_friends_list(current_user.id))[:5]
        player_level = calculate_level(current_user.total_xp)
        player_rank = User.query.filter(User.total_xp > current_user.total_xp).count() + 1

    leaderboard_players = User.query.order_by(User.total_xp.desc()).limit(5).all()
    run_state = session.get("run", {})

    is_mix = mode == MIX_MODE_SLUG

    return render_template(
            "quiz/question.html",
            question=question,
            display_prompt=question_display_prompt(
                question, is_mix=is_mix, character_mode=character_mode
            ),
            answer_placeholder=answer_placeholder(
                question, is_mix=is_mix, character_mode=character_mode
            ),
            content_label=content_label(question),
            question_image_url=question_image_url(question),
            character_mode=character_mode,
            scrambled_title=scrambled_title,
            options=options,
            report_reasons=REPORT_REASON,
            difficulty=LEVELS[question_difficulty],
            duration=duration_for(question.mode),
            position=position,
            total_questions=total_questions,
            is_mix=is_mix,
            leaderboard_players=leaderboard_players,
            sidebar_friends=sidebar_friends,
            player_level=player_level,
            player_rank=player_rank,
            current_score=run_state.get("correct", 0),
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
