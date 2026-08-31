"""Logique métier du système d'amis"""

from filmatrix.catalog import DEFAULT_AVATAR
from filmatrix.extensions import db
from filmatrix.services.levels import calculate_level
from filmatrix.models import Friendship, User
from sqlalchemy import func

def get_friendship_between(user_a_id: int, user_b_id: int) -> Friendship | None:
    """Cherche une relation d'amitié existante entre deux utilisateurs, dans les deux sens"""
    return Friendship.query.filter(
            db.or_(
                db.and_(
                    Friendship.requester_id == user_a_id,
                    Friendship.receiver_id == user_b_id,
                    ),
                db.and_(
                    Friendship.requester_id == user_b_id,
                    Friendship.receiver_id == user_a_id,
                    ),
                )
        ).first()

def send_friend_request(requester, receiver) -> bool:
    """Envoie une demande d'ami, renvoie False si déjà amis"""
    if requester.id == receiver.id:
        return False

    existing = get_friendship_between(requester.id, receiver.id)
    if existing is not None:
        return False

    new_friendship = Friendship(requester_id=requester.id, receiver_id=receiver.id)
    db.session.add(new_friendship)
    return True

def accept_friend_request(friendship_id: int, current_user_id: int) -> bool:
    """Accepte une demande d'amis reçue, renvoie False si non autorisé ou introuvable"""
    friendship = Friendship.query.get(friendship_id)

    if friendship is None or friendship.receiver_id != current_user_id:
        return False

    friendship.status = "accepted"
    return True

def decline_friend_request(friendship_id: int, current_user_id: int) -> bool:
    """Refuse (supprime) une demande d'ami reçue ou annule une demande envoyée"""
    friendship = Friendship.query.get(friendship_id)

    if friendship is None:
        return False

    if friendship.receiver_id != current_user_id and friendship.requester_id != current_user_id:
        return False

    db.session.delete(friendship)
    return True 

def remove_friend(user_id: int, friend_id: int) -> bool:
    """Supprime une amitié confirmée, renvoie False s'il n'y en a pas

    Distinct de decline_friend_request, qui porte sur une demande en attente et
    s'identifie par la relation ; ici on part des deux joueurs"""
    friendship = get_friendship_between(user_id, friend_id)

    if friendship is None or friendship.status != "accepted":
        return False

    db.session.delete(friendship)
    return True

def get_friends_list(user_id: int) -> list:
    """Renvoie la liste des amis confirmés d'un utilisateur"""
    accepted = Friendship.query.filter(
            db.and_(
                Friendship.status == "accepted",
                db.or_(
                    Friendship.requester_id == user_id,
                    Friendship.receiver_id == user_id,
                    ),
                )
        ).all()

    friends = []
    for friendship in accepted:
        friend = friendship.receiver if friendship.requester_id == user_id else friendship.requester
        friends.append(friend)

    return friends


def search_players(query: str, current_user_id: int, limit: int = 20) -> list[dict]:
    """Recherche des joueurs par pseudo et décrit la relation existante."""
    search_term = " ".join((query or "").strip().split())
    if not search_term:
        return []

    players = (
        User.query.filter(
            User.id != current_user_id,
            func.lower(User.username).contains(search_term.casefold()),
        )
        .order_by(User.username)
        .limit(limit)
        .all()
    )

    results = []
    for player in players:
        friendship = get_friendship_between(current_user_id, player.id)
        relationship = "none"
        friendship_id = None
        if friendship is not None:
            friendship_id = friendship.id
            if friendship.status == "accepted":
                relationship = "friends"
            elif friendship.requester_id == current_user_id:
                relationship = "request_sent"
            else:
                relationship = "request_received"

        results.append(
            {
                "id": player.id,
                "username": player.username,
                "avatar": player.avatar or DEFAULT_AVATAR,
                "level": calculate_level(player.total_xp)["level"],
                "relationship": relationship,
                "friendship_id": friendship_id,
                "online": False,
            }
        )

    return results


def friend_cards(users: list) -> list:
    """Prépare l'affichage d'une liste d'amis : pseudo, avatar et niveau

    Le niveau est calculé ici plutôt que dans le template, pour que les deux
    profils affichent exactement la même chose"""
    return [
        {
            "id": user.id,
            "username": user.username,
            "avatar": user.avatar or DEFAULT_AVATAR,
            "level": calculate_level(user.total_xp)["level"],
            "online": False,
        }
        for user in users
    ]
