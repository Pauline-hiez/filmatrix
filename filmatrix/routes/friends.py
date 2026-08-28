"""Liste d'amis, demandes envoyées et reçues."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.models import Friendship, User
from filmatrix.services.friends import (
    accept_friend_request,
    decline_friend_request,
    friend_cards,
    get_friends_list,
    remove_friend,
    send_friend_request,
)
from filmatrix.services.notifications import create_notification


bp = Blueprint("friends", __name__)


@bp.route("/amis/demander/<int:user_id>", methods=["POST"])
@login_required
def send_friend_request_route(user_id: int) -> str:
    """Envoie une demande d'amis à un utilisateur"""
    target_user = User.query.get_or_404(user_id)

    success = send_friend_request(current_user, target_user)

    if success:
        create_notification(
            target_user,
            f"{current_user.username} t'a envoyé une demande d'ami.",
            link=url_for("friends.friends_list"),
        )

    db.session.commit()

    if success:
        flash(f"Demande d'ami envoyée à {target_user.username}.")
    else:
        flash("Impossible d'envoyer cette demande.")

    return redirect(request.referrer or url_for("friends.friends_list"))

@bp.route("/amis/supprimer/<int:user_id>", methods=["POST"])
@login_required
def remove_friend_route(user_id: int) -> str:
    """Retire un joueur de la liste d'amis de l'utilisateur connecté"""
    former_friend = User.query.get_or_404(user_id)

    if remove_friend(current_user.id, former_friend.id):
        db.session.commit()
        flash(f"{former_friend.username} ne fait plus partie de tes amis.")
    else:
        flash("Impossible de retirer cet ami.")

    return redirect(request.referrer or url_for("friends.friends_list"))

@bp.route("/amis/accepter/<int:friendship_id>", methods=["POST"])
@login_required
def accept_friend_request_route(friendship_id: int) -> str:
    """Accepte une demande d'ami reçue"""
    friendship = Friendship.query.get(friendship_id)
    success = accept_friend_request(friendship_id, current_user.id)

    if success:
        create_notification(
            friendship.requester,
            f"{current_user.username} a accepté ta demande d'ami.",
            link=url_for("friends.friends_list"),
        )

    db.session.commit()

    if success:
        flash("Demande d'ami acceptée.")
    else:
        flash("Impossible d'accepter cette demande.")

    return redirect(url_for("friends.friends_list"))

@bp.route("/amis/refuser/<int:friendship_id>", methods=["POST"])
@login_required
def decline_friend_request_route(friendship_id: int) -> str:
    """Refuse ou annule une demande d'ami"""
    success = decline_friend_request(friendship_id, current_user.id)
    db.session.commit()

    if success:
        flash("Demande supprimée.")
    else:
        flash("Impossible de supprimer cette demande.")

    return redirect(url_for("friends.friends_list"))

@bp.route("/amis")
@login_required
def friends_list() -> str:
    """Affiche la liste d'amis, les demandes reçues et envoyées"""
    friends = friend_cards(get_friends_list(current_user.id))

    received_requests = [
            friendship
            for friendship in current_user.received_friend_requests
            if friendship.status == "pending"
        ]

    sent_requests = [
            friendship
            for friendship in current_user.sent_friend_requests
            if friendship.status == "pending"
        ]

    return render_template(
            "friends/amis.html",
            friends=friends,
            received_requests=received_requests,
            sent_requests=sent_requests,
        )
