"""Tests de la logique métier des parties multijoueur."""

from datetime import datetime, timedelta

from src.database import db
from src.models import GameSession, GameSessionQuestion, Question, User
from src.multiplayer import (
    create_game_invitation,
    get_ordered_questions,
    is_invitation_expired,
)


def create_test_user(username: str) -> User:
    """Crée un utilisateur de test en base"""
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def create_test_questions(mode: str, count: int) -> None:
    """Crée plusieurs questions de test pour un mode donné"""
    for i in range(count):
        question = Question(
            mode=mode,
            category="test",
            difficulty="facile",
            prompt=f"Question de test {i}",
            payload={"options": ["A", "B"]},
            correct_answer={"index": 0},
            requires_account=False,
        )
        db.session.add(question)
    db.session.commit()


def test_create_game_invitation_succeeds_with_enough_questions(app):
    """La création d'invitation réussie s'il y a assez de questions"""
    with app.app_context():
        host = create_test_user("Host")
        guest = create_test_user("Guest")
        create_test_questions("qcm", 5)

        game_session = create_game_invitation(host, guest, "qcm")

        assert game_session is not None
        assert game_session.status == "invited"
        assert game_session.host_id == host.id
        assert game_session.guest_id == guest.id


def test_create_game_invitation_fails_with_too_few_questions(app):
    """La création d'invitation échoue s'il n'y a pas assez de questions"""
    with app.app_context():
        host = create_test_user("Host")
        guest = create_test_user("Guest")
        create_test_questions("qcm", 2)

        game_session = create_game_invitation(host, guest, "qcm")

        assert game_session is None


def test_create_game_invitation_creates_five_distinct_questions(app):
    """La session de jeu doit comporter exactement 5 questions"""
    with app.app_context():
        host = create_test_user("Host")
        guest = create_test_user("Guest")
        create_test_questions("qcm", 10)

        game_session = create_game_invitation(host, guest, "qcm")
        db.session.commit()

        questions = get_ordered_questions(game_session)

        assert len(questions) == 5
        assert len({q.id for q in questions}) == 5


def test_is_invitation_expired_returns_false_for_fresh_invitation(app):
    """Une nouvelle invitation ne doit pas expirer"""
    with app.app_context():
        host = create_test_user("Host")
        guest = create_test_user("Guest")
        create_test_questions("qcm", 5)

        game_session = create_game_invitation(host, guest, "qcm")

        assert is_invitation_expired(game_session) is False


def test_is_invitation_expired_returns_true_for_old_invitation(app):
    """Une invitation dont le délai est passé doit être détectée comme expirée"""
    with app.app_context():
        host = create_test_user("Host")
        guest = create_test_user("Guest")

        game_session = GameSession(
            host_id=host.id,
            guest_id=guest.id,
            mode="qcm",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.session.add(game_session)
        db.session.commit()

        assert is_invitation_expired(game_session) is True