"""Tests des niveaux de jeu : temps de réponse accordé et récompenses."""

from filmatrix.extensions import db
from filmatrix.services.levels import coins_for_level, duration_for, resolve_level, xp_for_level
from filmatrix.models import Question, User


def test_duration_depends_on_mode_not_difficulty():
    """Le chrono est fixe par mode de jeu, jamais par la difficulté de la question"""
    assert duration_for("qcm") == 15
    assert duration_for("chronologie") == 25
    assert duration_for("blindtest") == 30


def test_higher_level_pays_more():
    """Plus le niveau monte, plus une bonne réponse rapporte"""
    assert (xp_for_level("facile"), coins_for_level("facile")) == (10, 2)
    assert (xp_for_level("moyen"), coins_for_level("moyen")) == (20, 4)
    assert (xp_for_level("difficile"), coins_for_level("difficile")) == (30, 6)


def test_unknown_mode_falls_back_on_a_default_duration():
    """Un mode inconnu ne doit pas faire planter le calcul du chrono"""
    assert duration_for("mode-inexistant") == 16


def test_unknown_level_falls_back_on_default():
    """Un niveau absent ou fantaisiste ne doit pas faire planter la partie"""
    assert resolve_level(None) == "moyen"
    assert resolve_level("legendaire") == "moyen"
    assert xp_for_level(None) == 20


def create_question(app, mode="qcm", difficulty="moyen"):
    """Crée une question simple dans la base de test"""
    with app.app_context():
        db.session.add(
            Question(
                mode=mode,
                prompt="Question de test niveau",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
                requires_account=False,
                difficulty=difficulty,
            )
        )
        db.session.commit()


def test_timer_follows_the_mode_not_the_question_difficulty(client, app):
    """La barre de temps suit le mode de jeu, pas la difficulté de la question tirée"""
    create_question(app, difficulty="facile")

    assert b'data-duration="15"' in client.get("/quiz/qcm/1").data
    # Un vieux ?level= d'URL (ancien système) reste sans effet.
    assert b'data-duration="15"' in client.get("/quiz/qcm/1?level=difficile").data


def test_duration_is_identical_across_difficulties_for_the_same_mode(client, app):
    """Une question facile et une question difficile du même mode ont le même chrono"""
    create_question(app, mode="vrai_faux", difficulty="facile")

    with app.app_context():
        db.session.add(
            Question(
                mode="vrai_faux",
                prompt="Autre question de test niveau",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
                requires_account=False,
                difficulty="difficile",
            )
        )
        db.session.commit()

    first = client.get("/quiz/vrai_faux/1").data
    second = client.get("/quiz/vrai_faux/2").data

    assert b'data-duration="12"' in first
    assert b'data-duration="12"' in second


def test_reward_follows_the_question_difficulty(client, app):
    """Une question difficile rapporte plus, même avec un ?level= périmé dans l'URL"""
    create_question(app, difficulty="difficile")

    with app.app_context():
        player = User(username="Joueuse", email="joueuse@filmatrix.fr")
        player.set_password("Azerty1!")
        db.session.add(player)
        db.session.commit()

    client.post("/connexion", data={"email": "joueuse@filmatrix.fr", "password": "Azerty1!"})
    client.post("/quiz/qcm/1?level=facile", data={"answer": "0"})

    with app.app_context():
        player = User.query.filter_by(username="Joueuse").first()
        # La question est enregistrée en "difficile" : c'est elle qui décide, pas ?level=.
        assert player.total_xp == 30
        assert player.coins == 6


def test_question_defaults_to_moyen_difficulty(app):
    """Une question créée sans difficulté explicite retombe sur moyen, comme le backfill de migration"""
    create_question(app)

    with app.app_context():
        assert Question.query.first().difficulty == "moyen"


def create_tagged_question(app, mode, tag_name, count=None):
    """Crée des questions rattachées à un thème, dans le mode demandé

    Un thème n'est proposé sur l'écran de préparation qu'à partir d'un
    certain nombre de questions (cf. TAG_MIN_QUESTIONS dans
    services/questions.py) : count s'aligne par défaut sur ce seuil, pour
    qu'un thème testé ici apparaisse bien tel qu'un joueur le verrait."""
    from filmatrix.models import Tag
    from filmatrix.services.questions import DEFAULT_TAG_MIN_QUESTIONS

    if count is None:
        count = DEFAULT_TAG_MIN_QUESTIONS

    with app.app_context():
        tag = Tag.query.filter_by(name=tag_name).first()
        if tag is None:
            tag = Tag(name=tag_name, tag_type="univers")
            db.session.add(tag)

        for index in range(count):
            question = Question(
                mode=mode,
                prompt=f"Question de test thème {index}",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
            )
            question.tags.append(tag)
            db.session.add(question)
        db.session.commit()


def test_setup_screen_only_offers_tags_present_in_the_mode(client, app):
    """Un thème sans question dans le mode choisi ne doit pas être proposé"""
    create_tagged_question(app, mode="qcm", tag_name="Star Wars")
    create_tagged_question(app, mode="citation", tag_name="Le Parrain")

    page_qcm = client.get("/quiz/qcm").data

    assert "Star Wars".encode() in page_qcm
    assert "Le Parrain".encode() not in page_qcm

    page_citation = client.get("/quiz/citation").data

    assert "Le Parrain".encode() in page_citation
    assert "Star Wars".encode() not in page_citation


def test_setup_screen_lists_no_tag_for_a_mode_without_tagged_questions(client, app):
    """Un mode dont aucune question n'est taguée ne doit proposer que « Tous les thèmes »"""
    create_tagged_question(app, mode="qcm", tag_name="Star Wars")

    page_emoji = client.get("/quiz/emoji").data

    assert "Tous les genres".encode() in page_emoji
    assert "Tous les univers".encode() in page_emoji
    assert "Tous les pays".encode() in page_emoji
    assert "Toutes les époques".encode() in page_emoji
    assert "Star Wars".encode() not in page_emoji
