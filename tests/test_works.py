"""Tests de l'entité Work : création idempotente depuis TMDB, filtrage
saga/genre, et script de rattrapage des questions existantes."""

from unittest.mock import patch

from filmatrix.extensions import db
from filmatrix.models import Question, Work
from filmatrix.services.questions import playable_question_query
from filmatrix.services.works import get_or_create_work
from scripts.migrate_questions_to_works import migrate_questions_to_works

MOVIE_DETAILS = {
    "id": 550,
    "title": "Fight Club",
    "poster_path": "/poster.jpg",
    "backdrop_path": None,
    "genre_ids": [18],
    "genres": ["Drame", "Thriller"],
    "saga": None,
}

SAGA_MOVIE_DETAILS = {
    "id": 671,
    "title": "Harry Potter à l'école des sorciers",
    "poster_path": "/hp.jpg",
    "backdrop_path": None,
    "genre_ids": [14],
    "genres": ["Fantastique", "Aventure"],
    "saga": "Harry Potter Collection",
}


def create_question(mode: str, correct_answer: dict, content_type: str = "film") -> Question:
    question = Question(
        mode=mode,
        prompt="Un énoncé quelconque",
        payload={},
        correct_answer=correct_answer,
        content_type=content_type,
    )
    db.session.add(question)
    db.session.commit()
    return question


def test_get_or_create_work_is_idempotent(app):
    """Deux appels avec le même tmdb_id+content_type ne créent jamais de doublon."""
    with app.app_context():
        with patch("filmatrix.services.works.get_movie_by_id", return_value=MOVIE_DETAILS):
            first = get_or_create_work(550, "film")
            second = get_or_create_work(550, "film")

        assert first.id == second.id
        assert Work.query.count() == 1
        assert first.title == "Fight Club"
        assert first.genres == ["Drame", "Thriller"]
        assert first.saga is None
        assert first.poster_url is not None


def test_get_or_create_work_fills_saga_from_collection(app):
    with app.app_context():
        with patch("filmatrix.services.works.get_movie_by_id", return_value=SAGA_MOVIE_DETAILS):
            work = get_or_create_work(671, "film")

        assert work.saga == "Harry Potter Collection"
        assert work.genres == ["Fantastique", "Aventure"]


def test_filter_by_saga(app):
    """build_question_query/playable_question_query isolent les questions
    d'une saga donnée, sans toucher aux questions d'une autre œuvre."""
    with app.app_context():
        with patch("filmatrix.services.works.get_movie_by_id", return_value=SAGA_MOVIE_DETAILS):
            saga_work = get_or_create_work(671, "film")
        with patch("filmatrix.services.works.get_movie_by_id", return_value=MOVIE_DETAILS):
            other_work = get_or_create_work(550, "film")

        saga_question = create_question("citation", {"film": "Harry Potter"})
        saga_question.work_id = saga_work.id
        other_question = create_question("citation", {"film": "Fight Club"})
        other_question.work_id = other_work.id
        db.session.commit()

        results = playable_question_query("citation", saga="Harry Potter Collection").all()

        assert [q.id for q in results] == [saga_question.id]


def test_filter_by_genre(app):
    """Le filtre genre matche une œuvre qui a ce genre parmi plusieurs, sans
    faux positif sur un genre au nom proche (cast+like sur le JSON échappé)."""
    with app.app_context():
        with patch("filmatrix.services.works.get_movie_by_id", return_value=SAGA_MOVIE_DETAILS):
            fantasy_work = get_or_create_work(671, "film")
        with patch("filmatrix.services.works.get_movie_by_id", return_value=MOVIE_DETAILS):
            drama_work = get_or_create_work(550, "film")

        fantasy_question = create_question("citation", {"film": "Harry Potter"})
        fantasy_question.work_id = fantasy_work.id
        drama_question = create_question("citation", {"film": "Fight Club"})
        drama_question.work_id = drama_work.id
        db.session.commit()

        results = playable_question_query("citation", genre="Fantastique").all()

        assert [q.id for q in results] == [fantasy_question.id]


def test_migrate_questions_to_works_links_matching_titles(app):
    """Le script relie les questions sans work_id à la Work trouvée sur TMDB,
    sans toucher à leurs tags, et sans rien changer pour les titres déjà liés."""
    with app.app_context():
        question = create_question("citation", {"film": "Fight Club"})
        already_linked = create_question("citation", {"film": "Peu importe"})
        with patch("filmatrix.services.works.get_movie_by_id", return_value=MOVIE_DETAILS):
            existing_work = get_or_create_work(550, "film")
        already_linked.work_id = existing_work.id
        db.session.commit()

        with patch(
            "scripts.migrate_questions_to_works.search_movie", return_value={"id": 550}
        ), patch("filmatrix.services.works.get_movie_by_id", return_value=MOVIE_DETAILS):
            migrate_questions_to_works()

        db.session.refresh(question)
        assert question.work_id == existing_work.id
        # Aucun doublon de Work créé pour le même tmdb_id+content_type.
        assert Work.query.count() == 1


def test_migrate_questions_to_works_is_idempotent(app):
    """Rejouer le script ne change plus rien une fois toutes les questions liées."""
    with app.app_context():
        create_question("citation", {"film": "Fight Club"})

        with patch(
            "scripts.migrate_questions_to_works.search_movie", return_value={"id": 550}
        ), patch("filmatrix.services.works.get_movie_by_id", return_value=MOVIE_DETAILS):
            migrate_questions_to_works()
            migrate_questions_to_works()

        assert Work.query.count() == 1
        assert Question.query.filter(Question.work_id.is_(None)).count() == 0


def test_migrate_questions_to_works_logs_unmatched_titles(app, capsys):
    """Un titre sans correspondance TMDB reste sans work_id et est logué."""
    with app.app_context():
        question = create_question("citation", {"film": "Titre Introuvable"})

        with patch("scripts.migrate_questions_to_works.search_movie", return_value=None):
            migrate_questions_to_works()

        db.session.refresh(question)
        assert question.work_id is None
        captured = capsys.readouterr()
        assert "Titre Introuvable" in captured.out
