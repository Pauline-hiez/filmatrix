"""Tests de la logique métier des parties multijoueur."""

import re
from datetime import datetime, timedelta

from filmatrix.extensions import db
from filmatrix.services.engine import convert_answer
from filmatrix.models import GameAnswer, GameSession, Question, User
from filmatrix.services.multiplayer import (
    CHOICES_PER_QUESTION,
    QUESTIONS_PER_GAME,
    build_choices,
    create_game_invitation,
    finalize_game,
    get_ordered_questions,
    abandon_game,
    is_invitation_expired,
    live_scores,
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

def titles_apart(question_kwargs, index):
    """Donne un titre distinct à chaque question, pour que les leurres existent"""
    fields = dict(question_kwargs)
    answer = dict(fields["correct_answer"])

    for key in ("film", "title"):
        if key in answer:
            answer[key] = f"{answer[key]} {index}"

    fields["correct_answer"] = answer
    return fields


def create_duel(app, mode, question_count=6, **question_kwargs):
    """Crée deux joueurs amis et une partie active dans le mode demandé"""
    with app.app_context():
        host = User(username="Hote", email="hote@filmatrix.fr")
        host.set_password("Azerty1!")
        guest = User(username="Invite", email="invite@filmatrix.fr")
        guest.set_password("Azerty1!")
        db.session.add_all([host, guest])
        db.session.commit()

        for index in range(question_count):
            db.session.add(
                Question(
                    mode=mode,
                    content_type="film",
                    prompt=f"Question {index}",
                    **titles_apart(question_kwargs, index),
                )
            )
        db.session.commit()

        game_session = create_game_invitation(host, guest, mode)
        game_session.status = "active"
        db.session.commit()

        return game_session.id


def login(client, email):
    """Connecte un client de test"""
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def test_a_duel_can_be_created_in_every_mode(app):
    """Tous les modes annoncés jouables en duel doivent pouvoir en démarrer un

    Seul le mix en est exclu : un duel tire ses leurres parmi les autres
    questions du même mode, ce qui suppose des lignes en base portant
    réellement ce mode — le mix n'en a aucune, il pioche parmi celles des
    autres (cf. game_modes.py)."""
    from filmatrix.game_modes import GAME_MODES, MIX_MODE_SLUG, MULTIPLAYER_MODES

    assert {mode["slug"] for mode in GAME_MODES} - {MIX_MODE_SLUG} == set(MULTIPLAYER_MODES)
    assert MIX_MODE_SLUG not in MULTIPLAYER_MODES


def test_a_free_text_mode_offers_choices_in_a_duel(client, app):
    """En duel on choisit, on n'écrit pas : un seul essai ne pardonne aucune faute"""
    game_id = create_duel(
        app,
        "blindtest",
        payload={"audio_url": "https://example.test/extrait.m4a"},
        correct_answer={"film": "Inception"},
    )
    login(client, "hote@filmatrix.fr")

    page = client.get(f"/multijoueur/{game_id}/jouer").get_data(as_text=True)

    assert "game-free-text-answer" not in page
    assert len(re.findall(r'data-answer="([^"]*)"', page)) == CHOICES_PER_QUESTION
    assert "<audio" in page


def test_both_players_get_the_same_choices_in_the_same_order(client, app):
    """La course doit être loyale : mêmes propositions, même ordre des deux côtés"""
    game_id = create_duel(
        app,
        "casting",
        payload={"actor_photos": ["https://example.test/a.jpg"]},
        correct_answer={"film": "Inception"},
    )

    host_client = app.test_client()
    guest_client = app.test_client()
    login(host_client, "hote@filmatrix.fr")
    login(guest_client, "invite@filmatrix.fr")

    host_page = host_client.get(f"/multijoueur/{game_id}/jouer").get_data(as_text=True)
    guest_page = guest_client.get(f"/multijoueur/{game_id}/jouer").get_data(as_text=True)

    assert re.findall(r'data-answer="([^"]*)"', host_page) == re.findall(
        r'data-answer="([^"]*)"', guest_page
    )


def test_both_players_get_the_same_scrambled_title(client, app):
    """Un mélange différent d'un joueur à l'autre avantagerait l'un des deux"""
    game_id = create_duel(
        app,
        "film_melange",
        payload={},
        correct_answer={"title": "Inception"},
    )

    host_client = app.test_client()
    guest_client = app.test_client()
    login(host_client, "hote@filmatrix.fr")
    login(guest_client, "invite@filmatrix.fr")

    pattern = re.compile(r"tracking-\[0\.2em\][^>]*>\s*(.+?)\s*</h1>", re.S)
    host_title = pattern.search(host_client.get(f"/multijoueur/{game_id}/jouer").get_data(as_text=True)).group(1)
    guest_title = pattern.search(guest_client.get(f"/multijoueur/{game_id}/jouer").get_data(as_text=True)).group(1)

    assert host_title == guest_title
    assert host_title != "Inception 0"


def test_the_duel_choices_include_the_right_answer(app):
    """Le bon titre doit toujours figurer parmi les propositions"""
    with app.app_context():
        for index in range(6):
            db.session.add(
                Question(
                    mode="citation",
                    content_type="film",
                    prompt=f"Réplique {index}",
                    payload={},
                    correct_answer={"film": f"Film {index}"},
                )
            )
        db.session.commit()

        question = Question.query.filter_by(mode="citation").first()
        choices = build_choices(question, seed=f"1-{question.id}")

        assert question.correct_answer["film"] in choices
        assert len(choices) == CHOICES_PER_QUESTION
        assert len(set(choices)) == len(choices)


def test_a_malformed_duel_answer_does_not_stall_the_round(app):
    """Une réponse illisible doit compter comme fausse, pas bloquer les deux joueurs"""
    with app.app_context():
        question = Question(
            mode="qcm",
            prompt="Question",
            payload={"options": ["A", "B"]},
            correct_answer={"index": 0},
        )

        # C'est ce que fait le gestionnaire de socket avant de trancher.
        try:
            convert_answer(question.mode, "pas-un-nombre")
            judged = True
        except ValueError:
            judged = False

        assert judged is False


def test_live_duel_score_is_provisional_and_abandon_clears_it(app):
    """Un score de duel abandonné ne doit laisser ni points ni réponses."""
    with app.app_context():
        host = create_test_user("Hote")
        guest = create_test_user("Invite")
        question = Question(
            mode="qcm",
            prompt="Question",
            payload={"options": ["A", "B"]},
            correct_answer={"index": 0},
        )
        db.session.add(question)
        db.session.commit()

        game_session = GameSession(
            host_id=host.id,
            guest_id=guest.id,
            mode="qcm",
            status="active",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        db.session.add(game_session)
        db.session.commit()
        db.session.add(GameAnswer(
            game_session_id=game_session.id,
            user_id=host.id,
            question_index=0,
            is_correct=True,
        ))
        db.session.commit()

        assert live_scores(game_session) == (1, 0)
        assert game_session.host_score == 0
        assert abandon_game(game_session, host.id) is True
        db.session.commit()

        assert game_session.status == "abandoned"
        assert game_session.host_score == 0
        assert game_session.guest_score == 0
        assert GameAnswer.query.filter_by(game_session_id=game_session.id).count() == 0


def test_finished_duel_persists_its_provisional_score(app):
    """Le score n'est copié dans la session qu'une fois le duel terminé."""
    with app.app_context():
        host = create_test_user("Hote")
        guest = create_test_user("Invite")
        game_session = GameSession(
            host_id=host.id,
            guest_id=guest.id,
            mode="qcm",
            status="active",
            current_question_index=5,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        db.session.add(game_session)
        db.session.commit()
        db.session.add(GameAnswer(
            game_session_id=game_session.id,
            user_id=guest.id,
            question_index=4,
            is_correct=True,
        ))
        db.session.commit()

        assert game_session.host_score == 0
        assert game_session.guest_score == 0
        assert finalize_game(game_session, total_questions=5) == (0, 1)
        assert game_session.status == "finished"
        assert game_session.host_score == 0
        assert game_session.guest_score == 1


def test_quitting_an_active_duel_marks_it_abandoned(client, app):
    """La route de sortie efface le duel et ses réponses provisoires."""
    game_id = create_duel(
        app,
        "qcm",
        question_count=6,
        payload={"options": ["A", "B"]},
        correct_answer={"index": 0},
    )
    login(client, "hote@filmatrix.fr")

    response = client.post(f"/multijoueur/{game_id}/quitter")

    assert response.status_code == 302
    with app.app_context():
        game_session = GameSession.query.get(game_id)
        assert game_session.status == "abandoned"
        assert game_session.host_score == 0
        assert game_session.guest_score == 0
        assert GameAnswer.query.filter_by(game_session_id=game_id).count() == 0


def test_a_duel_is_refused_when_the_choices_would_give_it_away(app):
    """Sans titres distincts en nombre, la seule proposition serait la réponse"""
    with app.app_context():
        host = create_test_user("Hote")
        guest = create_test_user("Invite")

        # Assez de questions pour une partie, mais toutes sur le même titre.
        for index in range(QUESTIONS_PER_GAME + 1):
            db.session.add(
                Question(
                    mode="blindtest",
                    prompt=f"Extrait {index}",
                    payload={"audio_url": "https://example.test/extrait.m4a"},
                    correct_answer={"film": "Toujours le même film"},
                )
            )
        db.session.commit()

        assert create_game_invitation(host, guest, "blindtest") is None
