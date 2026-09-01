"""Tests de la logique des défis quotidiens."""

from filmatrix.extensions import db
from filmatrix.models import DailyChallenge, Question, Tag, User
from filmatrix.services.daily_challenges import CHALLENGE_TYPES, get_or_create_daily_challenge


def create_test_user(username: str = "Defieur") -> User:
    """Crée un utilisateur de test en base"""
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def test_get_or_create_daily_challenge_creates_one_if_missing(app):
    """Un utilisateur sans défi aujourd'hui doit en voir un créé"""
    with app.app_context():
        user = create_test_user()

        challenge = get_or_create_daily_challenge(user)

        assert challenge.id is not None
        assert challenge.challenge_type in CHALLENGE_TYPES
        assert challenge.progress == 0


def test_get_or_create_daily_challenge_returns_existing_one(app):
    """Appeler deux fois le même jour doit renvoyer le même défi, et non en créer un nouveau"""
    with app.app_context():
        user = create_test_user()

        first_challenge = get_or_create_daily_challenge(user)
        second_challenge = get_or_create_daily_challenge(user)

        assert first_challenge.id == second_challenge.id
        assert DailyChallenge.query.filter_by(user_id=user.id).count() == 1


def test_mode_count_challenge_has_a_target_mode(app):
    """Un défi mode_count doit toujours préciser quel mode est ciblé"""
    with app.app_context():
        user = create_test_user()

        # On force le type pour un test déterministe plutôt que d'attendre
        # que le hasard tombe dessus.
        import filmatrix.services.daily_challenges as daily_challenges_module
        original_choice = daily_challenges_module.random.choice
        daily_challenges_module.random.choice = lambda options: (
            "mode_count" if options == CHALLENGE_TYPES else original_choice(options)
        )

        try:
            challenge = get_or_create_daily_challenge(user)
        finally:
            daily_challenges_module.random.choice = original_choice

        assert challenge.challenge_type == "mode_count"
        assert challenge.target_mode is not None