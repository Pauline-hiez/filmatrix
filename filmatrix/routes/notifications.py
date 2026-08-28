"""Consultation des notifications d'un joueur."""

from flask import Blueprint, session
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.models import Notification
from filmatrix.services.notifications import mark_all_as_read


bp = Blueprint("notifications", __name__)


@bp.route("/notifications")
@login_required
def get_notifications() -> dict:
    """Renvoie les notifications recentes de l'utilisateur et les marque comme lues"""
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(10)
        .all()
    )

    notifications_data = [
        {
            "message": notification.message,
            "link": notification.link,
            "is_read": notification.is_read,
        }
        for notification in notifications
    ]

    mark_all_as_read(current_user.id)
    db.session.commit()

    return {"notifications": notifications_data}
