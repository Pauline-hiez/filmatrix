"""Tests du score de fin de partie."""

from filmatrix.extensions import db
from filmatrix.models import Question, User
from filmatrix.services.score import (
    mark_run_fragment_awarded,
    read_run,
    record_answer,
    run_fragment_awarded,
    start_run,
)


def test_run_counts_correct_answers():
    """Le score doit distinguer les bonnes réponses du total joué"""
    store = {}
    start_run(store, "qcm")
    record_answer(store, "qcm", 1, True)
    record_answer(store, "qcm", 2, False)
    record_answer(store, "qcm", 3, True)

    assert read_run(store, "qcm") == {
        "correct": 2,
        "total": 3,
        "percentage": 67,
        "xp": 0,
        "coins": 0,
    }


def test_run_ignores_a_question_answered_twice():
    """Recharger la page pour répondre à nouveau ne doit pas gonfler le total"""
    store = {}
    start_run(store, "qcm")
    record_answer(store, "qcm", 1, True)
    record_answer(store, "qcm", 1, False)

    assert read_run(store, "qcm")["total"] == 1


def test_run_accumulates_what_was_earned():
    """L'XP et les pièces gagnées pendant la partie doivent être récapitulées"""
    store = {}
    start_run(store, "qcm")
    record_answer(store, "qcm", 1, True, xp=20, coins=4)
    record_answer(store, "qcm", 2, False)
    record_answer(store, "qcm", 3, True, xp=20, coins=4)

    score = read_run(store, "qcm")

    assert (score["xp"], score["coins"]) == (40, 8)


def test_run_of_another_mode_is_not_shown():
    """Le score d'une partie ne doit pas déborder sur un autre mode"""
    store = {}
    start_run(store, "qcm")
    record_answer(store, "qcm", 1, True)

    assert read_run(store, "citation") is None


def test_no_score_without_a_single_answer():
    """Arriver sur l'écran de fin sans avoir joué ne doit rien afficher"""
    store = {}
    start_run(store, "qcm")

    assert read_run(store, "qcm") is None
    assert read_run({}, "qcm") is None


def test_fragment_awarded_flag_is_per_run():
    """Le drapeau « un fragment par partie » démarre à False et marque le run"""
    store = {}
    start_run(store, "qcm")

    assert run_fragment_awarded(store, "qcm") is False

    mark_run_fragment_awarded(store, "qcm")

    assert run_fragment_awarded(store, "qcm") is True
    # Un autre mode n'est pas concerné.
    assert run_fragment_awarded(store, "citation") is False


def create_questions(app, count):
    """Crée des questions QCM dont la bonne réponse est toujours l'option 0"""
    with app.app_context():
        for index in range(count):
            db.session.add(
                Question(
                    mode="qcm",
                    prompt=f"Question {index}",
                    payload={"options": ["A", "B"]},
                    correct_answer={"index": 0},
                )
            )
        db.session.commit()


def test_end_screen_shows_the_score_of_the_run(client, app):
    """L'écran de fin doit afficher le score de la partie qui vient de s'achever"""
    create_questions(app, 3)

    client.get("/quiz/qcm/1?level=moyen")
    client.post("/quiz/qcm/1?level=moyen", data={"answer": "0"})
    client.post("/quiz/qcm/2?level=moyen", data={"answer": "1"})
    client.post("/quiz/qcm/3?level=moyen", data={"answer": "0"})

    end_screen = client.get("/quiz/qcm/4?level=moyen").data

    assert b"Ton score" in end_screen
    assert b"2" in end_screen
    assert "67 % de bonnes réponses".encode() in end_screen


def test_end_screen_shows_the_xp_earned_during_the_run(client, app):
    """Un joueur connecté doit voir ce que la partie lui a rapporté"""
    create_questions(app, 2)

    with app.app_context():
        player = User(username="Joueuse", email="joueuse@filmatrix.fr")
        player.set_password("Azerty1!")
        db.session.add(player)
        db.session.commit()

    client.post("/connexion", data={"email": "joueuse@filmatrix.fr", "password": "Azerty1!"})
    client.get("/quiz/qcm/1?level=difficile")
    client.post("/quiz/qcm/1?level=difficile", data={"answer": "0"})
    client.post("/quiz/qcm/2?level=difficile", data={"answer": "0"})

    end_screen = client.get("/quiz/qcm/3?level=difficile").data

    # Deux bonnes réponses en difficile : 2 x 30 XP et 2 x 6 pièces.
    assert "+ 60 XP".encode() in end_screen
    assert "+ 12 pièces".encode() in end_screen


def test_a_run_awards_only_one_fragment(client, app):
    """Plusieurs bonnes réponses dans une même partie ne donnent qu'un fragment"""
    from filmatrix.models import Album, Character, Question, Tag

    with app.app_context():
        player = User(username="Chasseur", email="chasseur@filmatrix.fr")
        player.set_password("Azerty1!")
        db.session.add(player)
        tag = Tag(name="Harry Potter", tag_type="univers")
        db.session.add(tag)
        db.session.commit()
        characters = [
            Character(name="Harry Potter", tag_id=tag.id, fragments_required=5),
            Character(name="Voldemort", tag_id=tag.id, fragments_required=5),
        ]
        db.session.add_all(characters)
        album = Album(name="Harry Potter")
        album.tags = [tag]
        album.characters = characters
        db.session.add(album)
        for index in range(2):
            question = Question(
                mode="qcm",
                prompt=f"Question {index}",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
            )
            question.tags = [tag]
            db.session.add(question)
        db.session.commit()

    client.post("/connexion", data={"email": "chasseur@filmatrix.fr", "password": "Azerty1!"})
    client.get("/quiz/qcm/1?level=moyen")
    first = client.post("/quiz/qcm/1?level=moyen", data={"answer": "0"}).get_json()
    second = client.post("/quiz/qcm/2?level=moyen", data={"answer": "0"}).get_json()

    assert first["fragment_result"] is not None
    assert second["fragment_result"] is None


def test_a_new_run_resets_the_previous_score(client, app):
    """Relancer le mode depuis la première question doit repartir de zéro"""
    create_questions(app, 2)

    client.get("/quiz/qcm/1")
    client.post("/quiz/qcm/1", data={"answer": "0"})
    client.post("/quiz/qcm/2", data={"answer": "0"})

    # Nouvelle partie : le GET de la première question remet le compteur à zéro.
    client.get("/quiz/qcm/1")
    client.post("/quiz/qcm/1", data={"answer": "1"})

    end_screen = client.get("/quiz/qcm/3").data

    assert b"Ton score" in end_screen
    assert "0 % de bonnes réponses".encode() in end_screen
