"""Logique métier des parties multijoueur."""

import random
from datetime import datetime, timedelta

from src.database import db
from src.models import GameSession, GameSessionQuestion, Question

INVITATION_DURATION_MINUTES = 15
QUESTIONS_PER_GAME = 5


def create_game_invitation(host, guest, mode: str) -> GameSession | None:
    """Crée une invitation de partie. Renvoie None si pas assez de questions disponibles."""
    available_questions = Question.query.filter_by(mode=mode).all()

    if len(available_questions) < QUESTIONS_PER_GAME:
        return None

    selected_questions = random.sample(available_questions, QUESTIONS_PER_GAME)

    game_session = GameSession(
        host_id=host.id,
        guest_id=guest.id,
        mode=mode,
        expires_at=datetime.utcnow() + timedelta(minutes=INVITATION_DURATION_MINUTES),
    )
    db.session.add(game_session)
    db.session.flush()

    for index, question in enumerate(selected_questions):
        session_question = GameSessionQuestion(
            game_session_id=game_session.id,
            question_id=question.id,
            order_index=index,
        )
        db.session.add(session_question)

    return game_session


def is_invitation_expired(game_session: GameSession) -> bool:
    """Vérifie si le délai d'une invitation est dépassé."""
    return datetime.utcnow() > game_session.expires_at


def get_ordered_questions(game_session: GameSession) -> list[Question]:
    """Renvoie les questions d'une partie, dans leur ordre défini."""
    session_questions = (
        GameSessionQuestion.query.filter_by(game_session_id=game_session.id)
        .order_by(GameSessionQuestion.order_index)
        .all()
    )
    return [sq.question for sq in session_questions]