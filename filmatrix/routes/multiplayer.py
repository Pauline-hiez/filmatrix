"""Duels en temps réel : présentation, invitation, salon et partie."""

import random

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db, socketio
from filmatrix.models import GameSession, User
from filmatrix.game_modes import GAME_MODES, MULTIPLAYER_MODES
from filmatrix.services.engine import scramble_title
from filmatrix.services.questions import question_image_url, shuffle_options
from filmatrix.services.friends import friend_cards, get_friends_list, get_friendship_between
from filmatrix.services.levels import calculate_level
from filmatrix.services.multiplayer import (
    INVITATION_DURATION_MINUTES,
    QUESTIONS_PER_GAME,
    QUESTION_DURATION,
    abandon_game,
    build_choices,
    finalize_game,
    create_game_invitation,
    get_ordered_questions,
    is_invitation_expired,
    live_scores,
)
from filmatrix.services.notifications import create_notification


bp = Blueprint("multiplayer", __name__)


@bp.route("/multijoueur")
def multiplayer_home() -> str:
    """Présente le mode multijoueur et permet de lancer un défi

    Le multijoueur n'avait aucune porte d'entrée : il fallait passer par la
    fiche publique d'un ami pour découvrir qu'il existait. Cette page lui
    donne une adresse, explique la règle, et met le défi à un clic."""
    multiplayer_modes = [
        entry for entry in GAME_MODES if entry["slug"] in MULTIPLAYER_MODES
    ]

    if not current_user.is_authenticated:
        return render_template(
            "multiplayer/accueil.html",
            modes=multiplayer_modes,
            friends=[],
            pending_invitations=[],
            questions_per_game=QUESTIONS_PER_GAME,
            invitation_minutes=INVITATION_DURATION_MINUTES,
        )

    # Invitations reçues et encore valides : sans elles, le joueur ne peut
    # les retrouver que dans la cloche de notifications.
    pending_invitations = [
        game
        for game in GameSession.query.filter_by(
            guest_id=current_user.id, status="invited"
        ).all()
        if not is_invitation_expired(game)
    ]

    return render_template(
        "multiplayer/accueil.html",
        modes=multiplayer_modes,
        friends=friend_cards(get_friends_list(current_user.id)),
        pending_invitations=pending_invitations,
        questions_per_game=QUESTIONS_PER_GAME,
        invitation_minutes=INVITATION_DURATION_MINUTES,
    )

@bp.route("/multijoueur/inviter/<int:user_id>", methods=["POST"])
@login_required
def invite_to_game(user_id: int) -> str:
    """Invite un ami à une partie multijoueur en mode rapidité"""
    friendship = get_friendship_between(current_user.id, user_id)
    if friendship is None or friendship.status != "accepted":
        flash("Tu dois être ami avec ce joueur pour l'inviter.")
        return redirect(url_for("friends.friends_list"))

    guest = User.query.get_or_404(user_id)
    mode = request.form.get("mode", "qcm")

    game_session = create_game_invitation(current_user, guest, mode)

    if game_session is None:
        flash("Ce mode n'a pas assez de questions pour un duel.")
        return redirect(url_for("friends.friends_list"))

    db.session.commit()

    create_notification(
            guest,
            f"{current_user.username} t'invite à une partie !",
            link=url_for("multiplayer.game_lobby", game_session_id=game_session.id),
        )
    db.session.commit()

    flash(f"Invitation envoyée à {guest.username}.")
    return redirect(url_for("multiplayer.game_lobby", game_session_id=game_session.id))

@bp.route("/multijoueur/<int:game_session_id>")
@login_required
def game_lobby(game_session_id: int) -> str:
    """Affiche la salle d'attente d'une partie multijoueur"""
    game_session = GameSession.query.get_or_404(game_session_id)

    if current_user.id not in (game_session.host_id, game_session.guest_id):
        flash("Tu ne fais pas partie de cette partie.")
        return redirect(url_for("friends.friends_list"))

    if game_session.status == "invited" and is_invitation_expired(game_session):
        game_session.status = "expired"
        db.session.commit()

    return render_template(
        "multiplayer/salon.html",
        game_session=game_session,
        questions_per_game=QUESTIONS_PER_GAME,
    )

@bp.route("/multijoueur/<int:game_session_id>/annuler", methods=["POST"])
@login_required
def cancel_game_invitation(game_session_id: int) -> str:
    """Annule une invitation encore en attente, uniquement pour son hôte."""
    game_session = GameSession.query.get_or_404(game_session_id)

    if current_user.id != game_session.host_id or game_session.status != "invited":
        flash("Impossible d'annuler cette invitation.")
        return redirect(url_for("multiplayer.game_lobby", game_session_id=game_session.id))

    game_session.status = "declined"
    db.session.commit()
    flash("Invitation annulée.")
    return redirect(url_for("multiplayer.multiplayer_home"))


@bp.route("/multijoueur/<int:game_session_id>/accepter", methods=["POST"])
@login_required
def accept_game_invitation(game_session_id: int) -> str:
    """Accepte une invitation de partie multijoueur"""
    game_session = GameSession.query.get_or_404(game_session_id)

    if current_user.id != game_session.guest_id or game_session.status != "invited":
        flash("Impossible d'accepter cette invitation.")
        return redirect(url_for("friends.friends_list"))

    if is_invitation_expired(game_session):
        game_session.status = "expired"
        db.session.commit()
        flash("Cette invitation a expiré.")
        return redirect(url_for("multiplayer.game_lobby", game_session_id=game_session.id))

    game_session.status = "active"
    db.session.commit()

    create_notification(
            game_session.host,
            f"{current_user.username} a accepté ta partie !",
            link=url_for("multiplayer.game_lobby", game_session_id=game_session.id),
        )
    db.session.commit()

    socketio.emit(
            "game_started",
            {"redirect_url": url_for("multiplayer.game_lobby", game_session_id=game_session.id)},
            room=f"user_{game_session.host_id}",
        )

    return redirect(url_for("multiplayer.game_lobby", game_session_id=game_session.id))

@bp.route("/multijoueur/<int:game_session_id>/refuser", methods=["POST"])
@login_required
def decline_game_invitation(game_session_id: int) -> str:
    """Refuse une invitation de partie multijoueur"""
    game_session = GameSession.query.get_or_404(game_session_id)

    if current_user.id != game_session.guest_id or game_session.status != "invited":
        flash("Impossible de refuser cette invitation.")
        return redirect(url_for("friends.friends_list"))

    game_session.status = "declined"
    db.session.commit()

    return redirect(url_for("multiplayer.game_lobby", game_session_id=game_session.id))

@bp.route("/multijoueur/<int:game_session_id>/jouer")
@login_required
def play_game(game_session_id: int) -> str:
    """Affiche la salle de jeu synchronisée d'une partie multijoueur"""
    game_session = GameSession.query.get_or_404(game_session_id)

    if current_user.id not in (game_session.host_id, game_session.guest_id):
        flash("Tu ne fais pas partie de cette partie.")
        return redirect(url_for("friends.friends_list"))

    if game_session.status != "active":
        return redirect(url_for("multiplayer.game_lobby", game_session_id=game_session.id))

    questions = get_ordered_questions(game_session)

    if game_session.current_question_index >= len(questions):
        return redirect(url_for("multiplayer.game_results", game_session_id=game_session.id))

    current_question = questions[game_session.current_question_index]
    opponent = game_session.guest if current_user.id == game_session.host_id else game_session.host

    # Le mélange doit tomber pareil chez les deux adversaires, sinon l'un
    # des deux hérite d'un titre plus lisible que l'autre. La graine est
    # propre à la partie et à la question : elle change d'un duel à l'autre.
    # Graine sous forme de texte : seeder sur un tuple passe par le hachage,
    # déprécié depuis Python 3.9, et rien ne garantit le même résultat d'un
    # processus à l'autre. Une chaîne, elle, donne toujours la même suite.
    shared_seed = f"{game_session.id}-{current_question.id}"

    scrambled_title = None
    if current_question.mode == "film_melange":
        scrambled_title = scramble_title(
            current_question.correct_answer["title"], seed=shared_seed
        )

    # Même exigence pour l'ordre des propositions d'un QCM : mêmes cases,
    # dans le même ordre, pour que la course reste à la loyale.
    options = None
    if current_question.mode == "qcm":
        options = shuffle_options(
            current_question,
            shuffler=random.Random(shared_seed),
        )

    # En solo le joueur écrit le titre ; en duel il le choisit. Il n'a droit
    # qu'à un essai, et une faute de frappe lui coûterait le point sans
    # recours. Le QCM a déjà ses options, la chronologie attend un ordre.
    choices = None
    if current_question.mode not in ("qcm", "vrai_faux", "chronologie"):
        choices = build_choices(current_question, seed=shared_seed)

    display_host_score, display_guest_score = live_scores(game_session)

    leaderboard_players = User.query.order_by(User.total_xp.desc()).limit(5).all()
    sidebar_friends = friend_cards(get_friends_list(current_user.id))[:5]
    player_level = calculate_level(current_user.total_xp)
    player_rank = User.query.filter(User.total_xp > current_user.total_xp).count() + 1

    return render_template(
            "multiplayer/partie.html",
            game_session=game_session,
            question=current_question,
            opponent=opponent,
            total_questions=len(questions),
            scrambled_title=scrambled_title,
            options=options,
            choices=choices,
            leaderboard_players=leaderboard_players,
            sidebar_friends=sidebar_friends,
            player_level=player_level,
            player_rank=player_rank,
            question_duration=QUESTION_DURATION,
            display_host_score=display_host_score,
            display_guest_score=display_guest_score,
            question_image_url=question_image_url(current_question),
        )

@bp.route("/multijoueur/<int:game_session_id>/quitter", methods=["POST"])
@login_required
def leave_game(game_session_id: int) -> str:
    """Abandonne une partie en cours sans conserver son score."""
    game_session = GameSession.query.get_or_404(game_session_id)

    if current_user.id not in (game_session.host_id, game_session.guest_id):
        flash("Tu ne fais pas partie de cette partie.")
        return redirect(url_for("friends.friends_list"))

    if abandon_game(game_session, current_user.id):
        db.session.commit()
        socketio.emit(
            "game_abandoned",
            {"redirect_url": url_for("multiplayer.multiplayer_home")},
            room=f"game_{game_session.id}",
        )
        flash("Partie quittée : aucun point n'a été enregistré.")
    else:
        flash("Cette partie ne peut plus être quittée.")

    return redirect(url_for("multiplayer.multiplayer_home"))


@bp.route("/multijoueur/<int:game_session_id>/statut")
@login_required
def game_session_status(game_session_id: int) -> dict:
    """Renvoie le statut actuel d'une partie"""
    game_session = GameSession.query.get_or_404(game_session_id)

    if current_user.id not in (game_session.host_id, game_session.guest_id):
        return {"status": "forbidden"}
    return {"status": game_session.status}

@bp.route("/multijoueur/<int:game_session_id>/resultats")
@login_required
def game_results(game_session_id: int) -> str:
    """Affiche les résultats finaux d'une partie multijoueur avec mort subite si égalité"""
    game_session = GameSession.query.get_or_404(game_session_id)

    if current_user.id not in (game_session.host_id, game_session.guest_id):
        flash("Tu ne fais pas partie de cette partie.")
        return redirect(url_for("friends.friends_list"))

    if game_session.status != "finished" and game_session.status != "active":
        return redirect(url_for("multiplayer.game_lobby", game_session_id=game_session.id))

    questions = get_ordered_questions(game_session)
    if game_session.status == "active" and game_session.current_question_index < len(questions):
        return redirect(url_for("multiplayer.play_game", game_session_id=game_session.id))

    if game_session.status == "active":
        finalize_game(game_session, len(questions))
        db.session.commit()

    if game_session.host_score == game_session.guest_score:
        winner = None
    elif game_session.host_score > game_session.guest_score:
        winner = game_session.host
    else:
        winner = game_session.guest

    opponent = game_session.guest if current_user.id == game_session.host_id else game_session.host
    my_score = game_session.host_score if current_user.id == game_session.host_id else game_session.guest_score
    opponent_score = game_session.guest_score if current_user.id == game_session.host_id else game_session.host_score

    return render_template(
            "multiplayer/resultats.html",
            game_session=game_session,
            winner=winner,
            opponent=opponent,
            my_score=my_score,
            opponent_score=opponent_score,
        )
