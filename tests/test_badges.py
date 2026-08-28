"""Tests du système de badges."""

from filmatrix.services.badges import award_badge, check_and_award_badges, has_badge
from filmatrix.extensions import db
from filmatrix.models import Attempt, Question, User


def create_test_user() -> User:
    """Crée un utilisateur de test en base."""
    user = User(username="TestPlayer", email="test@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def create_test_question(mode: str = "qcm") -> Question:
    """Crée une question de test en base."""
    question = Question(
        mode=mode,
        prompt="Question de test",
        payload={"options": ["A", "B"]},
        correct_answer={"index": 0},
        requires_account=False,
    )
    db.session.add(question)
    db.session.commit()
    return question


def test_award_badge_gives_badge_once(app):
    """A badge should only be awarded once, even if called twice."""
    with app.app_context():
        user = create_test_user()

        award_badge(user, "first_step")
        award_badge(user, "first_step")
        db.session.commit()

        assert len(user.badges) == 1


def test_has_badge_detects_existing_badge(app):
    """has_badge should correctly detect an already-awarded badge."""
    with app.app_context():
        user = create_test_user()

        award_badge(user, "first_step")
        db.session.commit()

        assert has_badge(user, "first_step") is True
        assert has_badge(user, "level_5") is False


def test_first_step_badge_awarded_after_one_attempt(app):
    """The first_step badge should unlock after a single attempt."""
    with app.app_context():
        user = create_test_user()
        question = create_test_question()

        attempt = Attempt(user_id=user.id, question_id=question.id, is_correct=True)
        db.session.add(attempt)
        db.session.commit()

        check_and_award_badges(user)
        db.session.commit()

        assert has_badge(user, "first_step") is True


def test_five_in_a_row_badge_requires_five_correct(app):
    """The five_in_a_row badge should only unlock after 5 correct answers in a row."""
    with app.app_context():
        user = create_test_user()
        question = create_test_question()

        for _ in range(4):
            attempt = Attempt(user_id=user.id, question_id=question.id, is_correct=True)
            db.session.add(attempt)
        db.session.commit()

        check_and_award_badges(user)
        db.session.commit()
        assert has_badge(user, "five_in_a_row") is False

        attempt = Attempt(user_id=user.id, question_id=question.id, is_correct=True)
        db.session.add(attempt)
        db.session.commit()

        check_and_award_badges(user)
        db.session.commit()
        assert has_badge(user, "five_in_a_row") is True