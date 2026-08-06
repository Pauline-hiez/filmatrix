"""Définition des badges et logique de déblocage"""

from src.database import db
from src.models import Attempt, Question, UserBadge

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
    """Attribue un badge à un utilisateur s'il ne l'a pas déjà"""
    if not has_badge(user, badge_code):
        new_badge = UserBadge(user_id=user.id, badge_code=badge_code)
        db.session.add(new_badge)

def check_and_award_badges(user) -> None:
    """Vérifie toutes les conditions de badges et attribue ceux récemment débloqués"""
    all_attempts = Attempt.query.filter_by(user_id=user.id).order_by(Attempt.answered_at).all()

    if len(all_attempts) >= 1:
        award_badge(user, "first_step")

    if len(all_attempts) >= 100:
        award_badge(user, "hudred_attempts")

    last_five = all_attempts[-5:]
    if len(last_five) == 5 and all(attempt.is_correct for attempt in last_five):
        award_badge(user, "five_in_a_row")

    from app import calculate_level
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