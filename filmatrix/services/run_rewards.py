"""Application groupée des récompenses d'une partie solo, une fois qu'elle
est effectivement terminée.

Pendant la partie, filmatrix/routes/quiz.py ne fait que mettre en file dans
la session (voir services/score.py : queue_pending_attempt,
queue_fragment_candidate) - rien n'est écrit en base tant que le joueur n'a
pas atteint la fin. Ce module fait le travail inverse : relire ce qui a été
mis en file et l'appliquer d'un coup à la base, la seule et unique fois où
une partie se termine réellement. Une partie abandonnée ne passe jamais par
ici, et ne laisse donc rien derrière elle.
"""

from datetime import datetime, timedelta

from flask import url_for

from filmatrix.extensions import db
from filmatrix.models import Attempt, Question
from filmatrix.services.badges import BADGES, check_and_award_badges
from filmatrix.services.collection import (
    award_fragment_for_question,
    award_guaranteed_fragment,
    fragment_result_payload,
)
from filmatrix.services.daily_challenges import (
    MISSION_COIN_REWARD,
    describe_challenge,
    update_missions_progress,
    update_streak_on_completion,
)
from filmatrix.services.levels import calculate_level
from filmatrix.services.notifications import create_notification
from filmatrix.services.score import SESSION_KEY, add_run_fragment_result, mark_run_finalized
from filmatrix.special_games import CORRECT_ANSWERS_PER_TICKET


def finalize_run_rewards(user, store, mode: str) -> None:
    """Applique d'un coup, à la base, tout ce qu'une partie terminée a
    accumulé en session : XP, pièces, bonnes réponses, tickets d'or,
    fragments, mini-missions, série de connexion et badges.

    Ne fait rien (et reste sûr à rappeler plusieurs fois) si la partie n'a
    pas déjà été mise en file pour ce mode, ou a déjà été finalisée."""
    run = store.get(SESSION_KEY)
    if run is None or run.get("mode") != mode or run.get("finalized"):
        return

    pending = run.get("pending_attempts", [])
    if not pending:
        mark_run_finalized(store, mode)
        return

    before_xp = user.total_xp
    before_correct = user.total_correct_answers
    previous_level = calculate_level(before_xp)["level"]

    # Un horodatage par entrée, décalé d'une microseconde : check_and_award_badges
    # trie les Attempt par answered_at pour "5 d'affilée" - les créer tous au
    # même instant (résolution de certaines horloges) casserait cet ordre.
    base_timestamp = datetime.utcnow()
    for index, event in enumerate(pending):
        db.session.add(
            Attempt(
                user_id=user.id,
                question_id=event["question_id"],
                is_correct=event["is_correct"],
                earned_xp=event["earned_xp"],
                answered_at=base_timestamp + timedelta(microseconds=index),
            )
        )

    user.total_xp += run.get("xp", 0)
    user.coins += run.get("coins", 0)
    user.total_correct_answers += run.get("correct", 0)

    # Une partie peut désormais franchir plusieurs paliers de ticket d'or
    # d'un coup (ex. une longue partie très réussie) - impossible avec
    # l'ancien système question par question, qui n'en croisait jamais
    # plus d'un à la fois.
    tickets_from_volume = (
        user.total_correct_answers // CORRECT_ANSWERS_PER_TICKET
        - before_correct // CORRECT_ANSWERS_PER_TICKET
    )
    if tickets_from_volume > 0:
        user.golden_tickets += tickets_from_volume

    new_level = calculate_level(user.total_xp)["level"]
    level_up = {"previous": previous_level, "new": new_level} if new_level > previous_level else None

    db.session.commit()

    if tickets_from_volume > 0:
        create_notification(
            user,
            f"🎟️ Tu as gagné un Ticket d'Or pour tes {user.total_correct_answers} bonnes réponses !",
            link=url_for("special_games.hub"),
        )

    # Fragment personnel : le premier candidat qui aboutit réellement (un
    # candidat peut échouer si tous les personnages des albums concernés
    # sont déjà débloqués) - un seul par partie, comme avant.
    for candidate in run.get("fragment_candidates", []):
        candidate_question = Question.query.get(candidate["question_id"])
        if candidate_question is None:
            continue
        result = award_fragment_for_question(
            user, candidate_question, character_name=candidate["character_name"]
        )
        if result is not None:
            add_run_fragment_result(store, mode, fragment_result_payload(user, result))
            break

    # Rejeu des mini-missions dans l'ordre où les questions ont été
    # répondues : update_missions_progress() est déjà sans effet sur une
    # mauvaise réponse, inutile de filtrer avant de l'appeler.
    completed_missions = []
    day_just_completed = False
    for event in pending:
        mission_question = Question.query.get(event["question_id"])
        if mission_question is None:
            continue
        newly_completed, day_flag = update_missions_progress(
            user, mission_question, event["is_correct"], current_run_streak=event["current_run_streak"]
        )
        completed_missions.extend(newly_completed)
        day_just_completed = day_just_completed or day_flag

    if completed_missions:
        user.coins += MISSION_COIN_REWARD * len(completed_missions)

    reached_streak_bonus = False
    if day_just_completed:
        day_completed_fragment = award_guaranteed_fragment(user)
        if day_completed_fragment is not None:
            add_run_fragment_result(store, mode, fragment_result_payload(user, day_completed_fragment))

        reached_streak_bonus = update_streak_on_completion(user)
        if reached_streak_bonus:
            streak_bonus_fragment = award_guaranteed_fragment(
                user, minimum_rarity=["rare", "epique", "legendaire", "mythique"]
            )
            if streak_bonus_fragment is not None:
                add_run_fragment_result(store, mode, fragment_result_payload(user, streak_bonus_fragment))
            # Ressource des Jeux Spéciaux (filmatrix/special_games.py) : même
            # palier que le fragment rare garanti ci-dessus, pour un rythme
            # hebdomadaire naturel sans nouveau système de mission dédié.
            user.golden_tickets += 1

    new_badge_codes = check_and_award_badges(user)

    db.session.commit()

    if reached_streak_bonus:
        create_notification(
            user,
            "🎟️ Tu as gagné un Ticket d'Or pour ta série de connexion !",
            link=url_for("special_games.hub"),
        )

    run = store.get(SESSION_KEY)
    if run is not None and run.get("mode") == mode:
        run["reveal"] = {
            "level_up": level_up,
            "new_badges": [BADGES[code] for code in new_badge_codes],
            "completed_missions": [describe_challenge(mission) for mission in completed_missions],
            "day_completed": day_just_completed,
            "streak_bonus": {"streak": user.current_streak} if reached_streak_bonus else None,
        }
        run["finalized"] = True
        store[SESSION_KEY] = run
