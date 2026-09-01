"""Logique métier des défis quotidiens et de la série de connexion"""

import random
from datetime import date

from filmatrix.extensions import db
from filmatrix.models import DailyChallenge, Question, Tag 

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
                tag for tag in saga_tags if (Question.tags.contains(tag)).count() >= SAGA_COUNT_TARGET
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