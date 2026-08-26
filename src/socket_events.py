"""Gestionnaire d'évènements SocketIO"""

from flask_login import current_user
from flask_socketio import join_room, emit

from src.database import db
from src.engine import check_answer
from src.models import GameAnswer, GameSession
from src.multiplayer import get_ordered_questions


def register_socket_events(socketio):
    """Enregistre les gestionnaires d'évènements SocketIO"""

    @socketio.on("connect")
    def handle_connect():
        """Fait rejoindre à l'utilisateur son salon personnel dès la connexion"""
        if current_user.is_authenticated:
            join_room(f"user_{current_user.id}")

    @socketio.on("join_game")
    def handle_join_game(data):
        """Fait rejoindre un joueur au salon d'une partie precise"""
        if not current_user.is_authenticated:
            return

        game_session_id = data["game_session_id"]
        join_room(f"game_{game_session_id}")

    @socketio.on("submit_game_answer")
    def handle_submit_game_answer(data):
        """Traite la reponse d'un joueur a la question en cours d'une partie"""
        if not current_user.is_authenticated:
            return

        game_session_id = data["game_session_id"]
        raw_answer = data["answer"]

        game_session = GameSession.query.get(game_session_id)
        if game_session is None or game_session.status != "active":
            return

        if current_user.id not in (game_session.host_id, game_session.guest_id):
            return

        already_answered = GameAnswer.query.filter_by(
            game_session_id=game_session.id,
            user_id=current_user.id,
            question_index=game_session.current_question_index,
        ).first()
        if already_answered is not None:
            return

        questions = get_ordered_questions(game_session)
        current_question = questions[game_session.current_question_index]

        is_correct = False
        if isinstance(raw_answer, str) and current_question.mode == "qcm":
            is_correct = check_answer(current_question, int(raw_answer))
        elif current_question.mode == "vrai_faux":
            is_correct = check_answer(current_question, raw_answer == "true")
        else:
            is_correct = check_answer(current_question, raw_answer)

        game_answer = GameAnswer(
            game_session_id=game_session.id,
            user_id=current_user.id,
            question_index=game_session.current_question_index,
            is_correct=is_correct,
        )
        db.session.add(game_answer)
        db.session.commit()

        round_answers = GameAnswer.query.filter_by(
            game_session_id=game_session.id,
            question_index=game_session.current_question_index,
        ).all()

        correct_answers_sorted = sorted(
            (answer for answer in round_answers if answer.is_correct),
            key=lambda a: a.answered_at,
        )
        first_correct = correct_answers_sorted[0] if correct_answers_sorted else None

        both_answered = len(round_answers) == 2
        room = f"game_{game_session.id}"

        if both_answered or first_correct is not None:
            winner_id = first_correct.user_id if first_correct else None

            if winner_id == game_session.host_id:
                game_session.host_score += 1
            elif winner_id == game_session.guest_id:
                game_session.guest_score += 1

            game_session.current_question_index += 1
            db.session.commit()

            emit(
                "round_result",
                {
                    "winner_id": winner_id,
                    "host_score": game_session.host_score,
                    "guest_score": game_session.guest_score,
                    "next_question_index": game_session.current_question_index,
                    "total_questions": len(questions),
                },
                room=room,
            )