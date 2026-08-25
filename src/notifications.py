"""Fonctions utilitaires pour créer et gérer les notifications."""

from src.database import db
from src.models import Notification


def create_notification(user, message: str, link: str | None = None) -> None:
    """Crée une notification pour un utilisateur donné et l'envoie en temps réel.

    La notification est enregistrée avant d'être émise : si le commit échoue,
    aucun évènement n'est envoyé, et le client qui recharge la liste au clic
    retrouve bien la notification en base.
    """
    notification = Notification(user_id=user.id, message=message, link=link)
    db.session.add(notification)
    db.session.commit()

    from app import socketio

    socketio.emit(
        "new_notification",
        {"message": message, "link": link},
        room=f"user_{user.id}",
    )


def get_unread_count(user_id: int) -> int:
    """Renvoie le nombre de notifications non lues d'un utilisateur."""
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def mark_all_as_read(user_id: int) -> None:
    """Marque toutes les notifications d'un utilisateur comme lues."""
    Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})