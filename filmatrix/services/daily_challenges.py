"""Logique métier des défis quotidiens et de la série de connexion"""

import random
from datetime import date

from filmatrix.extensions import db
from filmatrix.models import DailyChallenge, Question, Tag 
from filmatrix.catalog_rarities import humanize_tag_name

CHALLENGE_TYPES = ["mode_count", "total_count", "streak_count", "saga_count"]

MODE_COUNT_TARGET = 5
TOTAL_COUNT_TARGET = 8
STREAK_COUNT_TARGET = 3
SAGA_COUNT_TARGET = 3

AVAILABLE_MODES = [
        "qcm", "vrai_faux", "citation", "emoji", "film_melange",
        "chronologie", "devinette", "devinette_affiche", "casting", "blindtest",
    ]

def get_or_create_daily_challenge(user) -> DailyChallenge:
    """Récupère le défi du jour d'un joueur ou en génère un nouveau s'il n'en a pas"""
    today = date.today()

    existing = DailyChallenge.query.filter_by(user_id=user.id, challenge_date=today).first()
    if existing is not None:
        return existing

    challenge_type = random.choice(CHALLENGE_TYPES)

    target_mode = None
    target_tag_id = None
    target_value = TOTAL_COUNT_TARGET

    if challenge_type == "mode_count":
        target_mode = random.choice(AVAILABLE_MODES)
        target_value = MODE_COUNT_TARGET
    elif challenge_type == "streak_count":
        target_value = STREAK_COUNT_TARGET
    elif challenge_type == "saga_count":
        saga_tags = Tag.query.filter_by(tag_type="saga").all()
        eligible_tags = [
                tag for tag in saga_tags
                if Question.query.filter(Question.tags.contains(tag)).count() >= SAGA_COUNT_TARGET
            ]
        if eligible_tags:
            chosen_tag = random.choice(eligible_tags)
            target_tag_id = chosen_tag.id
            target_value = SAGA_COUNT_TARGET
        else:
            # Pas assez de sagas avec suffisamment de questions : on retombe
            # sur un défi générique plutôt que de générer un objectif impossible.
            challenge_type = "total_count"
            target_value = TOTAL_COUNT_TARGET

    challenge = DailyChallenge(
                user_id=user.id,
                challenge_date=today,
                challenge_type=challenge_type,
                target_value=target_value,
                target_mode=target_mode,
                target_tag_id=target_tag_id,
                progress=0,
            )
    db.session.add(challenge)
    db.session.commit()
    return challenge

def update_challenge_progress(user, question: Question, is_correct: bool, current_run_streak: int = 0) -> DailyChallenge | None:
    """Met à jour la progression du défi du jour, si la réponse y contribue"""
    if not is_correct:
        return None

    challenge = get_or_create_daily_challenge(user)

    if challenge.completed_at is not None:
        return None

    contributes = False

    if challenge.challenge_type == "total_count":
        contributes = True
    elif challenge.challenge_type == "mode_count":
        contributes = question.mode == challenge.target_mode
    elif challenge.challenge_type == "saga_count":
        contributes = any(tag.id == challenge.target_tag_id for tag in question.tags)
    elif challenge.challenge_type == "streak_count":
        challenge.progress = current_run_streak
        contributes = False 

    if contributes:
        challenge.progress += 1

    just_completed = False
    if challenge.progress >= challenge.target_value and challenge.completed_at is None:
        challenge.completed_at = db.func.now()
        just_completed = True

    db.session.commit()

    return challenge if just_completed else None

STREAK_BONUS_THRESHOLD = 7

def update_streak_on_completion(user) -> bool:
    """Met à jour la série de connexion du joueur suite à un défi complété aujourd'hui, renvoie True si le palier de bonus (7 jours) vient d'être atteint.
    """
    today = date.today()

    if user.last_streak_date == today:
        # Le défi d'aujourd'hui a déjà mis à jour la série une première fois.
        return False

    yesterday = date.fromordinal(today.toordinal() - 1)

    if user.last_streak_date == yesterday:
        user.current_streak += 1
    else:
        user.current_streak = 1

    user.last_streak_date = today

    reached_bonus = user.current_streak > 0 and user.current_streak % STREAK_BONUS_THRESHOLD == 0

    return reached_bonus

CHALLENGE_LABELS = {
        "total_count": "Réponds correctement à {target} questions, tous modes confondus",
        "mode_count": "Réponds correctement à {target} question en mode {mode}",
        "streak_count": "Enchaîne {target} bonnes réponses d'affilée",
        "saga_count": "Réponds correctement à {target} questions sur {saga}",
    }

def describe_challenge(challenge: DailyChallenge) -> dict:
    """Prépare les informations d'un défi pour l'affichage"""
    mode_labels = {
        "qcm": "Quiz", "vrai_faux": "Vrai / Faux", "citation": "Citations",
        "emoji": "Emoji Quiz", "film_melange": "Film mélangé", "chronologie": "Chronologie",
        "devinette": "Devinette", "devinette_affiche": "Devinette-affiche",
        "casting": "Casting", "blindtest": "Blind Test",
    }

    template = CHALLENGE_LABELS.get(challenge.challenge_type, "Défi du jour")
    description = template.format(
            target=challenge.target_value,
            mode=mode_labels.get(challenge.target_mode, challenge.target_mode or ""),
            saga=humanize_tag_name(challenge.target_tag.name) if challenge.target_tag else "",
        )

    progress_ratio = min(challenge.progress / challenge.target_value, 1.0) if challenge.target_value else 0

    return {
        "description": description,
        "progress": challenge.progress,
        "target_value": challenge.target_value,
        "progress_percentage": round(progress_ratio * 100, 1),
        "is_completed": challenge.completed_at is not None,
        }