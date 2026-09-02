"""Profil personnel et fiches publiques des joueurs."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.catalog import AVATARS, AVATAR_RING_COLORS
from filmatrix.models import Attempt, User
from filmatrix.game_modes import GAME_MODES, MULTIPLAYER_MODES
from filmatrix.services.badges import BADGES, next_objective
from filmatrix.services.friends import friend_cards, get_friends_list, get_friendship_between
from filmatrix.services.levels import calculate_level
from filmatrix.services.shop import TITLES
from filmatrix.services.collection import get_saga_summaries
from filmatrix.services.daily_challenges import describe_challenge, get_or_create_daily_challenge
from filmatrix.models import DailyChallenge
from datetime import date


bp = Blueprint("profile", __name__)


@bp.route("/profil")
@login_required
def profile() -> str:
    """Affiche le score et l'historique du joueur connecté"""
    attempts = (
        Attempt.query.filter_by(user_id=current_user.id)
        .order_by(Attempt.answered_at.desc())
        .all()
    )

    total_count = len(attempts)
    correct_count = sum(1 for attempt in attempts if attempt.is_correct)
    level_info = calculate_level(current_user.total_xp)

    attempts_by_mode = {}
    for attempt in attempts:
        mode = attempt.question.mode
        attempts_by_mode.setdefault(mode, []).append(attempt)

    earned_badge_codes = {badge.badge_code for badge in current_user.badges}
    all_badges = []
    for code, info in BADGES.items():
        all_badges.append(
            {
                "code": code,
                "name": info["name"],
                "description": info["description"],
                "icon": info["icon"],
                "earned": code in earned_badge_codes,
            }
        )

    equipped_title_name= None
    if current_user.equipped_title:
        equipped_title_name = TITLES.get(current_user.equipped_title, {}).get("name")

    saga_summaries = get_saga_summaries(current_user)
    objective = next_objective(current_user)

    today_challenge = get_or_create_daily_challenge(current_user)
    challenge_info = describe_challenge(today_challenge)

    challenge_history = (
        DailyChallenge.query.filter_by(user_id=current_user.id, completed_at=None)
        .filter(DailyChallenge.challenge_date < date.today())
        .order_by(DailyChallenge.challenge_date.desc())
        .limit(0)
        .all()
    )
    # On veut l'historique de TOUS les défis passés, complétés ou non :
    challenge_history = (
        DailyChallenge.query.filter_by(user_id=current_user.id)
        .filter(DailyChallenge.challenge_date < date.today())
        .order_by(DailyChallenge.challenge_date.desc())
        .limit(14)
        .all()
    )
    challenge_history_info = [
        {**describe_challenge(challenge), "date": challenge.challenge_date}
        for challenge in challenge_history
    ]

    return render_template(
        "profile/profil.html",
        friends=friend_cards(get_friends_list(current_user.id)),
        attempts_by_mode=attempts_by_mode,
        total_count=total_count,
        correct_count=correct_count,
        level_info=level_info,
        all_badges=all_badges,
        equipped_title_name=equipped_title_name,
        saga_summaries=saga_summaries,
        objective=objective,
        avatar_ring_color=AVATAR_RING_COLORS.get(current_user.avatar, "#22d3ee"),
        challenge=challenge_info,
        challenge_history=challenge_history_info,
        current_streak=current_user.current_streak,
    )

@bp.route("/profil/modifier", methods=["GET", "POST"])
@login_required
def edit_profile() -> str:
    """Permet de mofifier son avatar et sa bio"""
    if request.method == "POST":
        selected_avatar = request.form.get("avatar")
        if selected_avatar in AVATARS:
            current_user.avatar = selected_avatar

        bio = request.form.get("bio", "").strip()
        current_user.bio = bio[:280] if bio else None

        db.session.commit()

        flash("Profil mis à jour.")
        return redirect(url_for("profile.profile"))

    return render_template("profile/modifier.html", avatars=AVATARS)

@bp.route("/joueur/<int:user_id>")
@login_required
def public_profile(user_id: int) -> str:
    """Affiche le profil public d'un joueur

    Le profil est visible de n'importe quel joueur connecté : c'est de là
    qu'on envoie une demande d'ami. Seul le réseau social du joueur (sa
    liste d'amis, les amis en commun) reste réservé à ses amis"""
    if user_id == current_user.id:
        return redirect(url_for("profile.profile"))

    viewed_user = User.query.get_or_404(user_id)

    friendship = get_friendship_between(current_user.id, user_id)

    if friendship is None:
        friendship_state = "none"
    elif friendship.status == "accepted":
        friendship_state = "friends"
    elif friendship.requester_id == current_user.id:
        friendship_state = "request_sent"
    else:
        friendship_state = "request_received"

    attempts = Attempt.query.filter_by(user_id=viewed_user.id).all()
    total_count = len(attempts)
    correct_count = sum(1 for attempt in attempts if attempt.is_correct)
    level_info = calculate_level(viewed_user.total_xp)

    attempts_by_mode = {}
    for attempt in attempts:
        mode = attempt.question.mode
        attempts_by_mode.setdefault(mode, 0)
        attempts_by_mode[mode] += 1

    earned_badge_codes = {badge.badge_code for badge in viewed_user.badges}
    all_badges = []
    for code, info in BADGES.items():
        all_badges.append(
                {
                    "name": info["name"],
                    "icon": info["icon"],
                    "earned": code in earned_badge_codes,
                    }
            )

    # Le réseau d'amis du joueur n'est montré qu'à ses amis.
    viewed_user_friends = []
    mutual_friends = []

    if friendship_state == "friends":
        viewed_user_friends = get_friends_list(viewed_user.id)
        current_user_friends = get_friends_list(current_user.id)

        current_user_friend_ids = {friend.id for friend in current_user_friends}
        mutual_friends = friend_cards(
                [friend for friend in viewed_user_friends if friend.id in current_user_friend_ids]
            )
        viewed_user_friends = friend_cards(viewed_user_friends)

    # Le titre équipé est stocké sous forme de code : on affiche son libellé,
    # comme le fait déjà le profil personnel.
    equipped_title_name = None
    if viewed_user.equipped_title:
        equipped_title_name = TITLES.get(viewed_user.equipped_title, {}).get("name")

    return render_template(
            "profile/profil_public.html",
            multiplayer_modes=[
                entry for entry in GAME_MODES if entry["slug"] in MULTIPLAYER_MODES
            ],
            viewed_user=viewed_user,
            equipped_title_name=equipped_title_name,
            total_count=total_count,
            correct_count=correct_count,
            level_info=level_info,
            attempts_by_mode=attempts_by_mode,
            all_badges=all_badges,
            viewed_user_friends=viewed_user_friends,
            mutual_friends=mutual_friends,
            friendship_state=friendship_state,
        )
