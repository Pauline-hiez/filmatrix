"""Définition des badges et logique de déblocage"""

from filmatrix.services.levels import calculate_level
from filmatrix.models import Attempt, Question, UserBadge

BADGES = {
    "first_step": {
        "name": "Premier pas",
        "description": "Répondre à sa première question.",
        "icon": "🎬",
    },
    "five_in_a_row": {
        "name": "Sans faute",
        "description": "5 bonnes réponses d'affilée.",
        "icon": "🎯",
    },
    "hundred_attempts": {
        "name": "Cent réponses",
        "description": "Répondre à 100 questions au total.",
        "icon": "🧠",
    },
    "level_5": {
        "name": "Niveau 5",
        "description": "Atteindre le niveau 5.",
        "icon": "🏆",
    },
    "all_modes": {
        "name": "Polyvalent",
        "description": "Jouer à tous les modes de jeu au moins une fois.",
        "icon": "🎭",
    },
    "citation_expert": {
        "name": "Expert Citations",
        "description": "10 bonnes réponses en mode Citations.",
        "icon": "📚",
    },
}

def has_badge(user, badge_code: str) -> bool:
    """Vérifie si un utilisateur possède déjà un badge donné"""
    return any(badge.badge_code == badge_code for badge in user.badges)

def award_badge(user, badge_code: str) -> None:
    """Attribue un badge à un utilisateur, s'il ne l'a pas déjà."""
    if not has_badge(user, badge_code):
        new_badge = UserBadge(badge_code=badge_code)
        user.badges.append(new_badge)

def check_and_award_badges(user) -> list[str]:
    """Vérifie toutes les conditions de badges, attribue ceux nouvellement débloqués,
    et renvoie la liste des codes de badges tout juste obtenus."""
    badges_before = {badge.badge_code for badge in user.badges}

    all_attempts = Attempt.query.filter_by(user_id=user.id).order_by(Attempt.answered_at).all()

    if len(all_attempts) >= 1:
        award_badge(user, "first_step")

    if len(all_attempts) >= 100:
        award_badge(user, "hundred_attempts")

    last_five = all_attempts[-5:]
    if len(last_five) == 5 and all(attempt.is_correct for attempt in last_five):
        award_badge(user, "five_in_a_row")

    level_info = calculate_level(user.total_xp)
    if level_info["level"] >= 5:
        award_badge(user, "level_5")

    played_modes = {
        attempt.question.mode for attempt in all_attempts
    }

    all_available_modes = {question.mode for question in Question.query.all()}
    if all_available_modes and played_modes >= all_available_modes:
        award_badge(user, "all_modes")

    citation_correct_count = sum(
        1
        for attempt in all_attempts
        if attempt.is_correct and attempt.question.mode == "citation"
    )

    if citation_correct_count >= 10:
        award_badge(user, "citation_expert")

    badges_after = {badge.badge_code for badge in user.badges}
    return list(badges_after - badges_before)

def next_objective(user) -> dict | None:
    """Calcule la progression vers chaque badge non obtenu, et renvoie celui qui
    s'en approche le plus - le "prochain objectif" du profil. None si tous les
    badges sont déjà obtenus.

    Chaque ratio est calculé à partir des mêmes données que check_and_award_badges,
    pas d'un seuil générique : un badge n'a de sens qu'avec SA propre mesure
    (tentatives, streak courante, niveau, modes joués, citations correctes...)."""
    earned_codes = {badge.badge_code for badge in user.badges}
    remaining_codes = [code for code in BADGES if code not in earned_codes]
    if not remaining_codes:
        return None

    all_attempts = Attempt.query.filter_by(user_id=user.id).order_by(Attempt.answered_at).all()
    level_info = calculate_level(user.total_xp)
    played_modes = {attempt.question.mode for attempt in all_attempts}
    all_available_modes = {question.mode for question in Question.query.all()}

    citation_correct_count = sum(
        1
        for attempt in all_attempts
        if attempt.is_correct and attempt.question.mode == "citation"
    )

    current_streak_length = 0
    for attempt in reversed(all_attempts):
        if not attempt.is_correct:
            break
        current_streak_length += 1

    progress_by_code = {
        "first_step": (min(len(all_attempts), 1), 1),
        "hundred_attempts": (min(len(all_attempts), 100), 100),
        "five_in_a_row": (min(current_streak_length, 5), 5),
        "level_5": (min(level_info["level"], 5), 5),
        "all_modes": (len(played_modes & all_available_modes), len(all_available_modes) or 1),
        "citation_expert": (min(citation_correct_count, 10), 10),
    }

    best_code = max(
        remaining_codes,
        key=lambda code: progress_by_code[code][0] / progress_by_code[code][1],
    )
    current, target = progress_by_code[best_code]
    info = BADGES[best_code]

    return {
        "code": best_code,
        "name": info["name"],
        "description": info["description"],
        "icon": info["icon"],
        "current": current,
        "target": target,
        "percent": round(current / target * 100, 1),
        "remaining": max(target - current, 0),
    }