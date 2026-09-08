"""Quota hebdomadaire des suggestions de questions par les joueurs."""

from datetime import datetime, timedelta

from filmatrix.models import QuestionSubmission

# Fenêtre glissante de 7 jours plutôt que calendaire : un joueur qui poste
# juste avant minuit dimanche ne doit pas pouvoir contourner la limite en
# repostant juste après.
WEEKLY_SUBMISSION_LIMIT = 3


def submissions_this_week(user) -> int:
    """Compte les suggestions envoyées par le joueur sur les 7 derniers jours

    Une suggestion refusée compte quand même dans le quota (décision
    produit) : elle n'est pas retirée du décompte une fois traitée."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    return QuestionSubmission.query.filter(
        QuestionSubmission.user_id == user.id,
        QuestionSubmission.created_at >= cutoff,
    ).count()


def remaining_weekly_quota(user) -> int:
    """Retourne le nombre de suggestions qu'il reste au joueur cette semaine"""
    return max(0, WEEKLY_SUBMISSION_LIMIT - submissions_this_week(user))
