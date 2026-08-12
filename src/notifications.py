"""Fonctions utilitaires pour créer et gérer les notifications."""

from src.database import db
from src.models import Notification


def create_notification(user, message: str, link: str | None = None) -> None:
    """Crée une notification pour un utilisateur donné."""
    notification = Notification(user_id=user.id, message=message, link=link)
    db.session.add(notification)


def get_unread_count(user_id: int) -> int:
    """Renvoie le nombre de notifications non lues d'un utilisateur."""
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def mark_all_as_read(user_id: int) -> None:
    """Marque toutes les notifications d'un utilisateur comme lues."""
    Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})