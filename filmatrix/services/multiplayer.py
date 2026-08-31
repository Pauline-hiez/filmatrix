"""Logique métier des parties multijoueur."""

import random
from datetime import datetime, timedelta

from filmatrix.extensions import db
from filmatrix.models import GameAnswer, GameSession, GameSessionQuestion, Question

INVITATION_DURATION_MINUTES = 15
QUESTIONS_PER_GAME = 5
QUESTION_DURATION = 15

# Nombre de propositions offertes par question en duel.
CHOICES_PER_QUESTION = 4

# Modes qui composent eux-mêmes leurs réponses : le QCM a ses options en base,
# le vrai/faux ses deux boutons, et la chronologie attend un ordre, pas un titre.
MODES_WITHOUT_CHOICES = ("qcm", "vrai_faux", "chronologie")


def offers_real_choices(mode: str) -> bool:
    """Vérifie qu'un mode a de quoi composer un vrai choix multiple

    Les modes à titre unique proposent le bon titre au milieu de leurres tirés
    des autres questions. Faute de titres distincts en nombre suffisant, le
    joueur se retrouverait devant une seule proposition — c'est-à-dire devant
    la réponse. Mieux vaut refuser le duel que le fausser."""
    if mode in MODES_WITHOUT_CHOICES:
        return True

    titles = {
        title
        for title in (answer_title(question) for question in Question.query.filter_by(mode=mode))
        if title is not None
    }

    return len(titles) >= CHOICES_PER_QUESTION


def create_game_invitation(host, guest, mode: str) -> GameSession | None:
    """Crée une invitation de partie. Renvoie None si le mode ne peut pas être joué en duel."""
    available_questions = Question.query.filter_by(mode=mode).all()

    if len(available_questions) < QUESTIONS_PER_GAME:
        return None

    if not offers_real_choices(mode):
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

def live_scores(game_session: GameSession) -> tuple[int, int]:
    """Calcule le score provisoire d'un duel à partir de ses réponses."""
    host_score = 0
    guest_score = 0
    answers_by_round: dict[int, list[GameAnswer]] = {}

    for answer in GameAnswer.query.filter_by(game_session_id=game_session.id).all():
        answers_by_round.setdefault(answer.question_index, []).append(answer)

    for round_answers in answers_by_round.values():
        correct_answers = sorted(
            (answer for answer in round_answers if answer.is_correct),
            key=lambda answer: answer.answered_at,
        )
        if not correct_answers:
            continue

        winner_id = correct_answers[0].user_id
        if winner_id == game_session.host_id:
            host_score += 1
        elif winner_id == game_session.guest_id:
            guest_score += 1

    return host_score, guest_score


def finalize_game(game_session: GameSession, total_questions: int) -> tuple[int, int]:
    """Copie le score provisoire uniquement après la dernière manche."""
    host_score, guest_score = live_scores(game_session)
    if game_session.current_question_index >= total_questions:
        game_session.host_score = host_score
        game_session.guest_score = guest_score
        game_session.status = "finished"

    return host_score, guest_score


def abandon_game(game_session: GameSession, user_id: int) -> bool:
    """Abandonne un duel et efface toutes ses réponses provisoires."""
    if user_id not in (game_session.host_id, game_session.guest_id):
        return False
    if game_session.status not in ("invited", "active"):
        return False

    GameAnswer.query.filter_by(game_session_id=game_session.id).delete(
        synchronize_session=False
    )
    game_session.host_score = 0
    game_session.guest_score = 0
    game_session.status = "abandoned"
    return True


def answer_title(question: Question) -> str | None:
    """Retourne le titre attendu par une question, ou None si elle n'en a pas

    Les modes à réponse libre rangent ce titre sous "film", sauf le film mélangé
    qui parle de "title". La chronologie, elle, attend un ordre : elle n'a aucun
    titre unique à proposer et n'entre donc pas dans ce cadre."""
    return question.correct_answer.get("film") or question.correct_answer.get("title")


def build_choices(question: Question, seed, count: int = CHOICES_PER_QUESTION) -> list[str]:
    """Propose le bon titre au milieu de leurres, pour une question de duel

    En duel le joueur n'a droit qu'à un seul essai : le faire écrire lui coûterait
    le point sur une faute de frappe ou une variante de titre, et la manche
    départagerait la vitesse de frappe plutôt que la culture cinéma.

    Les leurres sortent du même mode et du même type de contenu : une série isolée
    au milieu de trois films se repérerait sans rien connaître. Le tirage est
    reproductible, pour que les deux adversaires voient les mêmes propositions
    dans le même ordre."""
    correct = answer_title(question)

    if correct is None:
        return []

    def titles_of(query):
        return {
            title
            for title in (answer_title(other) for other in query.all())
            if title is not None and title != correct
        }

    decoys = titles_of(
        Question.query.filter(
            Question.mode == question.mode,
            Question.content_type == question.content_type,
            Question.id != question.id,
        )
    )

    # Trop peu de titres du même type : mieux vaut élargir au mode entier que
    # de servir un choix à deux propositions.
    if len(decoys) < count - 1:
        decoys |= titles_of(
            Question.query.filter(
                Question.mode == question.mode,
                Question.id != question.id,
            )
        )

    picker = random.Random(seed)
    # sorted() avant le tirage : l'ordre d'un ensemble varie d'un processus à
    # l'autre, et les deux joueurs sont servis par deux requêtes distinctes.
    chosen = picker.sample(sorted(decoys), min(count - 1, len(decoys)))

    choices = [correct] + chosen
    picker.shuffle(choices)

    return choices
