"""Gestionnaire d'évènements SocketIO"""

from flask_login import current_user
from flask_socketio import join_room, emit

from filmatrix.extensions import db
from filmatrix.services.engine import check_answer, convert_answer
from filmatrix.models import GameAnswer, GameSession

_online_users: set[int] = set()
from filmatrix.services.multiplayer import get_ordered_questions


def register_socket_events(socketio):
    """Enregistre les gestionnaires d'évènements SocketIO"""

    @socketio.on("connect")
    def handle_connect():
        """Inscrit un joueur connecté et informe ses amis de sa présence."""
        if not current_user.is_authenticated:
            return

        join_room(f"user_{current_user.id}")
        _online_users.add(current_user.id)
        emit("presence_snapshot", {"user_ids": list(_online_users)}, to=f"user_{current_user.id}")
        emit("presence_update", {"user_id": current_user.id, "online": True}, broadcast=True)

    @socketio.on("disconnect")
    def handle_disconnect():
        """Informe les clients que le joueur a fermé sa connexion."""
        if current_user.is_authenticated:
            _online_users.discard(current_user.id)
            emit("presence_update", {"user_id": current_user.id, "online": False}, broadcast=True)

    @socketio.on("request_presence")
    def handle_request_presence():
        """Renvoie l'état courant après le chargement du client."""
        if current_user.is_authenticated:
            emit("presence_snapshot", {"user_ids": list(_online_users)})

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

        # Une réponse mal formée ne doit jamais remonter en exception : elle
        # laisserait la manche ouverte et bloquerait les deux joueurs. On la
        # compte comme fausse, la partie continue.
        try:
            player_answer = convert_answer(current_question.mode, raw_answer)
            is_correct = check_answer(current_question, player_answer)
        except (ValueError, AttributeError, TypeError):
            is_correct = False

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