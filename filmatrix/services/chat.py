"""Logique métier de la messagerie en direct entre amis."""

from filmatrix.catalog import DEFAULT_AVATAR
from filmatrix.extensions import db, socketio
from filmatrix.models import ChatMessage, User
from filmatrix.services.friends import get_friends_list, get_friendship_between

MAX_MESSAGE_LENGTH = 1000


def send_message(sender, recipient, body: str) -> ChatMessage:
    """Envoie un message d'un joueur à un autre, s'ils sont bien amis.

    Le message est enregistré avant d'être émis (même pattern que
    create_notification) : si le commit échoue, aucun évènement n'est
    envoyé, et un rechargement du fil ne fait jamais apparaître un message
    fantôme.
    """
    if sender.id == recipient.id:
        raise ValueError("Impossible de s'envoyer un message à soi-même.")

    friendship = get_friendship_between(sender.id, recipient.id)
    if friendship is None or friendship.status != "accepted":
        raise ValueError("Ce joueur n'est pas dans ta liste d'amis.")

    clean_body = (body or "").strip()
    if not clean_body:
        raise ValueError("Le message est vide.")
    if len(clean_body) > MAX_MESSAGE_LENGTH:
        raise ValueError("Le message est trop long.")

    message = ChatMessage(sender_id=sender.id, recipient_id=recipient.id, body=clean_body)
    db.session.add(message)
    db.session.commit()

    payload = serialize_message(message)

    socketio.emit("new_chat_message", payload, room=f"user_{recipient.id}")
    # Synchronise les autres onglets/appareils de l'expéditeur lui-même : le
    # front ignore cet écho sur l'onglet qui vient d'envoyer (déjà affiché
    # en optimiste), voir static/js/chat.js.
    socketio.emit("new_chat_message", payload, room=f"user_{sender.id}")

    return message


def serialize_message(message: ChatMessage) -> dict:
    """Représentation JSON d'un message, envoyée telle quelle au client (WS ou REST).

    Inclut le pseudo de l'expéditeur : le client reçoit ainsi tout ce qu'il
    faut pour afficher un toast ou un aperçu sans requête supplémentaire.
    """
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_username": message.sender.username,
        "recipient_id": message.recipient_id,
        "body": message.body,
        "is_read": message.is_read,
        "created_at": message.created_at.isoformat(),
    }


def get_conversation(user_id: int, friend_id: int, limit: int = 50, before_id: int | None = None) -> list[dict]:
    """Historique d'une conversation, du plus ancien au plus récent (prêt à afficher tel quel).

    before_id permet de remonter plus loin dans l'historique (pagination) :
    ne renvoie que les messages antérieurs à ce message-là.
    """
    query = ChatMessage.query.filter(
        db.or_(
            db.and_(ChatMessage.sender_id == user_id, ChatMessage.recipient_id == friend_id),
            db.and_(ChatMessage.sender_id == friend_id, ChatMessage.recipient_id == user_id),
        )
    )
    if before_id is not None:
        query = query.filter(ChatMessage.id < before_id)

    messages = query.order_by(ChatMessage.id.desc()).limit(limit).all()
    messages.reverse()
    return [serialize_message(message) for message in messages]


def mark_conversation_read(user_id: int, friend_id: int) -> int:
    """Marque comme lus les messages reçus de friend_id, renvoie combien ont changé."""
    unread = ChatMessage.query.filter_by(sender_id=friend_id, recipient_id=user_id, is_read=False).all()
    if not unread:
        return 0

    for message in unread:
        message.is_read = True
    db.session.commit()

    socketio.emit(
        "chat_read",
        {"by_user_id": user_id, "friend_id": friend_id},
        room=f"user_{friend_id}",
    )
    return len(unread)


def unread_total(user_id: int) -> int:
    """Nombre total de messages non lus, tous amis confondus — pour le badge de la bulle."""
    return ChatMessage.query.filter_by(recipient_id=user_id, is_read=False).count()


def list_conversations(user_id: int) -> list[dict]:
    """Pour chaque ami confirmé : dernier message échangé et nombre de non-lus.

    Sert à peupler le panneau de la bulle : triée avec les non-lus d'abord
    (voir static/js/chat.js pour le tri complet, présence+alpha inclus, qui
    a besoin d'informations côté client - ordre stable par défaut : dernier
    message le plus récent d'abord).
    """
    friends = get_friends_list(user_id)
    conversations = []

    for friend in friends:
        last_message = (
            ChatMessage.query.filter(
                db.or_(
                    db.and_(ChatMessage.sender_id == user_id, ChatMessage.recipient_id == friend.id),
                    db.and_(ChatMessage.sender_id == friend.id, ChatMessage.recipient_id == user_id),
                )
            )
            .order_by(ChatMessage.id.desc())
            .first()
        )
        unread_count = ChatMessage.query.filter_by(
            sender_id=friend.id, recipient_id=user_id, is_read=False
        ).count()

        conversations.append(
            {
                "friend_id": friend.id,
                "username": friend.username,
                "avatar": friend.avatar or DEFAULT_AVATAR,
                "last_message": last_message.body if last_message else None,
                "last_message_at": last_message.created_at.isoformat() if last_message else None,
                "last_message_from_me": last_message.sender_id == user_id if last_message else False,
                "unread_count": unread_count,
            }
        )

    # Chaîne ISO vide pour les conversations sans historique : elle trie
    # avant toute vraie date, donc reverse=True la renvoie bien en dernier.
    conversations.sort(key=lambda c: c["last_message_at"] or "", reverse=True)
    return conversations
