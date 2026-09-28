"""Tests du script de génération des questions Point commun
(scripts/generate_point_commun_questions.py) depuis les Work déjà en base."""

from filmatrix.extensions import db
from filmatrix.models import Question, Work
from scripts.generate_point_commun_questions import generate_point_commun_questions


def create_work(
    tmdb_id: int,
    title: str,
    saga: str | None = None,
    genres: list[str] | None = None,
    cast: list[str] | None = None,
) -> Work:
    work = Work(
        tmdb_id=tmdb_id,
        content_type="film",
        title=title,
        poster_url=f"https://example.com/{tmdb_id}.jpg",
        genres=genres or [],
        saga=saga,
        cast=cast or [],
    )
    db.session.add(work)
    db.session.commit()
    return work


def test_a_saga_shared_by_three_works_produces_a_question(app):
    """Un groupe de 3 Work partageant une saga doit produire une question
    dont la bonne réponse est cette saga, et dont aucun leurre n'est cette
    même saga (correction inutile puisqu'un seul champ saga par œuvre, mais
    on vérifie quand même l'absence de doublon de libellé)."""
    with app.app_context():
        for i in range(3):
            create_work(1000 + i, f"Harry Potter {i}", saga="Harry Potter Collection")
        # Sagas supplémentaires, pour fournir assez de leurres.
        for i, saga in enumerate(["Star Wars Collection", "Shrek Collection", "Rocky Collection"]):
            create_work(2000 + i, f"Œuvre {saga}", saga=saga)

        generate_point_commun_questions()

        questions = Question.query.filter_by(mode="point_commun").all()
        saga_questions = [
            q for q in questions
            if any("Harry Potter" in option for option in q.payload["options"])
        ]
        assert len(saga_questions) == 1

        question = saga_questions[0]
        correct_label = question.payload["options"][question.correct_answer["index"]]
        assert correct_label == "Ils appartiennent tous à la saga Harry Potter"
        assert len(question.payload["works"]) == 3
        assert len(question.payload["options"]) == 4


def test_a_genre_shared_by_three_works_never_has_an_ambiguous_decoy(app):
    """Un groupe de 3 Work partageant un genre doit produire une question
    dont AUCUN leurre n'est un genre partagé par les 3 œuvres montrées (sans
    quoi ce serait, en plus de la bonne réponse, une deuxième réponse
    correcte)."""
    with app.app_context():
        # Les 3 œuvres partagent "Horreur", mais pas un autre genre en commun
        # à elles trois (chacune a un deuxième genre différent).
        create_work(3000, "Scream", genres=["Horreur", "Policier"])
        create_work(3001, "Halloween", genres=["Horreur", "Thriller"])
        create_work(3002, "Conjuring", genres=["Horreur", "Mystère"])
        # Genres supplémentaires ailleurs dans la base, pour fournir des leurres.
        create_work(3003, "Autre 1", genres=["Comédie"])
        create_work(3004, "Autre 2", genres=["Drame"])
        create_work(3005, "Autre 3", genres=["Aventure"])

        generate_point_commun_questions()

        questions = Question.query.filter_by(mode="point_commun").all()
        genre_questions = [
            q for q in questions
            if any("Horreur" in option for option in q.payload["options"])
        ]
        assert len(genre_questions) == 1

        question = genre_questions[0]
        correct_label = question.payload["options"][question.correct_answer["index"]]
        assert correct_label == "Ils ont tous le genre Horreur en commun"

        shown_titles = {work["title"] for work in question.payload["works"]}
        shown_works = Work.query.filter(Work.title.in_(shown_titles)).all()
        for option in question.payload["options"]:
            if option == correct_label:
                continue
            # Le leurre doit être un genre qu'au moins une des 3 œuvres
            # montrées N'A PAS - sinon il serait, lui aussi, une bonne réponse.
            decoy_genre = option.removeprefix("Ils ont tous le genre ").removesuffix(" en commun")
            assert any(decoy_genre not in (w.genres or []) for w in shown_works)


def test_an_actor_shared_by_three_works_never_has_an_ambiguous_decoy(app):
    """Même garde anti-ambiguïté que le genre, appliquée au casting : aucun
    leurre-acteur ne doit être présent dans les 3 œuvres montrées."""
    with app.app_context():
        create_work(6000, "Fight Club", cast=["Brad Pitt", "Edward Norton"])
        create_work(6001, "Once Upon a Time in Hollywood", cast=["Brad Pitt", "Leonardo DiCaprio"])
        create_work(6002, "Ad Astra", cast=["Brad Pitt", "Tommy Lee Jones"])
        # Casting supplémentaire ailleurs dans la base, pour fournir des leurres.
        create_work(6003, "Autre 1", cast=["Meryl Streep"])
        create_work(6004, "Autre 2", cast=["Tom Hanks"])
        create_work(6005, "Autre 3", cast=["Robert De Niro"])

        generate_point_commun_questions()

        questions = Question.query.filter_by(mode="point_commun").all()
        cast_questions = [
            q for q in questions
            if any("Brad Pitt" in option for option in q.payload["options"])
        ]
        assert len(cast_questions) == 1

        question = cast_questions[0]
        correct_label = question.payload["options"][question.correct_answer["index"]]
        assert correct_label == "Ils ont tous Brad Pitt au casting"

        shown_titles = {work["title"] for work in question.payload["works"]}
        shown_works = Work.query.filter(Work.title.in_(shown_titles)).all()
        for option in question.payload["options"]:
            if option == correct_label:
                continue
            decoy_actor = option.removeprefix("Ils ont tous ").removesuffix(" au casting")
            assert any(decoy_actor not in (w.cast or []) for w in shown_works)


def test_running_the_script_twice_creates_no_duplicate(app):
    """Rejouer le script sur un état déjà généré ne doit créer aucune
    question supplémentaire (idempotence)."""
    with app.app_context():
        for i in range(3):
            create_work(4000 + i, f"Saga Film {i}", saga="Test Collection")
        for i, saga in enumerate(["Autre A", "Autre B", "Autre C"]):
            create_work(5000 + i, f"Œuvre {saga}", saga=saga)

        generate_point_commun_questions()
        first_count = Question.query.filter_by(mode="point_commun").count()
        assert first_count > 0

        generate_point_commun_questions()
        second_count = Question.query.filter_by(mode="point_commun").count()

        assert second_count == first_count
