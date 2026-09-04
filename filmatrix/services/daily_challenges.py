"""Logique métier des mini-missions quotidiennes et de la série de connexion"""

import random
from datetime import date

from flask import url_for

from filmatrix.extensions import db
from filmatrix.models import DailyChallenge, Question, Tag
from filmatrix.catalog_rarities import humanize_tag_name
from filmatrix.game_modes import GAME_MODES, MIX_MODE_SLUG

CHALLENGE_TYPES = ["mode_count", "total_count", "streak_count", "saga_count"]

# Trois mini-missions par jour plutôt qu'un défi unique : des objectifs plus
# courts, sur des critères différents (voir _generate_missions, qui pioche 3
# types distincts parmi les 4 disponibles pour garantir la variété). Les
# cibles sont donc plus petites qu'à l'époque du défi unique : l'effort total
# d'une journée reste comparable, réparti sur plusieurs petites missions au
# lieu d'une seule plus longue.
MISSIONS_PER_DAY = 3

MODE_COUNT_TARGET = 3
TOTAL_COUNT_TARGET = 5
STREAK_COUNT_TARGET = 3
SAGA_COUNT_TARGET = 3

# Pièces données pour CHAQUE mini-mission complétée. Le fragment garanti et
# l'avancée de la série de connexion, eux, n'arrivent que quand les trois
# missions du jour sont toutes complétées (voir day_reward_for_completion et
# filmatrix/routes/quiz.py) : la journée entière reste la vraie récompense,
# les pièces sont juste un petit à-côté par étape.
MISSION_COIN_REWARD = 15

AVAILABLE_MODES = [
        "qcm", "vrai_faux", "citation", "emoji", "film_melange",
        "chronologie", "devinette", "devinette_affiche", "casting", "blindtest",
    ]

def _daily_random(today: date) -> random.Random:
    """RNG déterministe pour une date donnée : le même tirage pour tout le
    monde. Chaque joueur garde ses propres lignes DailyChallenge (progression,
    complétion lui sont propres), mais avec des paramètres identiques —
    ce sont bien les mêmes mini-missions pour tous, pas un tirage indépendant
    par joueur."""
    return random.Random(today.toordinal())


def _build_mission_spec(challenge_type: str, rng: random.Random) -> dict:
    """Calcule mode/saga/objectif ciblés pour un type de mission donné.

    Séparé de la génération du jour pour rester appelable une fois par type
    choisi, sans dupliquer la logique par mission."""
    target_mode = None
    target_tag_id = None
    target_value = TOTAL_COUNT_TARGET

    if challenge_type == "mode_count":
        target_mode = rng.choice(AVAILABLE_MODES)
        target_value = MODE_COUNT_TARGET
    elif challenge_type == "streak_count":
        target_value = STREAK_COUNT_TARGET
    elif challenge_type == "saga_count":
        # Tri explicite : la liste doit être dans le même ordre pour tout le
        # monde, sinon le même index de rng.choice désignerait une saga
        # différente selon l'ordre renvoyé par la base.
        saga_tags = Tag.query.filter_by(tag_type="univers").order_by(Tag.id).all()
        eligible_tags = [
                tag for tag in saga_tags
                if Question.query.filter(Question.tags.contains(tag)).count() >= SAGA_COUNT_TARGET
            ]
        if eligible_tags:
            chosen_tag = rng.choice(eligible_tags)
            target_tag_id = chosen_tag.id
            target_value = SAGA_COUNT_TARGET
        else:
            # Pas assez de sagas avec suffisamment de questions : on retombe
            # sur une mission générique plutôt que de générer un objectif
            # impossible.
            challenge_type = "total_count"
            target_value = TOTAL_COUNT_TARGET

    return {
        "challenge_type": challenge_type,
        "target_mode": target_mode,
        "target_tag_id": target_tag_id,
        "target_value": target_value,
    }


def get_or_create_daily_missions(user) -> list[DailyChallenge]:
    """Récupère les mini-missions du jour d'un joueur, ou les génère si absentes.

    Les paramètres des missions (type, mode ou saga ciblée, objectif) sont
    les mêmes pour tous les joueurs un jour donné : voir _daily_random."""
    today = date.today()

    existing = (
        DailyChallenge.query.filter_by(user_id=user.id, challenge_date=today)
        .order_by(DailyChallenge.slot)
        .all()
    )
    if len(existing) >= MISSIONS_PER_DAY:
        return existing[:MISSIONS_PER_DAY]

    rng = _daily_random(today)
    # 3 types distincts parmi les 4 disponibles : jamais deux missions sur le
    # même critère le même jour (ex. deux fois "total_count"), qui feraient
    # doublon plutôt que d'apporter de la variété.
    chosen_types = rng.sample(CHALLENGE_TYPES, MISSIONS_PER_DAY)

    missions = []
    for slot, challenge_type in enumerate(chosen_types):
        spec = _build_mission_spec(challenge_type, rng)
        mission = DailyChallenge(
            user_id=user.id,
            challenge_date=today,
            slot=slot,
            challenge_type=spec["challenge_type"],
            target_value=spec["target_value"],
            target_mode=spec["target_mode"],
            target_tag_id=spec["target_tag_id"],
            progress=0,
        )
        db.session.add(mission)
        missions.append(mission)

    db.session.commit()
    return missions


def _mission_contributes(mission: DailyChallenge, question: Question) -> bool:
    """Indique si cette question fait progresser cette mission (hors streak_count,
    qui ne s'incrémente pas mais reflète directement la série en cours)."""
    if mission.challenge_type == "total_count":
        return True
    if mission.challenge_type == "mode_count":
        return question.mode == mission.target_mode
    if mission.challenge_type == "saga_count":
        return any(tag.id == mission.target_tag_id for tag in question.tags)
    return False


def update_missions_progress(
    user, question: Question, is_correct: bool, current_run_streak: int = 0
) -> tuple[list[DailyChallenge], bool]:
    """Met à jour la progression des mini-missions du jour pour cette réponse.

    Renvoie (missions_venant_d_etre_completees, journee_venant_d_etre_complete).
    Une réponse peut compléter plusieurs missions à la fois (ex. la dernière
    bonne réponse qui finit à la fois la mission de mode et le total). La
    série de connexion et le fragment garanti, eux, ne comptent que le
    passage de "pas toutes complétées" à "toutes complétées" : voir
    filmatrix/routes/quiz.py.
    """
    if not is_correct:
        return [], False

    missions = get_or_create_daily_missions(user)
    was_all_completed = all(mission.completed_at is not None for mission in missions)

    newly_completed = []
    for mission in missions:
        if mission.completed_at is not None:
            continue

        if mission.challenge_type == "streak_count":
            mission.progress = current_run_streak
        elif _mission_contributes(mission, question):
            mission.progress += 1

        if mission.progress >= mission.target_value and mission.completed_at is None:
            mission.completed_at = db.func.now()
            newly_completed.append(mission)

    db.session.commit()

    is_all_completed_now = all(mission.completed_at is not None for mission in missions)
    day_just_completed = is_all_completed_now and not was_all_completed

    return newly_completed, day_just_completed


STREAK_BONUS_THRESHOLD = 7

def update_streak_on_completion(user) -> bool:
    """Met à jour la série de connexion du joueur suite à une journée de
    mini-missions complétée, renvoie True si le palier de bonus (7 jours)
    vient d'être atteint.
    """
    today = date.today()

    if user.last_streak_date == today:
        # La journée a déjà mis à jour la série une première fois.
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

# Glyphe du mode ciblé (même source que le catalogue des modes, GAME_MODES)
# pour une mission mode_count ; un glyphe générique par type sinon.
_MODE_ICON_BY_SLUG = {entry["slug"]: entry["icon"] for entry in GAME_MODES}
CHALLENGE_TYPE_ICONS = {
    "total_count": "🎯",
    "streak_count": "⚡",
    "saga_count": "🎬",
}


def challenge_icon(challenge: DailyChallenge) -> str:
    """Icône représentant cette mission : celle du mode ciblé pour mode_count,
    un glyphe générique par type sinon."""
    if challenge.challenge_type == "mode_count":
        return _MODE_ICON_BY_SLUG.get(challenge.target_mode, "🎯")
    return CHALLENGE_TYPE_ICONS.get(challenge.challenge_type, "🎯")


def challenge_play_url(challenge: DailyChallenge) -> str:
    """URL qui lance directement une partie couvrant cette mission, sans
    repasser par l'écran de préparation : le mode ciblé pour mode_count, le
    mode mixte filtré sur la saga ciblée pour saga_count (le filtre restreint
    tout le tirage à cette saga, garantissant qu'il y a bien assez de
    questions puisque la mission n'a pu choisir qu'une saga déjà vérifiée
    éligible), le mode mixte sans filtre pour les autres types."""
    if challenge.challenge_type == "mode_count" and challenge.target_mode:
        return url_for("quiz.quiz", mode=challenge.target_mode, position=1)
    if challenge.challenge_type == "saga_count" and challenge.target_tag_id:
        return url_for("quiz.quiz", mode=MIX_MODE_SLUG, position=1, tag_id=challenge.target_tag_id)
    return url_for("quiz.quiz", mode=MIX_MODE_SLUG, position=1)


def describe_challenge(challenge: DailyChallenge) -> dict:
    """Prépare les informations d'une mini-mission pour l'affichage"""
    mode_labels = {
        "qcm": "Quiz", "vrai_faux": "Vrai / Faux", "citation": "Citations",
        "emoji": "Emoji Quiz", "film_melange": "Film mélangé", "chronologie": "Chronologie",
        "devinette": "Devinette", "devinette_affiche": "Devinette-affiche",
        "casting": "Casting", "blindtest": "Blind Test",
    }

    template = CHALLENGE_LABELS.get(challenge.challenge_type, "Mini-mission")
    description = template.format(
            target=challenge.target_value,
            mode=mode_labels.get(challenge.target_mode, challenge.target_mode or ""),
            saga=humanize_tag_name(challenge.target_tag.name) if challenge.target_tag else "",
        )

    progress_ratio = min(challenge.progress / challenge.target_value, 1.0) if challenge.target_value else 0

    return {
        "description": description,
        "icon": challenge_icon(challenge),
        "play_url": challenge_play_url(challenge),
        "progress": challenge.progress,
        "target_value": challenge.target_value,
        "progress_percentage": round(progress_ratio * 100, 1),
        "is_completed": challenge.completed_at is not None,
        "coin_reward": MISSION_COIN_REWARD,
        }


def describe_daily_missions(user) -> dict:
    """Vue d'ensemble des mini-missions du jour d'un joueur : la liste
    décrite de chacune, et l'état global (toutes complétées ou non)."""
    missions = get_or_create_daily_missions(user)
    described = [describe_challenge(mission) for mission in missions]
    return {
        "missions": described,
        "completed_count": sum(1 for mission in described if mission["is_completed"]),
        "total_count": len(described),
        "all_completed": all(mission["is_completed"] for mission in described),
    }
