"""Historique de la messagerie entre amis (l'envoi passe par Socket.IO, voir
filmatrix/realtime/events.py — ces routes ne servent qu'à peupler la bulle
et le fil au chargement d'une page, avant même que la connexion temps réel
ne soit établie)."""

from flask import Blueprint, url_for
from flask_login import current_user, login_required

from filmatrix.catalog import DEFAULT_AVATAR
from filmatrix.models import User
from filmatrix.services.chat import (
    get_conversation,
    list_conversations,
    mark_conversation_read,
    unread_total,
)
from filmatrix.services.friends import get_friendship_between

bp = Blueprint("chat", __name__)


def _avatar_url(avatar_id) -> str:
    return url_for("static", filename=f"images/avatars/{avatar_id or DEFAULT_AVATAR}.png")


@bp.route("/messagerie/amis")
@login_required
def conversations() -> dict:
    """Liste des amis avec leur dernier message et leur nombre de non-lus."""
    conversations_data = list_conversations(current_user.id)
    for conversation in conversations_data:
        conversation["avatar_url"] = _avatar_url(conversation["avatar"])

    return {
        "conversations": conversations_data,
        "unread_total": unread_total(current_user.id),
    }


@bp.route("/messagerie/<int:friend_id>")
@login_required
def conversation_history(friend_id: int) -> tuple[dict, int] | dict:
    """Historique d'une conversation avec un ami précis."""
    friend = User.query.get_or_404(friend_id)
    friendship = get_friendship_between(current_user.id, friend.id)
    if friendship is None or friendship.status != "accepted":
        return {"error": "not_friends"}, 403

    messages = get_conversation(current_user.id, friend.id)

    return {
        "friend": {
            "id": friend.id,
            "username": friend.username,
            "avatar_url": _avatar_url(friend.avatar),
        },
        "messages": messages,
    }


@bp.route("/messagerie/<int:friend_id>/lu", methods=["POST"])
@login_required
def mark_read(friend_id: int) -> dict:
    """Marque les messages reçus de cet ami comme lus (ouverture du fil)."""
    mark_conversation_read(current_user.id, friend_id)
    return {"ok": True}
